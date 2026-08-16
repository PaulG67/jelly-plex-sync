from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field, fields
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
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    source_item_id: str = ""
    dest_item_id: str = ""
    jellyfin_user_id: str = ""
    duration_seconds: float = 0.0
    target_played: bool = False
    target_position: float = 0.0


def action_from_dict(data: dict[str, Any]) -> ReportAction:
    allowed = {f.name for f in fields(ReportAction)}
    return ReportAction(**{k: v for k, v in data.items() if k in allowed})


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
        self._persist(report)

    def _persist(self, report: SyncReport) -> None:
        with self._lock:
            self._current = report
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")

    def _load(self) -> SyncReport | None:
        with self._lock:
            if self._current is not None:
                return self._current
        if not self.path.is_file():
            return None
        data = json.loads(self.path.read_text(encoding="utf-8"))
        actions = [action_from_dict(a) for a in data.get("actions", [])]
        report = SyncReport(
            started_at=data.get("started_at") or _iso_now(),
            finished_at=data.get("finished_at"),
            dry_run=bool(data.get("dry_run")),
            ok=bool(data.get("ok", True)),
            error=data.get("error"),
            stats=data.get("stats") or {},
            actions=actions,
            new_items=data.get("new_items") or [],
        )
        with self._lock:
            self._current = report
        return report

    def get_action(self, action_id: str) -> ReportAction | None:
        report = self._load()
        if not report:
            return None
        for action in report.actions:
            if action.id == action_id:
                return action
        return None

    def mark_applied(self, action_id: str) -> bool:
        report = self._load()
        if not report:
            return False
        for action in report.actions:
            if action.id == action_id:
                action.applied = True
                action.dry_run = False
                self._persist(report)
                return True
        return False

    def latest(self) -> dict[str, Any]:
        report = self._load()
        if report is not None:
            return report.to_dict()
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
