# QIS Buchungsimport – Automatischer FACT-Export

Dieses Tool exportiert automatisch Einzelbuchungen aus dem QIS-Portal der Universität Bayreuth und erstellt daraus FACT-kompatible Excel-Dateien.

---

## Ersteinrichtung (einmalig, für technische Person)

### Voraussetzungen
- Python 3.10 oder höher
- VPN-Zugang zur Universität Bayreuth (falls außerhalb des Uni-Netzes)

### Schritte

**1. Virtuelle Umgebung erstellen und Abhängigkeiten installieren**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

**2. Zugangsdaten hinterlegen**

Eine Datei `.env` im Projektordner anlegen (kein Leerzeichen um das `=`):
```
USER_NAME=dein_qis_benutzername
USER_PASSWORD=dein_qis_passwort
```

Diese Datei wird nicht ins Git eingecheckt und bleibt lokal.

**3. Starter ausführbar machen (nur einmalig)**
```bash
chmod +x starten.command
```

---

## Monatliche Nutzung

### Schritt 1 – Konfiguration prüfen

`config.yaml` im Texteditor öffnen und bei Bedarf anpassen:

**Kostenstellen aktivieren/deaktivieren:**
- `#` am Zeilenanfang entfernen → Kostenstelle wird abgerufen
- `#` voranstellen → Kostenstelle wird übersprungen

**Zeitraum einstellen** (`modus` anpassen):

| Modus | Bedeutung |
|---|---|
| `aktuelles_jahr` | Gesamtes laufendes Jahr |
| `vormonat` | Automatisch der letzte Monat |
| `aktueller_monat` | Automatisch der aktuelle Monat |
| `manuell` | Eigenes Von/Bis-Datum (Format: TT.MM.JJJJ) |

Bei `manuell` zusätzlich `datum_von` und `datum_bis` eintragen.

**Datei speichern** nach Änderungen.

### Schritt 2 – Export starten

`starten.command` **doppelklicken**. Ein Terminalfenster öffnet sich und zeigt den Fortschritt.

### Schritt 3 – Ergebnis prüfen

Die fertigen FACT-Excel-Dateien liegen in:
```
~/Downloads/qis_downloads/
```

Das Log der letzten Ausführung:
```
logs/qis_DATUM.log
```

---

## Bei einem Fehler mitten im Export

Kein Problem — einfach `starten.command` erneut doppelklicken. Das Skript erkennt welche Kostenstellen bereits erfolgreich exportiert wurden und macht nur bei den fehlgeschlagenen weiter.

---

## Häufige Probleme

| Problem | Lösung |
|---|---|
| „USER_NAME oder USER_PASSWORD fehlen" | `.env`-Datei prüfen oder neu anlegen |
| Browser öffnet sich nicht / kein Download | VPN aktivieren |
| „config.yaml nicht gefunden" | `starten.command` aus dem Projektordner starten, nicht von woanders |
| QIS-Seite sieht anders aus / Selektoren funktionieren nicht | `debug_browser: true` in `config.yaml` setzen, `starten.command` starten, Browser beobachten — Selektoren in `src/qis.py` im Dict `LOC` anpassen |

---

## Projektstruktur (für Entwickler)

```
starten.command      ← Doppelklick-Starter
config.yaml          ← Konfiguration (Kostenstellen, Zeitraum)
main.py              ← Einstiegspunkt
requirements.txt     ← Python-Abhängigkeiten

src/
  browser.py         ← Playwright-Browser-Setup
  qis.py             ← QIS-Login, Navigation, Download
  processor.py       ← CSV → FACT-Excel Transformation
  konfiguration.py   ← Konfig laden, Datum berechnen
  logger.py          ← Logging (Terminal + Datei)

config/
  kostenarten_number_to_new.yaml   ← Kostenarten-Mapping

logs/
  qis_DATUM.log      ← Protokoll der letzten Ausführung
```
