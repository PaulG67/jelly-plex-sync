from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


class StateStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS item_state (
                pair_key TEXT PRIMARY KEY,
                plex_id TEXT,
                jellyfin_id TEXT,
                played INTEGER,
                position_seconds REAL,
                last_played TEXT,
                updated_at TEXT
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS known_items (
                server TEXT,
                item_id TEXT,
                added_at TEXT,
                PRIMARY KEY (server, item_id)
            )
            """
        )
        self.conn.commit()

    def get(self, pair_key: str) -> dict | None:
        row = self.conn.execute(
            "SELECT plex_id, jellyfin_id, played, position_seconds, last_played FROM item_state WHERE pair_key = ?",
            (pair_key,),
        ).fetchone()
        if not row:
            return None
        return {
            "plex_id": row[0],
            "jellyfin_id": row[1],
            "played": bool(row[2]),
            "position_seconds": row[3],
            "last_played": row[4],
        }

    def save(
        self,
        pair_key: str,
        plex_id: str,
        jellyfin_id: str,
        played: bool,
        position_seconds: float,
        last_played: datetime | None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO item_state (pair_key, plex_id, jellyfin_id, played, position_seconds, last_played, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(pair_key) DO UPDATE SET
                plex_id=excluded.plex_id,
                jellyfin_id=excluded.jellyfin_id,
                played=excluded.played,
                position_seconds=excluded.position_seconds,
                last_played=excluded.last_played,
                updated_at=excluded.updated_at
            """,
            (
                pair_key,
                plex_id,
                jellyfin_id,
                int(played),
                position_seconds,
                last_played.isoformat() if last_played else None,
            ),
        )
        self.conn.commit()

    def known(self, server: str, item_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM known_items WHERE server = ? AND item_id = ?",
            (server, item_id),
        ).fetchone()
        return row is not None

    def remember(self, server: str, item_id: str, added_at: datetime | None) -> None:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO known_items (server, item_id, added_at)
            VALUES (?, ?, ?)
            """,
            (server, item_id, added_at.isoformat() if added_at else None),
        )
        self.conn.commit()
