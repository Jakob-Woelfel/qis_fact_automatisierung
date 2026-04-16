import pytest
from src.konfiguration import konfiguration_laden, datum_berechnen


def test_konfiguration_laden(tmp_path):
    """Lädt eine gültige config.yaml korrekt."""
    konfig_datei = tmp_path / "config.yaml"
    konfig_datei.write_text(
        "kostenstellen:\n  - '12345'\nzeitraum:\n  modus: aktuelles_jahr\n"
        "  datum_von: '01.01.2025'\n  datum_bis: '31.12.2025'\n"
        "ausgabe_ordner: '~/Downloads/test'\ndebug_browser: false\n",
        encoding="utf-8",
    )
    konfig = konfiguration_laden(konfig_datei)
    assert konfig["kostenstellen"] == ["12345"]
    assert konfig["zeitraum"]["modus"] == "aktuelles_jahr"
    assert konfig["debug_browser"] is False


def test_konfiguration_fehlt(tmp_path):
    """Fehlende config.yaml wirft einen klaren Fehler."""
    with pytest.raises(FileNotFoundError, match="config.yaml"):
        konfiguration_laden(tmp_path / "config.yaml")


def test_konfiguration_keine_kostenstellen(tmp_path):
    """Leere Kostenstellen-Liste wirft einen klaren Fehler."""
    konfig_datei = tmp_path / "config.yaml"
    konfig_datei.write_text(
        "kostenstellen: []\nzeitraum:\n  modus: aktuelles_jahr\n"
        "  datum_von: '01.01.2025'\n  datum_bis: '31.12.2025'\n"
        "ausgabe_ordner: '~/Downloads/test'\ndebug_browser: false\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Keine Kostenstellen"):
        konfiguration_laden(konfig_datei)


def test_datum_aktuelles_jahr():
    """Modus 'aktuelles_jahr' gibt 01.01.JJJJ und 31.12.JJJJ zurück."""
    from datetime import date
    von, bis = datum_berechnen({"modus": "aktuelles_jahr", "datum_von": "", "datum_bis": ""})
    jahr = date.today().year
    assert von == f"01.01.{jahr}"
    assert bis == f"31.12.{jahr}"


def test_datum_manuell():
    """Modus 'manuell' gibt die angegebenen Daten unverändert zurück."""
    von, bis = datum_berechnen({
        "modus": "manuell",
        "datum_von": "01.03.2025",
        "datum_bis": "31.03.2025",
    })
    assert von == "01.03.2025"
    assert bis == "31.03.2025"


def test_datum_aktueller_monat():
    """Modus 'aktueller_monat' gibt ersten und letzten Tag des aktuellen Monats zurück."""
    import calendar
    from datetime import date
    von, bis = datum_berechnen({"modus": "aktueller_monat", "datum_von": "", "datum_bis": ""})
    heute = date.today()
    letzter_tag = calendar.monthrange(heute.year, heute.month)[1]
    assert von == f"01.{heute.month:02d}.{heute.year}"
    assert bis == f"{letzter_tag:02d}.{heute.month:02d}.{heute.year}"


def test_datum_vormonat():
    """Modus 'vormonat' gibt ersten und letzten Tag des Vormonats zurück."""
    von, bis = datum_berechnen({"modus": "vormonat", "datum_von": "", "datum_bis": ""})
    assert len(von) == 10 and von[2] == "." and von[5] == "."
    assert len(bis) == 10 and bis[2] == "." and bis[5] == "."


def test_datum_ungültiger_modus():
    """Unbekannter Modus wirft einen klaren Fehler."""
    with pytest.raises(ValueError, match="Unbekannter Zeitraum-Modus"):
        datum_berechnen({"modus": "quatsch", "datum_von": "", "datum_bis": ""})
