from pathlib import Path

from jellyplexsync.credentials import plex_token_from_preferences


def test_reads_plex_token_from_preferences(tmp_path: Path):
    prefs = (
        tmp_path
        / "Library"
        / "Application Support"
        / "Plex Media Server"
        / "Preferences.xml"
    )
    prefs.parent.mkdir(parents=True)
    prefs.write_text('<Preferences PlexOnlineToken="SECRETTOKEN123" />', encoding="utf-8")
    assert plex_token_from_preferences(tmp_path) == "SECRETTOKEN123"
