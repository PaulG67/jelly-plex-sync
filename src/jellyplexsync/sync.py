from __future__ import annotations

import logging
from datetime import datetime, timezone

from jellyplexsync.config import Settings
from jellyplexsync.matching import find_match, index_states
from jellyplexsync.models import WatchState
from jellyplexsync.store import StateStore

log = logging.getLogger("jellyplexsync")


def _newer(left: datetime | None, right: datetime | None) -> bool:
    if left is None:
        return False
    if right is None:
        return True
    return left > right


def _should_apply(source: WatchState, dest: WatchState, settings: Settings) -> tuple[bool, str]:
    source_played = source.effective_played(settings.watched_percent)
    dest_played = dest.effective_played(settings.watched_percent)

    if source_played and not dest_played:
        if not settings.sync_watched:
            return False, "watched sync disabled"
        if dest.last_played and source.last_played and dest.last_played > source.last_played:
            return False, "destination last_played is newer"
        return True, "mark watched"

    if settings.sync_progress and not source_played and not dest_played:
        if source.position_seconds < settings.progress_min_seconds:
            return False, "source progress too small"
        delta = abs(source.position_seconds - dest.position_seconds)
        if delta < settings.progress_delta_seconds:
            return False, "progress already close"
        if dest.position_seconds > source.position_seconds and _newer(dest.last_played, source.last_played):
            return False, "destination progress is newer"
        return True, "update resume position"

    return False, "no change"


def pair_key(plex_item: WatchState, jelly_item: WatchState, user_key: str) -> str:
    return f"{user_key}:{plex_item.kind}:{sorted(plex_item.keys & jelly_item.keys)[:1] or plex_item.item_id}"


class SyncEngine:
    def __init__(self, settings: Settings, store: StateStore, plex, jellyfin) -> None:
        self.settings = settings
        self.store = store
        self.plex = plex
        self.jellyfin = jellyfin

    def run(self) -> dict[str, int]:
        stats = {"matched": 0, "updated_jellyfin": 0, "updated_plex": 0, "new_items": 0, "skipped": 0, "errors": 0}
        plex_users = self.plex.users()
        jelly_users = {user["name"].lower(): user for user in self.jellyfin.users()}
        allowed_users = self.settings.user_list(self.settings.whitelist_users)
        blocked_users = self.settings.user_list(self.settings.blacklist_users)
        allowed_libs = self.settings.user_list(self.settings.whitelist_libraries) or None
        blocked_libs = self.settings.user_list(self.settings.blacklist_libraries) or None

        for plex_user in plex_users:
            plex_name = plex_user["name"]
            mapped = self.settings.mapped_name(plex_name)
            if allowed_users and mapped not in allowed_users and plex_name.lower() not in allowed_users:
                continue
            if plex_name.lower() in blocked_users or mapped in blocked_users:
                continue
            jelly_user = jelly_users.get(mapped) or jelly_users.get(plex_name.lower())
            if not jelly_user:
                log.warning("No Jellyfin user for Plex user %s (mapped %s)", plex_name, mapped)
                continue

            log.info("Syncing user %s <-> %s", plex_name, jelly_user["name"])
            plex_items = self.plex.items_for_user(plex_name, allowed_libs, blocked_libs)
            jelly_items = self.jellyfin.items_for_user(jelly_user["id"], jelly_user["name"], allowed_libs, blocked_libs)
            plex_index = index_states(plex_items)
            jelly_index = index_states(jelly_items)

            if self.settings.sync_new_items:
                stats["new_items"] += self._remember_new("plex", plex_items)
                stats["new_items"] += self._remember_new("jellyfin", jelly_items)

            if self.settings.sync_from_plex_to_jellyfin:
                self._direction(plex_items, jelly_index, "jellyfin", jelly_user["id"], stats)
            if self.settings.sync_from_jellyfin_to_plex:
                self._direction(jelly_items, plex_index, "plex", None, stats)
        return stats

    def _remember_new(self, server: str, items: list[WatchState]) -> int:
        count = 0
        for item in items:
            if not self.store.known(server, item.item_id):
                count += 1
                log.info("New item on %s: %s", server, item.title)
            self.store.remember(server, item.item_id, item.added_at)
        return count

    def _direction(self, sources: list[WatchState], dest_index: dict[str, WatchState], dest_server: str, jelly_user_id: str | None, stats: dict[str, int]) -> None:
        for source in sources:
            dest = find_match(source, dest_index)
            if not dest:
                stats["skipped"] += 1
                continue
            stats["matched"] += 1
            apply, reason = _should_apply(source, dest, self.settings)
            if not apply:
                stats["skipped"] += 1
                continue
            try:
                self._write(source, dest, dest_server, jelly_user_id, reason)
                if dest_server == "jellyfin":
                    stats["updated_jellyfin"] += 1
                else:
                    stats["updated_plex"] += 1
            except Exception:
                stats["errors"] += 1
                log.exception("Failed updating %s for %s", dest_server, source.title)

    def _write(self, source: WatchState, dest: WatchState, dest_server: str, jelly_user_id: str | None, reason: str) -> None:
        played = source.effective_played(self.settings.watched_percent)
        position = 0.0 if played else source.position_seconds
        log.info("%s -> %s: %s (%s)", source.server, dest_server, dest.title, reason)
        if self.settings.dry_run:
            return
        if dest_server == "jellyfin":
            self.jellyfin.apply(jelly_user_id, dest, played, position)
            plex_item, jelly_item = source if source.server == "plex" else dest, dest if dest.server == "jellyfin" else source
        else:
            if played:
                self.plex.mark_played(dest.item_id)
            elif position > 0:
                self.plex.set_progress(dest.item_id, position, dest.duration_seconds or source.duration_seconds)
            plex_item, jelly_item = dest if dest.server == "plex" else source, source if source.server == "jellyfin" else dest
        self.store.save(
            pair_key(plex_item, jelly_item, source.user.lower()),
            plex_item.item_id,
            jelly_item.item_id,
            played,
            position,
            source.last_played or datetime.now(timezone.utc),
        )
