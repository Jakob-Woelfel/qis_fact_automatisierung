"""
qis.py
------
Automatisiert alle Interaktionen mit dem QIS-Portal der Universität Bayreuth.

Enthält Funktionen für Login, Navigation und den CSV-Download pro Kostenstelle.
Alle Selektoren sind im Dict LOC gebündelt – bei QIS-Layout-Änderungen
nur dort anpassen.

Hinweis zu Selektoren
---------------------
Die absoluten XPaths aus der ursprünglichen Selenium-Version wurden übernommen.
Robustere Selektoren (ID, name-Attribut, Linktext) sollten mit VPN-Zugang
geprüft und hier eingetragen werden. Anleitung:
  1. debug_browser: true in config.yaml setzen
  2. Rechtsklick auf Element → "Untersuchen"
  3. Stabiles Attribut (id, name, aria-label) notieren
  4. LOC-Eintrag aktualisieren
"""
import logging
from pathlib import Path

from playwright.sync_api import Page

logger = logging.getLogger("qis")

# ── Zentrale Selektoren ────────────────────────────────────────────────────
# Bei Änderungen am QIS-Layout nur hier anpassen.
LOC = {
    # Login-Seite
    "benutzername":         "#asdf",
    "passwort":             "#fdsa",
    "login_button":         "input[type='submit']",

    # Navigation (nach Login) – ggf. mit VPN auf robustere Selektoren prüfen
    "finanzberichte":       "//*[@id='wrapper']/div[4]/a[3]",
    "einzelbuchungen":      "//*[@id='makronavigation']/ul/li[2]/a",

    # Suchformular – Kostenstellen-Dropdown
    "kostenstelle_select":  "xpath=//*[@id='wrapper']/div[6]/div[2]/form/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td[2]/table/tbody/tr[1]/td/table/tbody/tr[2]/td[2]/select",

    # Datumsfelder: Von
    "monat_von":            "xpath=//*[@id='wrapper']/div[6]/div[2]/form/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td/table/tbody/tr[2]/td[2]/table/tbody/tr[1]/td[3]/select",
    # Tag- und Jahr-Felder mit VPN ermitteln und hier eintragen:
    "tag_von":              "xpath=//*[@id='wrapper']/div[6]/div[2]/form/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td/table/tbody/tr[2]/td[2]/table/tbody/tr[1]/td[2]/select",
    
    "jahr_von":             "xpath=//*[@id='wrapper']/div[6]/div[2]/form/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td/table/tbody/tr[2]/td[2]/table/tbody/tr[1]/td[4]/input",

    # Datumsfelder: Bis
    "monat_bis":            "xpath=//*[@id='wrapper']/div[6]/div[2]/form/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td[3]/select",
    # Tag- und Jahr-Felder mit VPN ermitteln und hier eintragen:
    "tag_bis":              "xpath=//*[@id='wrapper']/div[6]/div[2]/form/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td[2]/select",   
    
    "jahr_bis":             "xpath=//*[@id='wrapper']/div[6]/div[2]/form/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td/table/tbody/tr[2]/td[2]/table/tbody/tr[2]/td[4]/input",

    # Formular abschicken und Download
    "suche_starten":        "xpath=//*[@id='wrapper']/div[6]/div[2]/form/p/input",
    "csv_icon":             "img[alt='Erstelle Bericht als CSV-Datei']",
}

QIS_LOGIN_URL = "https://qis-fsv.uvw.uni-bayreuth.de/rds?state=user&type=0"


def einloggen(seite: Page, benutzername: str, passwort: str) -> None:
    """Öffnet die QIS-Login-Seite und meldet sich an.

    Parameter
    ---------
    seite : Page
        Playwright-Seitenobjekt.
    benutzername : str
        QIS-Benutzername (aus .env: USER_NAME).
    passwort : str
        QIS-Passwort (aus .env: USER_PASSWORD).
    """
    logger.info("Öffne QIS-Login-Seite...")
    seite.goto(QIS_LOGIN_URL)
    seite.locator(LOC["benutzername"]).fill(benutzername)
    seite.locator(LOC["passwort"]).fill(passwort)
    seite.locator(LOC["login_button"]).click()
    logger.info("Login abgeschlossen.")


