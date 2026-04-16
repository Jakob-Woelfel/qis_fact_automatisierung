"""
browser.py
----------
Startet und beendet den Playwright-Browser für den QIS-Export.

Verwendung:
    from src.browser import browser_starten, browser_beenden

    playwright, browser, seite = browser_starten(download_ordner=Path("~/Downloads/qis"))
    # ... Seite verwenden ...
    browser_beenden(playwright, browser)
"""
from pathlib import Path

from playwright.sync_api import Browser, Page, Playwright, sync_playwright


def browser_starten(
    download_ordner: Path,
    debug: bool = False,
) -> tuple[Playwright, Browser, Page]:
    """Startet einen Chromium-Browser und gibt Playwright, Browser und Seite zurück.

    Parameter
    ---------
    download_ordner : Path
        Ordner, in den heruntergeladene Dateien gespeichert werden.
        Wird automatisch erstellt falls nicht vorhanden.
    debug : bool
        False (Standard): Browser läuft unsichtbar im Hintergrund.
        True: Browser-Fenster wird angezeigt (für Fehlersuche).

    Rückgabe
    --------
    tuple[Playwright, Browser, Page]
        playwright  – Playwright-Instanz (zum Beenden benötigt)
        browser     – Browser-Instanz
        seite       – Geöffnete Browser-Seite
    """
    download_ordner = download_ordner.expanduser()
    download_ordner.mkdir(parents=True, exist_ok=True)

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=not debug)
    kontext = browser.new_context(accept_downloads=True)
    seite = kontext.new_page()

    return playwright, browser, seite


def browser_beenden(playwright: Playwright, browser: Browser) -> None:
    """Schließt Browser und Playwright-Instanz sauber.

    Wird auch im Fehlerfall aufgerufen (try/finally in main.py).
    """
    try:
        browser.close()
    finally:
        playwright.stop()
