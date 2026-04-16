"""
logger.py
---------
Richtet das Logging für den QIS-Buchungsimport ein.

Schreibt gleichzeitig ins Terminal und in eine tagesaktuelle Log-Datei.
"""
import logging
from datetime import date
from pathlib import Path


def logger_einrichten(log_ordner: Path = Path("logs")) -> None:
    """Konfiguriert das Logging für die gesamte Anwendung.

    Legt eine Log-Datei im Format qis_YYYY-MM-DD.log an und gibt
    alle Meldungen gleichzeitig im Terminal aus.

    Parameter
    ---------
    log_ordner : Path
        Ordner, in dem die Log-Dateien gespeichert werden.
        Wird automatisch erstellt falls nicht vorhanden.
    """
    log_ordner.mkdir(parents=True, exist_ok=True)

    dateiname = log_ordner / f"qis_{date.today().strftime('%Y-%m-%d')}.log"

    format_string = "[%(asctime)s] %(levelname)-5s %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    logger = logging.getLogger("qis")
    logger.setLevel(logging.DEBUG)

    # Bereits vorhandene Handler entfernen (wichtig bei mehrfachem Aufruf in Tests)
    logger.handlers.clear()

    datei_handler = logging.FileHandler(dateiname, encoding="utf-8")
    datei_handler.setFormatter(logging.Formatter(format_string, datefmt=datefmt))
    logger.addHandler(datei_handler)

    terminal_handler = logging.StreamHandler()
    terminal_handler.setFormatter(logging.Formatter(format_string, datefmt=datefmt))
    logger.addHandler(terminal_handler)
