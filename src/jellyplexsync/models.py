from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class WatchState:
    server: str
    user: str
    item_id: str
    title: str
    kind: str
    library: str
    path: str | None
    provider_ids: dict[str, str]
    duration_seconds: float
    position_seconds: float
    played: bool
    play_count: int
    last_played: datetime | None
    added_at: datetime | None = None
    keys: set[str] = field(default_factory=set)

    def progress_ratio(self) -> float:
        if self.duration_seconds <= 0:
            return 1.0 if self.played else 0.0
        return min(1.0, max(0.0, self.position_seconds / self.duration_seconds))

    def effective_played(self, watched_percent: int) -> bool:
        return self.played or self.progress_ratio() * 100 >= watched_percent


@dataclass(slots=True)
class SyncDecision:
    action: str
    source: WatchState
    destination: WatchState
    reason: str
