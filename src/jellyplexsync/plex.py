from __future__ import annotations

from datetime import datetime, timezone
from xml.etree import ElementTree as ET

from jellyplexsync.http import client as make_client, request
from jellyplexsync.models import WatchState


class PlexClient:
    def __init__(self, baseurl: str, token: str, timeout: int, verify: bool) -> None:
        self.baseurl = baseurl.rstrip("/")
        self.token = token
        self.http = make_client(timeout, verify)

    def _params(self, params: dict | None = None) -> dict:
        merged: dict[str, str] = {}
        if self.token:
            merged["X-Plex-Token"] = self.token
        if params:
            merged.update(params)
        return merged

    def _get(self, path: str, params: dict | None = None) -> ET.Element:
        merged = self._params(params)
        response = request(
            self.http,
            "GET",
            f"{self.baseurl}{path}",
            params=merged,
            headers={"Accept": "application/xml"},
        )
        return ET.fromstring(response.text)

    def _get_ok(self, path: str, params: dict | None = None) -> None:
        request(self.http, "GET", f"{self.baseurl}{path}", params=self._params(params))

    def users(self) -> list[dict[str, str]]:
        users: list[dict[str, str]] = []
        try:
            root = self._get("/accounts")
            for account in root.findall(".//Account"):
                name = account.attrib.get("name") or account.attrib.get("title")
                uid = account.attrib.get("id")
                if name and uid:
                    users.append({"id": uid, "name": name})
        except Exception:
            pass
        if not users:
            root = self._get("/")
            name = root.attrib.get("myPlexUsername") or "plex"
            users.append({"id": "1", "name": name})
        return users

    def libraries(self) -> list[dict[str, str]]:
        root = self._get("/library/sections")
        libs = []
        for directory in root.findall("Directory"):
            libs.append(
                {
                    "key": directory.attrib["key"],
                    "title": directory.attrib.get("title", ""),
                    "type": directory.attrib.get("type", ""),
                }
            )
        return libs

    def items_for_user(self, user_name: str, allowed_libraries: set[str] | None, blocked_libraries: set[str] | None) -> list[WatchState]:
        items: list[WatchState] = []
        for library in self.libraries():
            title = library["title"]
            if allowed_libraries and title.lower() not in allowed_libraries:
                continue
            if blocked_libraries and title.lower() in blocked_libraries:
                continue
            if library["type"] not in {"movie", "show"}:
                continue
            kind = "movie" if library["type"] == "movie" else "episode"
            container_type = "1" if kind == "movie" else "4"
            root = self._get(
                f"/library/sections/{library['key']}/all",
                {"type": container_type, "includeGuids": "1"},
            )
            tag = "Video" if kind == "movie" else "Video"
            for node in root.findall(tag):
                if kind == "episode" and node.attrib.get("type") != "episode":
                    continue
                items.append(self._to_state(node, user_name, title, kind))
        return items

    def _to_state(self, node: ET.Element, user: str, library: str, kind: str) -> WatchState:
        provider_ids: dict[str, str] = {}
        for guid in node.findall("Guid"):
            gid = guid.attrib.get("id", "")
            if "://" in gid:
                provider, value = gid.split("://", 1)
                provider_ids[provider] = value
        path = None
        part = node.find(".//Part")
        if part is not None:
            path = part.attrib.get("file")
        duration_ms = float(node.attrib.get("duration") or 0)
        view_offset = float(node.attrib.get("viewOffset") or 0)
        view_count = int(node.attrib.get("viewCount") or 0)
        last_viewed = node.attrib.get("lastViewedAt")
        added = node.attrib.get("addedAt")
        ratio = (view_offset / duration_ms) if duration_ms else 0.0
        played = ratio >= 0.9 or (view_count > 0 and view_offset == 0)
        title = node.attrib.get("title") or ""
        if kind == "episode":
            show = node.attrib.get("grandparentTitle") or ""
            season = int(node.attrib.get("parentIndex") or 0)
            episode = int(node.attrib.get("index") or 0)
            title = f"{show} S{season:02d}E{episode:02d} {title}".strip()
        return WatchState(
            server="plex",
            user=user,
            item_id=node.attrib["ratingKey"],
            title=title,
            kind=kind,
            library=library,
            path=path,
            provider_ids=provider_ids,
            duration_seconds=duration_ms / 1000,
            position_seconds=view_offset / 1000,
            played=played,
            play_count=view_count,
            last_played=_epoch(last_viewed),
            added_at=_epoch(added),
        )

    def mark_played(self, item_id: str) -> None:
        self._get_ok("/:/scrobble", {"identifier": "com.plexapp.plugins.library", "key": item_id})

    def mark_unplayed(self, item_id: str) -> None:
        self._get_ok("/:/unscrobble", {"identifier": "com.plexapp.plugins.library", "key": item_id})

    def set_progress(self, item_id: str, position_seconds: float, duration_seconds: float) -> None:
        self._get_ok(
            "/:/timeline/",
            {
                "ratingKey": item_id,
                "key": f"/library/metadata/{item_id}",
                "identifier": "com.plexapp.plugins.library",
                "state": "stopped",
                "time": str(int(position_seconds * 1000)),
                "duration": str(int(duration_seconds * 1000)),
            },
        )


def _epoch(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except ValueError:
        return None
