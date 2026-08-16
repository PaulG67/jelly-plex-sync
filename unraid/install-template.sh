#!/bin/bash
# Unraid Terminal: Vorlage sauber neu installieren
set -euo pipefail
DIR="/boot/config/plugins/dockerMan/templates-user"
URL="https://raw.githubusercontent.com/PaulG67/jelly-plex-sync/main/unraid/my-jelly-plex-sync.xml"
DEST="$DIR/my-jelly-plex-sync.xml"

mkdir -p "$DIR"
# Alte/leere Vorlagen dieses Containers entfernen
rm -f "$DIR"/my-jelly-plex-sync.xml "$DIR"/jelly-plex-sync.xml

curl -fsSL "$URL" -o "$DEST"
# Kurz pruefen, dass Config-Felder wirklich drin sind
COUNT=$(grep -c '<Config ' "$DEST" || true)
if [ "$COUNT" -lt 5 ]; then
  echo "FEHLER: Vorlage hat zu wenige Config-Felder ($COUNT). Download kaputt?"
  head -n 30 "$DEST"
  exit 1
fi

echo "OK: $DEST ($COUNT Config-Felder)"
echo "grep Plex:"
grep 'Name="Plex' "$DEST" || true
echo
echo "Jetzt in Unraid:"
echo "1) Docker-Seite neu laden (F5)"
echo "2) Container hinzufuegen"
echo "3) Vorlage: jelly-plex-sync (User Templates)"
echo "4) Felder wie Plex Appdata muessen sichtbar sein"
echo "5) Name muss jelly-plex-sync und Quelle ghcr.io/... gefuellt sein"