def zu_einzelbuchungen_navigieren(seite: Page) -> None:
    """Navigiert zur Einzelbuchungen-Maske und wartet bis das Formular geladen ist.

    Kann zwischen mehreren Exporten wiederholt aufgerufen werden.
    """
    seite.locator(LOC["finanzberichte"]).click()
    seite.locator(LOC["einzelbuchungen"]).click()
    seite.locator(LOC["kostenstelle_select"]).wait_for()
    logger.debug("Einzelbuchungen-Maske geladen.")


def _datum_felder_setzen(
    seite: Page,
    datum: str,
    tag_loc: str,
    monat_loc: str,
    jahr_loc: str,
) -> None:
    """Befüllt Tag-, Monat- und Jahr-Felder für ein Datum.

    Parameter
    ---------
    datum : str
        Datum im Format TT.MM.JJJJ.
    tag_loc, monat_loc, jahr_loc : str
        Selektoren für die drei Felder. Leere Selektoren werden übersprungen.
    """
    tag, monat, jahr = datum.split(".")

    if tag_loc:
        seite.locator(tag_loc).select_option(str(int(tag)))
    seite.locator(monat_loc).select_option(str(int(monat)))
    if jahr_loc:
        feld = seite.locator(jahr_loc)
        feld.fill("")
        feld.fill(jahr)


def buchungen_exportieren(
    seite: Page,
    kostenstelle: str,
    datum_von: str,
    datum_bis: str,
    download_ordner: Path,
) -> Path | None:
    """Führt Abfrage und CSV-Download für eine Kostenstelle durch.

    Erwartet dass die Einzelbuchungen-Maske bereits geladen ist
    (vorher `zu_einzelbuchungen_navigieren` aufrufen).

    Parameter
    ---------
    seite : Page
        Playwright-Seitenobjekt.
    kostenstelle : str
        Kostenstellen-Wert aus dem Dropdown (z.B. "P00422371").
    datum_von : str
        Startdatum im Format TT.MM.JJJJ.
    datum_bis : str
        Enddatum im Format TT.MM.JJJJ.
    download_ordner : Path
        Ordner für die heruntergeladene CSV-Datei.

    Rückgabe
    --------
    Path | None
        Pfad zur heruntergeladenen Datei, oder None bei Fehler.
    """
    # Kostenstelle auswählen und Label auslesen
    dropdown = seite.locator(LOC["kostenstelle_select"])
    dropdown.select_option(value=kostenstelle)
    label = dropdown.evaluate(
        "el => el.options[el.selectedIndex].text"
    ).lstrip("- ").strip()
    logger.debug(f"Kostenstelle gewählt: {kostenstelle} ({label})")

    # Datum setzen
    _datum_felder_setzen(
        seite, datum_von,
        LOC["tag_von"], LOC["monat_von"], LOC["jahr_von"],
    )
    _datum_felder_setzen(
        seite, datum_bis,
        LOC["tag_bis"], LOC["monat_bis"], LOC["jahr_bis"],
    )

    # Suche starten
    seite.locator(LOC["suche_starten"]).click()

    # Download abwarten – Playwright wartet automatisch bis der Download beginnt
    with seite.expect_download() as download_info:
        seite.locator(LOC["csv_icon"]).click()

    download = download_info.value
    zieldatei = download_ordner / f"Einzelbuchungen_{kostenstelle}_{datum_von.replace('.', '-')}.csv"
    download.save_as(zieldatei)
    logger.debug(f"Download gespeichert: {zieldatei.name}")

    return zieldatei
