from pathlib import Path

from jellyplexsync.report import ReportAction, ReportStore


def test_report_store_roundtrip(tmp_path: Path):
    store = ReportStore(tmp_path / "last-report.json")
    report = store.begin(dry_run=True)
    report.actions.append(
        ReportAction(
            direction="plex->jellyfin",
            title="Dune",
            kind="movie",
            library="Movies",
            reason="mark watched",
            source_server="plex",
            dest_server="jellyfin",
            source_played=True,
            dest_played=False,
            source_position=0,
            dest_position=0,
            dry_run=True,
            applied=False,
            user="paul",
        )
    )
    store.finish(report, {"updated_jellyfin": 1, "skipped": 0})
    latest = store.latest()
    assert latest["dry_run"] is True
    assert latest["actions"][0]["title"] == "Dune"
    assert latest["stats"]["updated_jellyfin"] == 1
