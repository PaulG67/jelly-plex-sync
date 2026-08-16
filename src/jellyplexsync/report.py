from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ReportAction:
    direction: str
    title: str
    kind: str
    library: str
    reason: str
    source_server: str
    dest_server: str
    source_played: bool
    dest_played: bool
    source_position: float
    dest_position: float
    dry_run: bool
    applied: bool
    user: str = ""


@dataclass
class SyncReport:
    started_at: str = field(default_factory=_iso_now)
    finished_at: str | None = None
    dry_run: bool = False
    ok: bool = True
    error: str | None = None
    stats: dict[str, int] = field(default_factory=dict)
    actions: list[ReportAction] = field(default_factory=list)
    new_items: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "dry_run": self.dry_run,
            "ok": self.ok,
            "error": self.error,
            "stats": self.stats,
            "actions": [asdict(a) for a in self.actions],
            "new_items": self.new_items,
        }


class ReportStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._current: SyncReport | None = None

    def begin(self, dry_run: bool) -> SyncReport:
        report = SyncReport(dry_run=dry_run)
        with self._lock:
            self._current = report
        return report

    def finish(self, report: SyncReport, stats: dict[str, int], error: str | None = None) -> None:
        report.finished_at = _iso_now()
        report.stats = stats
        report.ok = error is None
        report.error = error
        with self._lock:
            self._current = report
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")

    def latest(self) -> dict[str, Any]:
        with self._lock:
            if self._current is not None:
                return self._current.to_dict()
        if self.path.is_file():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return {
            "started_at": None,
            "finished_at": None,
            "dry_run": False,
            "ok": True,
            "error": None,
            "stats": {},
            "actions": [],
            "new_items": [],
            "message": "Noch kein Sync-Lauf. Warte auf den ersten Durchgang.",
        }
