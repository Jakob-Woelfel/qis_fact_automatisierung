"""
konfiguration.py
----------------
Lädt und validiert die Benutzer-Konfiguration aus config.yaml.
Berechnet den gewünschten Buchungszeitraum als Von/Bis-Datumsstrings.
"""
import calendar
from datetime import date
from pathlib import Path

import yaml


def konfiguration_laden(pfad: Path) -> dict:
    """Liest config.yaml ein und prüft die Pflichtfelder.

    Parameter
    ---------
    pfad : Path
        Pfad zur config.yaml-Datei.

    Rückgabe
    --------
    dict
        Geparste Konfiguration als Dictionary.

    Fehler
    ------
    FileNotFoundError
        Falls config.yaml nicht existiert.
    ValueError
        Falls Pflichtfelder fehlen oder ungültig sind.
    """
    if not pfad.exists():
        raise FileNotFoundError(
            f"config.yaml nicht gefunden: {pfad}\n"
            "Bitte die Datei im Projektordner anlegen."
        )

    with open(pfad, encoding="utf-8") as f:
        konfig = yaml.safe_load(f) or {}

    kostenstellen = konfig.get("kostenstellen") or []
    if not kostenstellen:
        raise ValueError(
            "Keine Kostenstellen in config.yaml angegeben. "
            "Bitte mindestens eine Kostenstelle eintragen."
        )

    return konfig


def datum_berechnen(zeitraum: dict) -> tuple[str, str]:
    """Berechnet Von- und Bis-Datum anhand des konfigurierten Modus.

    Parameter
    ---------
    zeitraum : dict
        Zeitraum-Abschnitt aus config.yaml mit Feldern:
        - modus: "vormonat" | "aktueller_monat" | "aktuelles_jahr" | "manuell"
        - datum_von: Datum im Format TT.MM.JJJJ (nur bei modus "manuell")
        - datum_bis: Datum im Format TT.MM.JJJJ (nur bei modus "manuell")

    Rückgabe
    --------
    tuple[str, str]
        (datum_von, datum_bis) im Format TT.MM.JJJJ
    """
    modus = zeitraum["modus"]
    heute = date.today()

    if modus == "aktuelles_jahr":
        von = date(heute.year, 1, 1)
        bis = date(heute.year, 12, 31)

    elif modus == "aktueller_monat":
        letzter_tag = calendar.monthrange(heute.year, heute.month)[1]
        von = date(heute.year, heute.month, 1)
        bis = date(heute.year, heute.month, letzter_tag)

    elif modus == "vormonat":
        if heute.month == 1:
            jahr, monat = heute.year - 1, 12
        else:
            jahr, monat = heute.year, heute.month - 1
        letzter_tag = calendar.monthrange(jahr, monat)[1]
        von = date(jahr, monat, 1)
        bis = date(jahr, monat, letzter_tag)

    elif modus == "manuell":
        return zeitraum["datum_von"], zeitraum["datum_bis"]

    else:
        raise ValueError(
            f"Unbekannter Zeitraum-Modus: '{modus}'. "
            "Erlaubte Werte: vormonat, aktueller_monat, aktuelles_jahr, manuell"
        )

    return von.strftime("%d.%m.%Y"), bis.strftime("%d.%m.%Y")
