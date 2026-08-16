from __future__ import annotations

import logging
import sys
from pathlib import Path

from jellyplexsync.config import get_settings
from jellyplexsync.report import ReportStore
from jellyplexsync.runner import SyncRunner
from jellyplexsync.web import start_web


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    log = logging.getLogger("jellyplexsync")
    data_dir = Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    report_store = ReportStore(data_dir / "last-report.json")
    runner = SyncRunner(settings, report_store)
    if settings.web_enabled:
        try:
            start_web(runner, settings.web_host, settings.web_port)
        except OSError:
            log.exception(
                "Web-UI konnte Port %s nicht binden. WEB_PORT und Container-Port pruefen.",
                settings.web_port,
            )
            raise
    log.info(
        "jelly-plex-sync starting (interval=%ss, dry_run=%s, web=%s)",
        settings.sleep_duration,
        settings.dry_run,
        f"{settings.web_host}:{settings.web_port}" if settings.web_enabled else "off",
    )
    runner.loop()


if __name__ == "__main__":
    main()
