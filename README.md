# jelly-plex-sync

Synchronisiert **gesehenen Status**, **Resume-Position** (nicht fertig angeschaut) und **neu hinzugefügte Titel** zwischen Plex und Jellyfin. Ziel ist dieselbe Funktion wie [luigi311/JellyPlex-Watched](https://github.com/luigi311/JellyPlex-Watched), aber mit persistentem State, Retries und Last-Write-Wins, damit der Abgleich nicht hin- und herspringt.

## Was wird synchronisiert

- Filme und Episoden als **gesehen** (ab 90 % Fortschritt, konfigurierbar)
- **Wiedergabeposition**, wenn ein Titel nicht fertig ist
- **Neue Medieneinträge**: sobald ein Titel auf einer Seite auftaucht, wird er gematcht und der Watch-Status übernommen
- Richtung: Plex → Jellyfin, Jellyfin → Plex oder beides

Matching erfolgt zuerst über Provider-IDs (IMDb, TMDB, TVDB), danach über den Dateinamen.

## Unraid: Vorlage + Container hinzufügen

Ab Unraid 6.10 gibt es **keine Template-Repositories** mehr in den Docker-Einstellungen. Die Vorlage muss als User-Template auf den USB-Stick. Danach erscheint sie unter **Docker → Container hinzufügen → Vorlage**.

Image: `ghcr.io/paulg67/jelly-plex-sync:latest`

### 1. Vorlage installieren (Unraid-Terminal)

```bash
wget -O /boot/config/plugins/dockerMan/templates-user/my-jelly-plex-sync.xml \
  https://raw.githubusercontent.com/PaulG67/jelly-plex-sync/main/unraid/my-jelly-plex-sync.xml
```

Oder dieselbe Datei per Samba nach `\\TOWER\flash\config\plugins\dockerMan\templates-user\my-jelly-plex-sync.xml` kopieren.

### 2. Container anlegen

1. **Docker** → **Container hinzufügen**
2. Bei **Vorlage** den Eintrag **jelly-plex-sync** wählen
3. **Kein Port** anlegen, nichts in der Firewall/Router freigeben
4. Ausfüllen:
   - **Plex URL** / **Jellyfin URL:** `http://172.17.0.1:32400` und `http://172.17.0.1:8096` (Unraid-Host im Docker-Netz, nicht das Internet)
   - **Plex Appdata:** dein Plex-Ordner, z. B. `/mnt/user/appdata/plex` (read-only) — Token wird lokal aus `Preferences.xml` gelesen
   - **Jellyfin Benutzer:** dein lokaler Jellyfin-Name. **Passwort leer**, wenn der User keins hat
   - **User Mapping** nur wenn die Namen anders sind
5. Appdata: `/mnt/user/appdata/jelly-plex-sync`
6. **Anwenden**

Die App spricht nur Plex und Jellyfin auf demselben Server an. Es gibt keine WebUI und keine Veröffentlichung ins Internet.

Falls Plex den Token aus der Appdata nicht akzeptiert: in Plex unter **Settings → Network** bei *List of IP addresses and networks that are allowed without auth* `172.16.0.0/12` eintragen (nur LAN/Docker, nicht WAN).

In Jellyfin unter **Dashboard → Networking** das Docker-Subnetz zu den LAN-Netzen nehmen.

## Lokaler Zugang (ohne Internet, ohne API-Key)

Plex und Jellyfin brauchen trotzdem eine **lokale Identität**, sonst wissen sie nicht, wessen Verlauf geschrieben werden soll. Die Identität bleibt auf Unraid:

- **Plex:** Token wird aus der gemounteten Appdata gelesen. Nichts eintippen, nichts nach außen.
- **Jellyfin:** Login mit Benutzername (Passwort optional). Kein API-Key im Dashboard nötig.
- Tokens/Passwörter optional nur als Fallback in den erweiterten Feldern.

## Umgebungsvariablen

| Variable | Default | Bedeutung |
| --- | --- | --- |
| `PLEX_BASEURL` | `http://172.17.0.1:32400` | Plex nur über Docker-Host |
| `PLEX_TOKEN` | leer | Optional; sonst aus Plex-Appdata |
| `PLEX_APPDATA` | `/plex` | Mount der Plex-Appdata |
| `JELLYFIN_BASEURL` | `http://172.17.0.1:8096` | Jellyfin nur über Docker-Host |
| `JELLYFIN_USERNAME` | leer | Lokaler User statt API-Key |
| `JELLYFIN_PASSWORD` | leer | Optional |
| `JELLYFIN_TOKEN` | leer | Optionaler API-Key |
| `USER_MAPPING` | leer | `plex=jellyfin` oder JSON |
| `SLEEP_DURATION` | `300` | Intervall in Sekunden |
| `DRY_RUN` | `false` | Nur loggen |
| `SYNC_FROM_PLEX_TO_JELLYFIN` | `true` | |
| `SYNC_FROM_JELLYFIN_TO_PLEX` | `true` | |
| `SYNC_WATCHED` | `true` | |
| `SYNC_PROGRESS` | `true` | Resume-Punkte |
| `SYNC_NEW_ITEMS` | `true` | Neue Titel loggen/einbeziehen |
| `WATCHED_PERCENT` | `90` | Schwelle „gesehen“ |
| `SSL_BYPASS` | `false` | Selbstsignierte Zertifikate |

## Lokal / Docker Compose

```bash
cp .env.example .env
docker compose up -d --build
```

## Stabilität gegenüber jellyplex-watched

- SQLite unter `/data/state.db` merkt sich Paare und zuletzt geschriebenen Stand
- Updates nur wenn die Quelle neuer ist oder der Fortschritt sich deutlich unterscheidet
- HTTP-Retries mit Backoff bei 5xx/Netzwerkfehlern
- Einzelne Titel-Fehler stoppen den Lauf nicht
- Healthcheck über `/data/healthy`
