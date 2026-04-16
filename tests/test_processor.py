from pathlib import Path
import pandas as pd
import pytest
from src.processor import process_buchungsdatei

FIXTURE = Path("tests/fixtures/beispiel_buchungen.csv")


def test_ausgabe_wird_verarbeitet(tmp_path):
    """Ausgabe-Zeilen landen in der FACT-Datei mit korrektem Betrag."""
    ergebnis = process_buchungsdatei(FIXTURE, tmp_path)
    assert ergebnis is not None
    df = pd.read_excel(ergebnis)
    assert any(df["bezeichnung"].str.contains("Testbuchung Ausgabe"))
    ausgabe_zeile = df[df["bezeichnung"] == "Testbuchung Ausgabe"]
    assert ausgabe_zeile["betrag"].iloc[0] == pytest.approx(1234.56)


def test_irrelevante_zeilen_werden_gefiltert(tmp_path):
    """Zeilen mit unbekanntem Typ erscheinen nicht in der FACT-Datei."""
    ergebnis = process_buchungsdatei(FIXTURE, tmp_path)
    df = pd.read_excel(ergebnis)
    assert not any(df["bezeichnung"].str.contains("Wird gefiltert"))


def test_alle_vier_typen_vorhanden(tmp_path):
    """Alle vier Buchungstypen werden verarbeitet."""
    ergebnis = process_buchungsdatei(FIXTURE, tmp_path)
    df = pd.read_excel(ergebnis)
    bezeichnungen = df["bezeichnung"].tolist()
    assert any("Ausgabe" in str(b) for b in bezeichnungen)
    assert any("Bewilligung" in str(b) for b in bezeichnungen)
    assert any("Forderung" in str(b) for b in bezeichnungen)
    assert any("Verpflichtung" in str(b) for b in bezeichnungen)


def test_fact_datei_spalten(tmp_path):
    """Die erzeugte FACT-Datei enthält alle erwarteten Spalten."""
    ergebnis = process_buchungsdatei(FIXTURE, tmp_path)
    df = pd.read_excel(ergebnis)
    erwartete_spalten = {
        "bezeichnung", "betrag", "istPlanbuchung", "datum",
        "buchungsIdentifizierer", "buchungIstKorrekt", "kostenart",
        "kostenartId", "kommentar",
    }
    assert erwartete_spalten.issubset(set(df.columns))


def test_leere_csv_gibt_none(tmp_path):
    """Eine CSV ohne passende Buchungszeilen gibt None zurück."""
    # Erstelle eine CSV mit Header aber ohne relevante Buchungstypen
    leere_csv = tmp_path / "leer.csv"
    # Lies die Fixture um die Headerzeile zu bekommen
    header = FIXTURE.read_text(encoding="utf-8").split("\n")[0]
    leere_csv.write_text(header + "\n", encoding="utf-8")
    ergebnis = process_buchungsdatei(leere_csv, tmp_path)
    assert ergebnis is None
