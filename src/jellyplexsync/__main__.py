from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

from jellyplexsync.config import Settings, get_settings
from jellyplexsync.credentials import resolve_jellyfin_token, resolve_plex_token
from jellyplexsync.jellyfin import JellyfinClient
from jellyplexsync.plex import PlexClient
from jellyplexsync.report import ReportStore
from jellyplexsync.store import StateStore
from jellyplexsync.sync import SyncEngine
from jellyplexsync.web import start_web


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )


def run_once(settings: Settings, report_store: ReportStore) -> None:
    data_dir = Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    store = StateStore(data_dir / "state.db")
    verify = not settings.ssl_bypass
    plex_token = resolve_plex_token(settings)
    jelly_token = resolve_jellyfin_token(
        settings,
        lambda user, password: JellyfinClient.login(
            settings.jellyfin_baseurl, user, password, settings.request_timeout, verify
        ),
    )
    plex = PlexClient(settings.plex_baseurl, plex_token, settings.request_timeout, verify)
    jellyfin = JellyfinClient(
        settings.jellyfin_baseurl,
        jelly_token,
        settings.request_timeout,
        verify,
    )
    stats = SyncEngine(settings, store, plex, jellyfin, report_store).run()
    (data_dir / "healthy").write_text("ok\n", encoding="utf-8")
    logging.getLogger("jellyplexsync").info("Sync finished: %s", stats)


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    log = logging.getLogger("jellyplexsync")
    data_dir = Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    report_store = ReportStore(data_dir / "last-report.json")
    if settings.web_enabled:
        start_web(report_store, settings.web_host, settings.web_port)
    log.info(
        "jelly-plex-sync starting (interval=%ss, dry_run=%s, web=%s)",
        settings.sleep_duration,
        settings.dry_run,
        f"{settings.web_host}:{settings.web_port}" if settings.web_enabled else "off",
    )
    while True:
        try:
            run_once(settings, report_store)
        except Exception:
            log.exception("Sync run failed")
        if settings.run_only_once:
            return
        time.sleep(max(30, settings.sleep_duration))


if __name__ == "__main__":
    main()
