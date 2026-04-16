"""
src/processor.py
----------------
Nachbearbeitungsmodul für QIS-Einzelbuchungs-Exporte.

Dieses Modul wird von anderen Modulen (z.B. download.py oder main.py) importiert
und übernimmt alle Transformationsschritte für die aus QIS exportierten Dateien.

Ablauf (Überblick):
- CSV aus QIS einlesen (Semikolon-getrennt)
- Beträge bereinigen und in numerisches Format bringen
- Relevante Buchungszeilen filtern (Ausgabe, Bewilligung ohne Einnahme, Forderung, Verpflichtung)
- Kostenarten über ein YAML-Mapping in neue Kategorien überführen
- Für jeden Buchungstyp ein einheitliches FACT-Format aufbauen
- Alle Typen zu einem DataFrame zusammenführen
- Ergebnis als Excel-Datei für FACT exportieren

Verwendung (aus einem anderen Modul):
    from src.processor import process_buchungsdatei
    zielpfad = process_buchungsdatei(Path("/pfad/zur/datei.csv"), Path("/pfad/zum/zielordner"))
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime
import re
import pandas as pd
import unicodedata
import yaml
from functools import lru_cache

# -------------------- Einstellungen / Konstanten --------------------

# Spalten-Indizes aus dem QIS-Export (0-basiert),
# damit der restliche Code sprechende Namen statt Magic Numbers nutzt.
IDX_BETRAG = 9                # Spalte mit dem Buchungsbetrag
IDX_AUSGABE_FLAG = 10         # Spalte mit Buchungstyp ("Ausgabe", "Bewilligung ohne Einnahme", ...)
IDX_DATUM = 23                # Spalte mit dem Buchungsdatum im Format TT.MM.JJJJ
IDX_IDENT = 25                # Eindeutiger Buchungs-Identifizierer im Export
IDX_BEZEICHNUNG = 30          # Bezeichnung / Freitext zur Buchung
IDX_ORIGINALE_KOSTENART = 35  # Ursprüngliche Kostenart / Kommentar / Notiz im Export

# Spaltenname der Kostenart-Textspalte im QIS-Export.
# Diese enthält die alte Kostenartennummer (z.B. 8500) in Textform.
COL_KOSTENART_TEXT = "Erlös- / Kostenart"

# Fallback-Bezeichnung, falls eine Kostenart nicht im Mapping gefunden wird.
FALLBACK = "Sonstige allgemeine Verwaltungsausgaben"


def _normalisiere_nummer(x) -> str:
    """Normalisiert eine Kostenart-Nummer auf eine reine Ziffernfolge.

    Beispiele:
    - "8.500"   → "8500"
    - "  8 700 " → "8700"

    Nicht-Ziffern werden entfernt, der Rest als String zurückgegeben.
    """
    # None wird zu Leerstring, sonst in String konvertieren
    s = "" if x is None else str(x)
    # Unicode-Normalisierung und Trimmen von Leerzeichen
    s = unicodedata.normalize("NFKC", s).strip()
    # Alles außer Ziffern entfernen
    s = re.sub(r"\D+", "", s)
    return s


def korrigiere_umlaute(text):
    """Korrigiert bekannte, fehlerhafte Zeichen aus dem Export zu echten Umlauten.

    Die QIS-Exporte enthalten vereinzelt falsche Byte-Interpretationen,
    z.B. "‰" statt "ä". Diese Funktion ersetzt nur bekannte Problemfälle
    und lässt sonstigen Text unverändert.
    """
    if isinstance(text, str):
        ersetzungen = {
            "‰": "ä",
            "ˆ": "ö",
            "¸": "ü",
        }
        for falsch, richtig in ersetzungen.items():
            text = text.replace(falsch, richtig)
    return text


@lru_cache(maxsize=1)
def lade_kostenart_mapping() -> dict[str, str]:
    """Liest das Mapping *alte Kostenart-Nummer → neue Kostenart (Name)* aus YAML.

    - Die YAML-Datei liegt unter config/kostenarten_number_to_new.yaml
      (relativ zum Projektstamm, eine Ebene über diesem Modul).
    - Keys werden auf reine Ziffern normalisiert ("8.500" → "8500").
    - Werte werden zu Strings konvertiert; leere Werte erhalten den FALLBACK.
    - Das Ergebnis wird per LRU-Cache nur einmal pro Prozess eingelesen.
    """
    # Projektstamm ermitteln: src/ liegt eine Ebene unter dem Projektstamm
    projektstamm = Path(__file__).resolve().parent.parent
    yaml_pfad = projektstamm / "config" / "kostenarten_number_to_new.yaml"

    # Frühzeitige, klare Fehlermeldung, falls das Mapping fehlt
    if not yaml_pfad.exists():
        raise FileNotFoundError(f"Mapping-Datei fehlt: {yaml_pfad}")

    # YAML-Datei einlesen
    with open(yaml_pfad, "r", encoding="utf-8") as f:
        roh = yaml.safe_load(f) or {}

    # Sicherstellen, dass die YAML-Struktur ein Dict ist
    if not isinstance(roh, dict):
        raise ValueError(f"Mapping-YAML muss ein Mapping/Dict sein: {yaml_pfad}")

    # Keys bereinigen (nur Ziffern) und Werte als Strings hinterlegen
    bereinigt: dict[str, str] = {}
    for k, v in roh.items():
        # Ursprünglichen Key (z.B. "8.500") in reine Zahl ("8500") umformen
        schluessel = _normalisiere_nummer(k)
        if not schluessel:
            # Leere Keys werden übersprungen
            continue
        # Falls kein Wert definiert ist, auf FALLBACK zurückfallen
        bereinigt[schluessel] = str(v) if v is not None else FALLBACK
    return bereinigt


def mappe_kostenart_series(series: pd.Series) -> pd.Series:
    """Mappt eine Series mit alten Kostenart-Nummern auf neue Kostenart-Namen.

    Parameter:
        series: Spalte mit alten Kostenart-Nummern (z.B. 8500 oder "8.700").

    Rückgabe:
        Neue pd.Series mit den zugehörigen neuen Kostenart-Namen.
        Nicht gefundene oder fehlerhafte Nummern werden als FALLBACK gesetzt.
        Index und Länge der Series bleiben erhalten.
    """
    # Mapping einmalig (pro Prozess) laden
    mapping = lade_kostenart_mapping()

    # Alte Werte in Strings umwandeln, fehlende durch Leerstring ersetzen,
    # dann auf reine Ziffern normalisieren
    normierte_schluessel = series.astype("string").fillna("").map(_normalisiere_nummer)

    # Für jede normalisierte Nummer den passenden neuen Namen aus dem Mapping ziehen
    gemappt = normierte_schluessel.map(lambda k: mapping.get(k, FALLBACK))

    # Index & Länge bleiben identisch zur Eingabe (wichtige Invariante)
    return gemappt


def erstelle_fact_dataframe(df, gemappte_kostenarten: pd.Series | None = None, df_typ: str = "Ausgaben") -> pd.DataFrame:
    """Erzeugt ein FACT-kompatibles DataFrame aus einem QIS-Teil-DataFrame.

    Parameter
    ---------
    df : pd.DataFrame
        Roh-DataFrame mit den relevanten QIS-Spalten (bereits auf einen Typ vorgefiltert).
    gemappte_kostenarten : pd.Series | None
        Gemappte Kostenarten-Namen pro Zeile; wird nur für df_typ="Ausgaben" benötigt.
    df_typ : str
        Typ des Buchungsblocks (z.B. "Ausgaben", "Bewilligung ohne Einnahme",
        "Forderungen", "Verpflichtungen"). Steuert Kommentar und Kostenart-Spalte.

    Rückgabe
    --------
    pd.DataFrame
        Neues DataFrame im Ziel-Format für FACT.
    """
    # Neues DataFrame mit gleichem Index wie das Eingabe-DataFrame
    neue_daten = pd.DataFrame(index=df.index)

    # Bezeichnungstext aus dem Export übernehmen und Encoding-Fehler korrigieren
    neue_daten["bezeichnung"] = df.iloc[:, IDX_BEZEICHNUNG].apply(korrigiere_umlaute)

    # Betrag sicher in numerisches Format konvertieren (fehlerhafte Werte → NaN)
    neue_daten["betrag"] = pd.to_numeric(df.iloc[:, IDX_BETRAG], errors="coerce")

    # Flag, ob es sich um eine Planbuchung handelt (hier immer Ist-Buchungen → "false")
    neue_daten["istPlanbuchung"] = "false"

    # Buchungsdatum aus dem Textformat TT.MM.JJJJ in ein Datumsobjekt konvertieren
    neue_daten["datum"] = pd.to_datetime(df.iloc[:, IDX_DATUM], format="%d.%m.%Y", errors="coerce")

    # Eindeutigen Buchungs-Identifizierer aus dem Export übernehmen
    neue_daten["buchungsIdentifizierer"] = df.iloc[:, IDX_IDENT]

    # Qualitätsflag: Alle erzeugten Zeilen werden als formal korrekt markiert
    neue_daten["buchungIstKorrekt"] = "true"

    # Typ-spezifische Behandlung der Kostenart und des Kommentars
    if df_typ == "Ausgaben":
        # Für Ausgaben benötigen wir zwingend die gemappten Kostenarten
        if gemappte_kostenarten is None:
            raise ValueError("gemappte_kostenarten darf für df_typ 'Ausgaben' nicht None sein")

        # Neue Kostenart (Name) und kostenartId werden identisch gesetzt
        neue_daten["kostenart"] = gemappte_kostenarten
        neue_daten["kostenartId"] = gemappte_kostenarten  # bewusst identisch gehalten

        # Kommentar enthält den ursprünglichen Kostenarten-Text aus dem Export
        neue_daten["kommentar"] = df.iloc[:, IDX_ORIGINALE_KOSTENART].apply(korrigiere_umlaute)

    elif df_typ == "Bewilligung ohne Einnahme":
        # Für Bewilligungen ohne Einnahme wird eine Dummy-Kostenart gesetzt
        neue_daten["kostenart"] = "Andere Kostenarten (Platzhalter-Dummy)"
        neue_daten["kostenartId"] = "Andere Kostenarten (Platzhalter-Dummy)"

        # Kommentar macht den Typ der Buchung kenntlich
        neue_daten["kommentar"] = "Bewilligung ohne Einnahme"

    elif df_typ == "Forderungen":
        # Für Forderungen wird ebenfalls eine Dummy-Kostenart verwendet
        neue_daten["kostenart"] = "Andere Kostenarten (Platzhalter-Dummy)"
        neue_daten["kostenartId"] = "Andere Kostenarten (Platzhalter-Dummy)"

        # Kommentar markiert diese Zeilen als Forderungen
        neue_daten["kommentar"] = "Forderungen"

    elif df_typ == "Verpflichtungen":
        # Für Verpflichtungen wird ebenfalls eine Dummy-Kostenart verwendet
        neue_daten["kostenart"] = "Andere Kostenarten (Platzhalter-Dummy)"
        neue_daten["kostenartId"] = "Andere Kostenarten (Platzhalter-Dummy)"

        # Kommentar markiert diese Zeilen als Verpflichtungen
        neue_daten["kommentar"] = "Verpflichtungen"

    else:
        # Fallback für nicht explizit behandelte Typen
        neue_daten["kostenart"] = "Andere Kostenarten (Platzhalter-Dummy)"
        neue_daten["kostenartId"] = "Andere Kostenarten (Platzhalter-Dummy)"

        # Kommentar: Zur Sicherheit wird die Bezeichnung übernommen
        neue_daten["kommentar"] = df.iloc[:, IDX_BEZEICHNUNG].apply(korrigiere_umlaute)

    return neue_daten


# -------------------- Hauptfunktion: End-to-End-Verarbeitung --------------------


def process_buchungsdatei(dateipfad: Path, zielordner: Path) -> Path | None:
    """Transformiert eine heruntergeladene QIS-Datei in eine FACT-Excel.

    Diese Funktion ist der zentrale Einstiegspunkt und wird von anderen Modulen
    (z.B. download.py oder main.py) nach jedem erfolgreichen Export aufgerufen.

    Parameter
    ----------
    dateipfad : Path
        Pfad zur heruntergeladenen Datei (semikolon-getrennte CSV aus QIS).
    zielordner : Path
        Zielordner, in dem die erzeugte FACT-Excel abgelegt werden soll.

    Rückgabe
    -------
    Path | None
        Pfad zur erzeugten Excel-Datei oder None bei einem Fehler oder
        wenn keine relevanten Buchungszeilen vorhanden sind.
    """
    # Sicherstellen, dass der Zielordner existiert
    zielordner.mkdir(parents=True, exist_ok=True)

    # 1) Datei einlesen
    # dtype=object verhindert, dass pandas einzelne Spalten als StringDtype
    # einliest — das würde das spätere Setzen numerischer Werte blockieren.
    try:
        # QIS liefert eine semikolon-getrennte CSV.
        df = pd.read_csv(dateipfad, sep=";", encoding="utf-8", engine="python", dtype=object)
    except Exception as e:
        print(f"Fehler beim Einlesen der Datei: {e}")
        return None

    # 2) Beträge säubern und in numerische Werte umwandeln
    #    - Tausenderpunkte entfernen (deutsches Format: "1.234,56")
    #    - Dezimalkomma in Dezimalpunkt konvertieren
    #    - Leerzeichen am Rand beschneiden
    betrag_roh = df.iloc[:, IDX_BETRAG].astype(str)
    betrag_roh = (
        betrag_roh.str.replace(".", "", regex=False)   # Tausenderpunkte entfernen
                  .str.replace(",", ".", regex=False)  # Komma → Punkt
                  .str.strip()                         # Leerzeichen entfernen
    )
    # Konvertierung in float; ungültige Werte werden zu NaN
    df.iloc[:, IDX_BETRAG] = pd.to_numeric(betrag_roh, errors="coerce")

    # 3) Nur relevante Buchungsarten behalten:
    #    Ausgabe, Bewilligung ohne Einnahme, Forderung, Verpflichtung
    erlaubte_typen = [
        "Ausgabe",
        "Bewilligung ohne Einnahme",
        "Forderung",
        "Verpflichtung",
    ]

    # DataFrame auf die obigen Typen einschränken
    df = df[df.iloc[:, IDX_AUSGABE_FLAG].isin(erlaubte_typen)]

    # Teil-DataFrames pro Typ erzeugen — werden einzeln in FACT-Form gebracht
    df_ausgaben = df[df.iloc[:, IDX_AUSGABE_FLAG] == "Ausgabe"]
    df_bewilligungen_ohne_einnahmen = df[df.iloc[:, IDX_AUSGABE_FLAG] == "Bewilligung ohne Einnahme"]
    df_forderungen = df[df.iloc[:, IDX_AUSGABE_FLAG] == "Forderung"]
    df_verpflichtungen = df[df.iloc[:, IDX_AUSGABE_FLAG] == "Verpflichtung"]

    # 4) Kostenarten-Spalte finden und auf neue Kategorien mappen
    if COL_KOSTENART_TEXT in df.columns:
        # Kostenart-Textspalte vorhanden → Mapping anwenden
        gemappte_kostenarten = mappe_kostenart_series(df[COL_KOSTENART_TEXT])
    else:
        # Keine Kostenart-Spalte vorhanden → alles dem FALLBACK zuordnen
        gemappte_kostenarten = pd.Series([FALLBACK] * len(df), index=df.index)

    # 5) Für jeden Typ ein FACT-kompatibles DataFrame erzeugen
    teilframes: list[pd.DataFrame] = []

    # --- Ausgaben ---
    if not df_ausgaben.empty:
        # Für Ausgaben: Kostenarten-Mapping auf den Index von df_ausgaben einschränken
        neue_ausgaben = erstelle_fact_dataframe(
            df_ausgaben,
            gemappte_kostenarten.loc[df_ausgaben.index],
            df_typ="Ausgaben",
        )
        teilframes.append(neue_ausgaben)

    # --- Bewilligungen ohne Einnahmen ---
    if not df_bewilligungen_ohne_einnahmen.empty:
        neue_bewilligungen = erstelle_fact_dataframe(
            df_bewilligungen_ohne_einnahmen,
            df_typ="Bewilligung ohne Einnahme",
        )
        teilframes.append(neue_bewilligungen)

    # --- Forderungen ---
    if not df_forderungen.empty:
        neue_forderungen = erstelle_fact_dataframe(
            df_forderungen,
            df_typ="Forderungen",
        )
        teilframes.append(neue_forderungen)

    # --- Verpflichtungen ---
    if not df_verpflichtungen.empty:
        neue_verpflichtungen = erstelle_fact_dataframe(
            df_verpflichtungen,
            df_typ="Verpflichtungen",
        )
        teilframes.append(neue_verpflichtungen)

    # Sicherstellen, dass es überhaupt relevante Buchungssätze gibt
    if teilframes:
        # Alle Teil-DataFrames vertikal untereinander hängen;
        # ignore_index=True sorgt für einen durchgehenden Index ab 0
        neue_daten_gesamt = pd.concat(teilframes, ignore_index=True)
    else:
        # Keine Buchung gefunden → keine FACT-Datei erzeugen
        print("Keine passenden Buchungssätze gefunden — keine FACT-Datei erzeugt.")
        return None

    # 6) Dateinamen für die Ziel-Excel konstruieren
    originalname = dateipfad.stem  # Dateiname ohne Suffix

    # Optionale Bereinigung unschöner QIS-Standardbenennungen mit Unterstrichen
    originalname = re.sub(r"(^|_)_-_-(?:_|-)*", "_", originalname).strip("_")

    # Heutiges Datum im ISO-Format für die Dateibenennung
    heutiges_datum = datetime.today().strftime("%Y-%m-%d")

    # Finaler Dateiname: <original>_<JJJJ-MM-TT>_FACT.xlsx
    neuer_dateiname = f"{originalname}_{heutiges_datum}_FACT.xlsx"
    zielpfad = zielordner / neuer_dateiname

    # 7) Excel schreiben
    try:
        # ExcelWriter mit openpyxl, Datumsformat TT.MM.JJJJ
        with pd.ExcelWriter(zielpfad, engine="openpyxl", datetime_format="DD.MM.YYYY") as writer:
            neue_daten_gesamt.to_excel(writer, index=False)
        print(f"FACT-Excel gespeichert: {zielpfad}")
        return zielpfad
    except Exception as e:
        print(f"Fehler beim Schreiben der FACT-Excel: {e}")
        return None


def main() -> None:
    """Manueller Test-Entry-Point — nur zur lokalen Entwicklung.

    Hinweis: Diese Funktion dient ausschließlich zu Testzwecken während der
    Entwicklung. Im regulären Workflow wird process_buchungsdatei() von anderen
    Modulen importiert und aufgerufen. Den Dateipfad bei Bedarf anpassen.
    """
    print(
        "main() ist nur zum manuellen Testen gedacht.\n"
        "Bitte Dateipfad und Zielordner in dieser Funktion anpassen und erneut ausführen."
    )


if __name__ == "__main__":
    # Wenn das Skript direkt ausgeführt wird, läuft die main()-Funktion.
    # Im regulären Workflow wird process_buchungsdatei() importiert.
    main()


# ---------------------------------------------------------------------------
# DOKU (Kurz & Knapp – technische Zusammenfassung):
# 1) Einlesen: Semikolon-getrennte CSV → DataFrame df.
# 2) Betrag: Beträge bereinigen (Tausenderpunkte entfernen, Komma → Punkt)
#    und in float umwandeln. Ungültige Werte → NaN (errors='coerce').
# 3) Filter: Nur Zeilen mit "Ausgabe", "Bewilligung ohne Einnahme",
#    "Forderung" oder "Verpflichtung" bleiben erhalten.
# 4) Kostenarten-Mapping:
#    - config/kostenarten_number_to_new.yaml liefert Nummer → neuer Name.
#    - Keys werden auf reine Ziffern normalisiert ("8.500" → "8500").
#    - Nicht gemappte oder leere Werte landen im FALLBACK
#      ("Sonstige allgemeine Verwaltungsausgaben").
#    - Das Mapping wird per @lru_cache nur einmal von der Platte gelesen.
# 5) Ausgabestruktur: Für jeden Typ wird ein DataFrame in FACT-Struktur erzeugt
#    (bezeichnung, betrag, kostenart, kostenartId, datum,
#     buchungsIdentifizierer, kommentar, Flags).
# 6) Zusammenführung: Alle Typ-DataFrames werden per pd.concat zu einem
#    Gesamt-DataFrame zusammengeführt (ignore_index=True).
# 7) Excel-Export: Dateiname <original>_<JJJJ-MM-TT>_FACT.xlsx
#    im Zielordner, Datumsspalten im Format TT.MM.JJJJ.
#
# Design-Entscheidungen:
# - Keine Magic Numbers: Spalten werden über Konstanten (IDX_*) adressiert.
# - Robuste Pfadauflösung: YAML relativ zu diesem Skript geladen (../config/).
# - Vektorisierte Zuordnung: Mapping via .map() über normalisierte Keys.
# - Fehlertoleranz: Nicht gemappte Kostenarten fallen sauber in FALLBACK.
# - Performance: Mapping-Datei via @lru_cache memoisiert (einmaliges Einlesen).
# - Klare Trennung von Rohdaten (df_*) und Zielstruktur (FACT-DataFrames).
# ---------------------------------------------------------------------------
