# jelly-plex-sync

Synchronisiert **gesehenen Status**, **Resume-Position** (nicht fertig angeschaut) und **neu hinzugefügte Titel** zwischen Plex und Jellyfin. Ziel ist dieselbe Funktion wie [luigi311/JellyPlex-Watched](https://github.com/luigi311/JellyPlex-Watched), aber mit persistentem State, Retries und Last-Write-Wins, damit der Abgleich nicht hin- und herspringt.

## Was wird synchronisiert

- Filme und Episoden als **gesehen** (ab 90 % Fortschritt, konfigurierbar)
- **Wiedergabeposition**, wenn ein Titel nicht fertig ist
- **Neue Medieneinträge**: sobald ein Titel auf einer Seite auftaucht, wird er gematcht und der Watch-Status übernommen
- Richtung: Plex → Jellyfin, Jellyfin → Plex oder beides

Matching erfolgt zuerst über Provider-IDs (IMDb, TMDB, TVDB), danach über den Dateinamen.

## Unraid einbinden

Das Image wird nach dem ersten Push nach `main` unter `ghcr.io/paulg67/jelly-plex-sync:latest` veröffentlicht.

### Variante A: Template-Repository (empfohlen)

1. Unraid → **Einstellungen → Docker** → **Template Repositories**
2. Diese URL ergänzen:

   `https://github.com/PaulG67/jelly-plex-sync`

3. Speichern
4. Docker → **Add Container** → Template **jelly-plex-sync**
5. Felder ausfüllen:
   - **Plex URL** z. B. `http://192.168.1.10:32400` (LAN-IP, nicht `localhost` aus dem Container)
   - **Plex Token** ([Anleitung](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/))
   - **Jellyfin URL** z. B. `http://192.168.1.10:8096`
   - **Jellyfin API Key** (Dashboard → API Keys)
   - **User Mapping** wenn die Namen anders sind: `PlexName=JellyfinName`
6. Appdata-Pfad belassen: `/mnt/user/appdata/jelly-plex-sync`
7. Beim ersten Mal optional `DRY_RUN=true`, Logs prüfen, danach auf `false`

### Variante B: Image manuell

Repository: `ghcr.io/paulg67/jelly-plex-sync:latest`  
Volume: `/mnt/user/appdata/jelly-plex-sync` → `/data`

Falls das GHCR-Image privat ist: GitHub → Paket → *Change package visibility* auf **Public**, oder in Unraid ein GitHub-Token hinterlegen.

## Tokens

- **Plex:** Der Token bestimmt, wessen Verlauf gelesen und geschrieben wird (in der Regel der Server-Admin).
- **Jellyfin:** Ein API-Key mit Admin-Rechten kann den Status aller gemappten Nutzer setzen. In Jellyfin unter **Dashboard → Networking** das Docker-Subnetz zu den LAN-Netzwerken hinzufügen, sonst liefert die API HTML statt JSON.

## Umgebungsvariablen

| Variable | Default | Bedeutung |
| --- | --- | --- |
| `PLEX_BASEURL` | — | Plex-URL |
| `PLEX_TOKEN` | — | Plex-Token |
| `JELLYFIN_BASEURL` | — | Jellyfin-URL |
| `JELLYFIN_TOKEN` | — | Jellyfin API-Key |
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
