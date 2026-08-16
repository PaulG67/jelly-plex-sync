from __future__ import annotations

import logging
import threading
from pathlib import Path

from jellyplexsync.config import Settings
from jellyplexsync.credentials import resolve_jellyfin_token, resolve_plex_token
from jellyplexsync.jellyfin import JellyfinClient
from jellyplexsync.models import WatchState
from jellyplexsync.plex import PlexClient
from jellyplexsync.report import ReportAction, ReportStore
from jellyplexsync.store import StateStore
from jellyplexsync.sync import SyncEngine
from datetime import datetime, timezone

log = logging.getLogger("jellyplexsync")


class SyncRunner:
    def __init__(self, settings: Settings, report_store: ReportStore) -> None:
        self.settings = settings
        self.report_store = report_store
        self._lock = threading.Lock()
        self._running = False
        self._wake = threading.Event()
        self.status = "idle"
        self.last_error: str | None = None

    def request_now(self) -> dict:
        if self._running:
            return {"ok": False, "message": "Sync laeuft bereits"}
        self._wake.set()
        return {"ok": True, "message": "Sync gestartet – Seite aktualisiert sich automatisch"}

    def apply_action(self, action_id: str) -> dict:
        action = self.report_store.get_action(action_id)
        if action is None:
            return {"ok": False, "message": "Eintrag nicht gefunden – bitte Sync erneut ausfuehren"}
        if action.applied:
            return {"ok": False, "message": "Bereits durchgefuehrt"}
        if not action.dest_item_id:
            return {
                "ok": False,
                "message": "Alte Liste ohne IDs. Bitte einmal „Jetzt synchronisieren“, dann erneut versuchen.",
            }
        with self._lock:
            if self._running:
                return {"ok": False, "message": "Vollstaendiger Sync laeuft gerade"}
            self._running = True
        try:
            self._apply_action(action)
            self.report_store.mark_applied(action_id)
            return {"ok": True, "message": f"Durchgefuehrt: {action.title}"}
        except Exception as exc:
            log.exception("Einzel-Apply fehlgeschlagen: %s", action.title)
            return {"ok": False, "message": str(exc)}
        finally:
            self._running = False

    def _clients(self):
        settings = self.settings
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
        return plex, jellyfin

    def _apply_action(self, action: ReportAction) -> None:
        plex, jellyfin = self._clients()
        played = action.target_played
        position = action.target_position
        if action.dest_server == "jellyfin":
            if not action.jellyfin_user_id:
                raise RuntimeError("Keine Jellyfin-User-ID in diesem Eintrag")
            stub = WatchState(
                server="jellyfin",
                user=action.user,
                item_id=action.dest_item_id,
                title=action.title,
                kind=action.kind,
                library=action.library,
                path=None,
                provider_ids={},
                duration_seconds=action.duration_seconds,
                position_seconds=position,
                played=played,
                play_count=1 if played or position > 0 else 0,
                last_played=datetime.now(timezone.utc),
            )
            jellyfin.apply(action.jellyfin_user_id, stub, played, position)
        else:
            if played:
                plex.mark_played(action.dest_item_id)
            elif position > 0:
                plex.set_progress(action.dest_item_id, position, action.duration_seconds or position)
            else:
                raise RuntimeError("Nichts anzuwenden (weder gesehen noch Position)")

        data_dir = Path(self.settings.data_dir)
        store = StateStore(data_dir / "state.db")
        if action.source_server == "plex":
            plex_id, jelly_id = action.source_item_id, action.dest_item_id
        else:
            plex_id, jelly_id = action.dest_item_id, action.source_item_id
        store.save(
            f"{(action.user or 'user').lower()}:{action.kind}:{plex_id}:{jelly_id}",
            plex_id,
            jelly_id,
            played,
            position,
            datetime.now(timezone.utc),
        )
        log.info("Manuell angewendet: %s (%s)", action.title, action.direction)

    def snapshot(self) -> dict:
        report = self.report_store.latest()
        report["runner_status"] = self.status
        report["runner_error"] = self.last_error
        report["interval_seconds"] = self.settings.sleep_duration
        return report

    def run_once(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self.status = "running"
        try:
            self._run_once()
            self.status = "idle"
            self.last_error = None
        except Exception as exc:
            self.status = "error"
            self.last_error = str(exc)
            log.exception("Sync run failed")
            latest = self.report_store.latest()
            if not latest.get("finished_at"):
                report = self.report_store.begin(self.settings.dry_run)
                self.report_store.finish(report, {}, error=str(exc))
        finally:
            self._running = False

    def _run_once(self) -> None:
        settings = self.settings
        data_dir = Path(settings.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        store = StateStore(data_dir / "state.db")
        verify = not settings.ssl_bypass
        plex_token = resolve_plex_token(settings)
        if not plex_token:
            log.warning("Kein Plex-Token gefunden – Sync kann scheitern")
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
        stats = SyncEngine(settings, store, plex, jellyfin, self.report_store).run()
        (data_dir / "healthy").write_text("ok\n", encoding="utf-8")
        log.info("Sync finished: %s", stats)

    def loop(self) -> None:
        while True:
            self.run_once()
            if self.settings.run_only_once:
                return
            self._wake.clear()
            self._wake.wait(timeout=max(30, self.settings.sleep_duration))
