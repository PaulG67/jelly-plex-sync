from __future__ import annotations

from datetime import datetime, timezone

from jellyplexsync.http import client as make_client, request
from jellyplexsync.models import WatchState

TICKS_PER_SECOND = 10_000_000


class JellyfinClient:
    def __init__(self, baseurl: str, token: str, timeout: int, verify: bool) -> None:
        self.baseurl = baseurl.rstrip("/")
        self.headers = {
            "X-Emby-Token": token,
            "X-Emby-Authorization": 'MediaBrowser Client="jelly-plex-sync", Device="docker", DeviceId="jelly-plex-sync", Version="1.0.0"',
            "Accept": "application/json",
        }
        self.http = make_client(timeout, verify)

    def _get(self, path: str, params: dict | None = None) -> dict | list:
        response = request(self.http, "GET", f"{self.baseurl}{path}", params=params, headers=self.headers)
        return response.json()

    def _post(self, path: str, json: dict | None = None, params: dict | None = None) -> None:
        request(self.http, "POST", f"{self.baseurl}{path}", json=json, params=params, headers=self.headers)

    def users(self) -> list[dict[str, str]]:
        data = self._get("/Users")
        return [{"id": user["Id"], "name": user["Name"]} for user in data if not user.get("Policy", {}).get("IsDisabled")]

    def items_for_user(self, user_id: str, user_name: str, allowed_libraries: set[str] | None, blocked_libraries: set[str] | None) -> list[WatchState]:
        views = self._get(f"/Users/{user_id}/Views").get("Items", [])
        items: list[WatchState] = []
        for view in views:
            title = view.get("Name", "")
            if allowed_libraries and title.lower() not in allowed_libraries:
                continue
            if blocked_libraries and title.lower() in blocked_libraries:
                continue
            page_start = 0
            while True:
                page = self._get(
                    f"/Users/{user_id}/Items",
                    {
                        "ParentId": view["Id"],
                        "Recursive": "true",
                        "IncludeItemTypes": "Movie,Episode",
                        "Fields": "ProviderIds,Path,MediaSources,UserData,RunTimeTicks,DateCreated",
                        "StartIndex": str(page_start),
                        "Limit": "500",
                    },
                )
                chunk = page.get("Items", [])
                for node in chunk:
                    items.append(self._to_state(node, user_name, title))
                page_start += len(chunk)
                if page_start >= int(page.get("TotalRecordCount") or 0) or not chunk:
                    break
        return items

    def _to_state(self, node: dict, user: str, library: str) -> WatchState:
        userdata = node.get("UserData") or {}
        runtime = float(node.get("RunTimeTicks") or 0) / TICKS_PER_SECOND
        position = float(userdata.get("PlaybackPositionTicks") or 0) / TICKS_PER_SECOND
        last_played = _iso(userdata.get("LastPlayedDate"))
        added = _iso(node.get("DateCreated"))
        kind = "movie" if node.get("Type") == "Movie" else "episode"
        title = node.get("Name") or ""
        if kind == "episode" and node.get("SeriesName"):
            title = f"{node['SeriesName']} S{node.get('ParentIndexNumber', 0):02d}E{node.get('IndexNumber', 0):02d} {title}"
        providers = {str(k): str(v) for k, v in (node.get("ProviderIds") or {}).items() if v}
        return WatchState(
            server="jellyfin",
            user=user,
            item_id=node["Id"],
            title=title,
            kind=kind,
            library=library,
            path=node.get("Path"),
            provider_ids=providers,
            duration_seconds=runtime,
            position_seconds=position,
            played=bool(userdata.get("Played")),
            play_count=int(userdata.get("PlayCount") or 0),
            last_played=last_played,
            added_at=added,
        )

    def apply(self, user_id: str, item: WatchState, played: bool, position_seconds: float) -> None:
        payload = {
            "PlaybackPositionTicks": int(max(0, position_seconds) * TICKS_PER_SECOND),
            "Played": played,
            "PlayCount": max(item.play_count, 1 if played or position_seconds > 0 else 0),
            "LastPlayedDate": (item.last_played or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%S.0000000Z"),
        }
        self._post(f"/Users/{user_id}/Items/{item.item_id}/UserData", json=payload)


def _iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
