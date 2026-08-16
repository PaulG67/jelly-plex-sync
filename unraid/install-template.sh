#!/bin/bash
# Auf Unraid im Terminal ausführen. Danach: Docker → Container hinzufügen → Vorlage jelly-plex-sync
set -euo pipefail
DEST="/boot/config/plugins/dockerMan/templates-user/my-jelly-plex-sync.xml"
URL="https://raw.githubusercontent.com/PaulG67/jelly-plex-sync/main/unraid/my-jelly-plex-sync.xml"
mkdir -p "$(dirname "$DEST")"
curl -fsSL "$URL" -o "$DEST"
echo "Vorlage installiert: $DEST"
echo "Jetzt in Unraid: Docker → Container hinzufügen → Vorlage: jelly-plex-sync"
