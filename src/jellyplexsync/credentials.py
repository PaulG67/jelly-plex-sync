from __future__ import annotations

import logging
import re
from pathlib import Path

from jellyplexsync.config import Settings

log = logging.getLogger("jellyplexsync")

PLEX_TOKEN_RE = re.compile(r'PlexOnlineToken="([^"]+)"')


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None


def plex_token_from_preferences(root: Path) -> str | None:
    candidates = [
        root / "Library" / "Application Support" / "Plex Media Server" / "Preferences.xml",
        root / "Plex Media Server" / "Preferences.xml",
        root / "Preferences.xml",
    ]
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve() if path.exists() else path
        if resolved in seen or not path.is_file():
            continue
        seen.add(resolved)
        text = _read_text(path)
        if not text:
            continue
        match = PLEX_TOKEN_RE.search(text)
        if match and match.group(1).strip():
            log.info("Plex-Token aus %s gelesen (Appdata, nur lokal)", path)
            return match.group(1).strip()
    return None


def resolve_plex_token(settings: Settings) -> str:
    if settings.plex_token.strip():
        return settings.plex_token.strip()
    if settings.plex_token_file:
        text = _read_text(Path(settings.plex_token_file))
        if text and text.strip():
            return text.strip()
    if settings.plex_appdata:
        found = plex_token_from_preferences(Path(settings.plex_appdata))
        if found:
            return found
    log.warning("Kein Plex-Token: lokale Anfragen ohne Token (Plex muss LAN ohne Auth erlauben)")
    return ""


def resolve_jellyfin_token(settings: Settings, authenticate) -> str:
    if settings.jellyfin_token.strip():
        return settings.jellyfin_token.strip()
    if settings.jellyfin_token_file:
        text = _read_text(Path(settings.jellyfin_token_file))
        if text and text.strip():
            return text.strip()
    username = settings.jellyfin_username.strip()
    if username:
        token = authenticate(username, settings.jellyfin_password)
        log.info("Jellyfin-Sitzung für lokalen User %s erzeugt (kein API-Key nötig)", username)
        return token
    raise RuntimeError(
        "Jellyfin: API-Key oder JELLYFIN_USERNAME setzen (Passwort darf leer sein, wenn der User keins hat)"
    )
