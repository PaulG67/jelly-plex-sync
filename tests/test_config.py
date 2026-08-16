import os

from jellyplexsync.config import Settings, _parse_mapping, get_settings


def test_parse_mapping_empty():
    assert _parse_mapping("") == {}
    assert _parse_mapping(None) == {}
    assert _parse_mapping("Paul=paul") == {"paul": "paul"}


def test_settings_accepts_empty_user_mapping(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("USER_MAPPING", "")
    monkeypatch.setenv("LIBRARY_MAPPING", "")
    monkeypatch.setenv("PLEX_BASEURL", "http://192.168.0.222:32400")
    monkeypatch.setenv("JELLYFIN_BASEURL", "http://192.168.0.224:8096")
    settings = Settings()
    assert settings.user_mapping == {}
    assert settings.library_mapping == {}
    get_settings.cache_clear()
