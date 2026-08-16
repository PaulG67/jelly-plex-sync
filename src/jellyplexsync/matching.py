from __future__ import annotations

import os
import re
from pathlib import Path

from jellyplexsync.models import WatchState

PROVIDER_ORDER = ("imdb", "tmdb", "tvdb", "tvrage")


def normalize_provider(key: str, value: str) -> tuple[str, str]:
    key = key.lower().replace("id", "")
    if key in {"imdb", "imdbid"}:
        key = "imdb"
    elif key in {"tmdb", "tmdbid", "themoviedb"}:
        key = "tmdb"
    elif key in {"tvdb", "tvdbid", "thetvdb"}:
        key = "tvdb"
    value = value.strip().lower()
    if key == "imdb" and not value.startswith("tt") and value.isdigit():
        value = f"tt{value}"
    return key, value


def filename_key(path: str | None) -> str | None:
    if not path:
        return None
    name = Path(path.replace("\\", "/")).name
    stem = os.path.splitext(name)[0]
    stem = re.sub(r"[._]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip().lower()
    return stem or None


def build_keys(state: WatchState) -> set[str]:
    keys: set[str] = set()
    for raw_key, raw_value in state.provider_ids.items():
        if not raw_value:
            continue
        key, value = normalize_provider(raw_key, str(raw_value))
        if key in PROVIDER_ORDER:
            keys.add(f"id:{key}:{value}")
            keys.add(f"kind:{state.kind}:id:{key}:{value}")
    file_key = filename_key(state.path)
    if file_key:
        keys.add(f"file:{file_key}")
    title = re.sub(r"\s+", " ", state.title).strip().lower()
    if title:
        keys.add(f"title:{state.kind}:{title}")
    return keys


def index_states(items: list[WatchState]) -> dict[str, WatchState]:
    index: dict[str, WatchState] = {}
    for item in items:
        item.keys = build_keys(item)
        for key in item.keys:
            index.setdefault(key, item)
    return index


def find_match(source: WatchState, dest_index: dict[str, WatchState]) -> WatchState | None:
    ranked: list[str] = []
    for provider in PROVIDER_ORDER:
        ranked.extend(key for key in source.keys if key.startswith(f"id:{provider}:") or key.startswith(f"kind:{source.kind}:id:{provider}:"))
    ranked.extend(key for key in source.keys if key.startswith("file:"))
    ranked.extend(key for key in source.keys if key.startswith("title:"))
    for key in ranked:
        match = dest_index.get(key)
        if match and match.kind == source.kind:
            return match
    return None
