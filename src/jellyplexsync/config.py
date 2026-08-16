from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_mapping(value: Any) -> dict[str, str]:
    if value is None or value == "":
        return {}
    if isinstance(value, dict):
        return {str(k).strip().lower(): str(v).strip() for k, v in value.items()}
    text = str(value).strip()
    if not text:
        return {}
    if text.startswith("{"):
        data = json.loads(text)
        return {str(k).strip().lower(): str(v).strip() for k, v in data.items()}
    mapping: dict[str, str] = {}
    for pair in text.split(","):
        if "=" not in pair:
            continue
        left, right = pair.split("=", 1)
        mapping[left.strip().lower()] = right.strip()
    return mapping


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    dry_run: bool = False
    log_level: str = "INFO"
    sleep_duration: int = 300
    run_only_once: bool = False
    request_timeout: int = 60
    data_dir: str = "/data"

    plex_baseurl: str = "http://172.17.0.1:32400"
    plex_token: str = ""
    plex_token_file: str = ""
    plex_appdata: str = "/plex"
    jellyfin_baseurl: str = "http://172.17.0.1:8096"
    jellyfin_token: str = ""
    jellyfin_token_file: str = ""
    jellyfin_username: str = ""
    jellyfin_password: str = ""

    user_mapping: dict[str, str] = Field(default_factory=dict)
    library_mapping: dict[str, str] = Field(default_factory=dict)
    whitelist_users: str = ""
    blacklist_users: str = ""
    whitelist_libraries: str = ""
    blacklist_libraries: str = ""

    sync_from_plex_to_jellyfin: bool = True
    sync_from_jellyfin_to_plex: bool = True
    sync_watched: bool = True
    sync_progress: bool = True
    sync_new_items: bool = True

    watched_percent: int = 90
    progress_min_seconds: int = 30
    progress_delta_seconds: int = 10
    ssl_bypass: bool = False

    web_enabled: bool = True
    web_host: str = "0.0.0.0"
    web_port: int = 8787

    @field_validator(
        "dry_run",
        "run_only_once",
        "sync_from_plex_to_jellyfin",
        "sync_from_jellyfin_to_plex",
        "sync_watched",
        "sync_progress",
        "sync_new_items",
        "ssl_bypass",
        "web_enabled",
        mode="before",
    )
    @classmethod
    def coerce_bool(cls, value: Any) -> bool:
        return _parse_bool(value)

    @field_validator("user_mapping", "library_mapping", mode="before")
    @classmethod
    def coerce_mapping(cls, value: Any) -> dict[str, str]:
        return _parse_mapping(value)

    def user_list(self, raw: str) -> set[str]:
        return {part.strip().lower() for part in raw.split(",") if part.strip()}

    def mapped_name(self, name: str) -> str:
        key = name.strip().lower()
        mapped = self.user_mapping.get(key)
        if mapped:
            return mapped.strip().lower()
        inverse = {v.strip().lower(): k for k, v in self.user_mapping.items()}
        return inverse.get(key, key)

    def library_names_match(self, left: str, right: str) -> bool:
        a = left.strip().lower()
        b = right.strip().lower()
        if a == b:
            return True
        mapped = self.library_mapping.get(a, "").strip().lower()
        inverse = {v.strip().lower(): k for k, v in self.library_mapping.items()}
        return mapped == b or inverse.get(a, "") == b


@lru_cache
def get_settings() -> Settings:
    return Settings()
