from jellyplexsync.matching import build_keys, find_match, index_states
from jellyplexsync.models import WatchState


def _item(server: str, item_id: str, title: str, path: str | None, providers: dict[str, str], kind: str = "movie") -> WatchState:
    state = WatchState(
        server=server,
        user="paul",
        item_id=item_id,
        title=title,
        kind=kind,
        library="Movies",
        path=path,
        provider_ids=providers,
        duration_seconds=6000,
        position_seconds=120,
        played=False,
        play_count=0,
        last_played=None,
    )
    state.keys = build_keys(state)
    return state


def test_match_by_imdb():
    plex = _item("plex", "1", "Dune", r"D:\media\Dune (2021).mkv", {"imdb": "tt1160419"})
    jelly = _item("jellyfin", "abc", "Dune", "/data/movies/Dune 2021.mkv", {"Imdb": "tt1160419"})
    index = index_states([jelly])
    assert find_match(plex, index) is jelly


def test_match_by_filename_when_ids_missing():
    plex = _item("plex", "1", "Other Title", r"/mnt/user/media/The Matrix (1999).mkv", {})
    jelly = _item("jellyfin", "abc", "Matrix", "/media/The Matrix (1999).mkv", {})
    index = index_states([jelly])
    assert find_match(plex, index) is jelly


def test_no_match_across_kinds():
    movie = _item("plex", "1", "Lost", None, {"tmdb": "1"}, kind="movie")
    episode = _item("jellyfin", "abc", "Lost", None, {"tmdb": "1"}, kind="episode")
    index = index_states([episode])
    assert find_match(movie, index) is None
