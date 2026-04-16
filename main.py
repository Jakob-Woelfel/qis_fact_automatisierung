"""
main.py
-------
Einstiegspunkt für den QIS-Buchungsimport.

Lädt die Konfiguration, startet den Browser, exportiert alle
konfigurierten Kostenstellen und verarbeitet sie zu FACT-Excel-Dateien.

Starten:
    python main.py
    oder per Doppelklick auf starten.command
"""
import json
import logging
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from src.browser import browser_beenden, browser_starten
from src.konfiguration import datum_berechnen, konfiguration_laden
from src.logger import logger_einrichten
from src.processor import process_buchungsdatei
from src.qis import buchungen_exportieren, einloggen, zu_einzelbuchungen_navigieren

load_dotenv()

KONFIG_PFAD = Path("config.yaml")
LOG_ORDNER = Path("logs")


def _fortschritt_laden(pfad: Path) -> set[str]:
    """Lädt bereits abgeschlossene Kostenstellen aus der Fortschritts-Datei.

    Ermöglicht das Fortsetzen eines unterbrochenen Exports.
    """
    if pfad.exists():
        return set(json.loads(pfad.read_text(encoding="utf-8")).get("abgeschlossen", []))
    return set()


def _fortschritt_speichern(pfad: Path, abgeschlossen: set[str]) -> None:
    """Speichert die abgeschlossenen Kostenstellen in die Fortschritts-Datei."""
    pfad.write_text(
        json.dumps(
            {"datum": str(date.today()), "abgeschlossen": sorted(abgeschlossen)},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    """Hauptablauf des QIS-Buchungsimports."""

    # 1) Logging einrichten
    logger_einrichten(LOG_ORDNER)
    log = logging.getLogger("qis")

    # 2) Konfiguration laden
    try:
        konfig = konfiguration_laden(KONFIG_PFAD)
    except (FileNotFoundError, ValueError) as fehler:
        print(f"Konfigurationsfehler: {fehler}")
        return

    kostenstellen: list[str] = konfig["kostenstellen"]
    ausgabe_ordner = Path(konfig["ausgabe_ordner"]).expanduser()
    debug = konfig.get("debug_browser", False)

    # 3) Zugangsdaten prüfen
    benutzername = os.getenv("USER_NAME")
    passwort = os.getenv("USER_PASSWORD")
    if not benutzername or not passwort:
        log.error("USER_NAME oder USER_PASSWORD fehlen in der .env-Datei.")
        return

    # 4) Datum berechnen
    datum_von, datum_bis = datum_berechnen(konfig["zeitraum"])
    log.info(f"Zeitraum: {datum_von} bis {datum_bis}")

    # 5) Fortschritt laden – bereits abgeschlossene Kostenstellen überspringen
    fortschritt_pfad = LOG_ORDNER / f"fortschritt_{date.today()}.json"
    abgeschlossen = _fortschritt_laden(fortschritt_pfad)
    ausstehend = [k for k in kostenstellen if k not in abgeschlossen]

    if abgeschlossen:
        log.info(f"Bereits abgeschlossen (übersprungen): {', '.join(sorted(abgeschlossen))}")

    log.info(f"Starte QIS-Export für {len(ausstehend)} Kostenstelle(n).")

    # 6) Browser starten
    playwright, browser, seite = browser_starten(ausgabe_ordner, debug=debug)

    erfolgreich: list[str] = []
    fehlgeschlagen: list[str] = []

    try:
        einloggen(seite, benutzername, passwort)

        for nr, kostenstelle in enumerate(ausstehend, 1):
            log.info(f"[{nr}/{len(ausstehend)}] Exportiere {kostenstelle} ...")
            try:
                zu_einzelbuchungen_navigieren(seite)
                csv_pfad = buchungen_exportieren(
                    seite, kostenstelle, datum_von, datum_bis, ausgabe_ordner
                )
                if csv_pfad:
                    process_buchungsdatei(csv_pfad, ausgabe_ordner)
                    abgeschlossen.add(kostenstelle)
                    _fortschritt_speichern(fortschritt_pfad, abgeschlossen)
                    erfolgreich.append(kostenstelle)
                    log.info(f"OK    {kostenstelle} → {csv_pfad.name}")
                else:
                    fehlgeschlagen.append(kostenstelle)
                    log.warning(f"WARN  {kostenstelle} → kein Download erkannt.")
            except Exception as fehler:
                fehlgeschlagen.append(kostenstelle)
                log.error(f"FEHLER {kostenstelle}: {fehler}")

    finally:
        browser_beenden(playwright, browser)

    # 7) Zusammenfassung
    if fehlgeschlagen:
        log.info(
            f"Fertig: {len(erfolgreich)} erfolgreich, "
            f"{len(fehlgeschlagen)} fehlgeschlagen: {', '.join(fehlgeschlagen)}"
        )
    else:
        log.info(f"Fertig: alle {len(erfolgreich)} Kostenstellen erfolgreich exportiert.")

    # Fortschritts-Datei löschen wenn alles abgeschlossen
    if not fehlgeschlagen and fortschritt_pfad.exists():
        fortschritt_pfad.unlink()


if __name__ == "__main__":
    main()
