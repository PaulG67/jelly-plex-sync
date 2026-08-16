from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

from jellyplexsync.config import Settings, get_settings
from jellyplexsync.jellyfin import JellyfinClient
from jellyplexsync.plex import PlexClient
from jellyplexsync.store import StateStore
from jellyplexsync.sync import SyncEngine


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )


def run_once(settings: Settings) -> None:
    data_dir = Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    store = StateStore(data_dir / "state.db")
    verify = not settings.ssl_bypass
    plex = PlexClient(settings.plex_baseurl, settings.plex_token, settings.request_timeout, verify)
    jellyfin = JellyfinClient(
        settings.jellyfin_baseurl,
        settings.jellyfin_token,
        settings.request_timeout,
        verify,
    )
    stats = SyncEngine(settings, store, plex, jellyfin).run()
    (data_dir / "healthy").write_text("ok\n", encoding="utf-8")
    logging.getLogger("jellyplexsync").info("Sync finished: %s", stats)


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    log = logging.getLogger("jellyplexsync")
    log.info("jelly-plex-sync starting (interval=%ss, dry_run=%s)", settings.sleep_duration, settings.dry_run)
    while True:
        try:
            run_once(settings)
        except Exception:
            log.exception("Sync run failed")
        if settings.run_only_once:
            return
        time.sleep(max(30, settings.sleep_duration))


if __name__ == "__main__":
    main()
