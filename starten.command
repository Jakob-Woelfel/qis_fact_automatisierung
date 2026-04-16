#!/bin/bash
# ────────────────────────────────────────────────────────
# QIS Buchungsimport – Starter
# Doppelklick auf diese Datei startet den Export.
# ────────────────────────────────────────────────────────

# Ins Projektverzeichnis wechseln (unabhängig vom Speicherort der Datei)
cd "$(dirname "$0")"

# Virtuelle Umgebung aktivieren falls vorhanden
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
fi

# Export starten
python main.py

# Fenster offen halten damit das Ergebnis lesbar bleibt
echo ""
echo "────────────────────────────────────"
echo "Fertig. Fenster zum Beenden schließen."
read -r
