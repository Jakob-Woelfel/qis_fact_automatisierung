import logging
from src.logger import logger_einrichten


def test_log_datei_wird_erstellt(tmp_path):
    """Logger erstellt die Log-Datei im angegebenen Ordner."""
    logger_einrichten(log_ordner=tmp_path)
    log_dateien = list(tmp_path.glob("qis_*.log"))
    assert len(log_dateien) == 1


def test_logger_schreibt_in_datei(tmp_path):
    """Logger schreibt Nachrichten in die Log-Datei."""
    logger_einrichten(log_ordner=tmp_path)
    logging.getLogger("qis").info("Testmeldung")
    log_datei = list(tmp_path.glob("qis_*.log"))[0]
    inhalt = log_datei.read_text(encoding="utf-8")
    assert "Testmeldung" in inhalt


def test_logger_benennt_datei_mit_datum(tmp_path):
    """Log-Dateiname enthält das aktuelle Datum im Format YYYY-MM-DD."""
    from datetime import date
    logger_einrichten(log_ordner=tmp_path)
    log_dateien = list(tmp_path.glob("qis_*.log"))
    assert date.today().strftime("%Y-%m-%d") in log_dateien[0].name
