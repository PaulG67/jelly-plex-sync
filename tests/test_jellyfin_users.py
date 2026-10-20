from jellyplexsync.jellyfin import JellyfinClient


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


def test_users_falls_back_to_me_on_401(monkeypatch):
    client = JellyfinClient("http://jellyfin", "token", 10, True)
    calls = {"n": 0}

    def fake_get(path, params=None):
        calls["n"] += 1
        if path == "/Users":
            raise RuntimeError("401 Unauthorized")
        if path == "/Users/Me":
            return {"Id": "abc", "Name": "Paul"}
        raise AssertionError(path)

    monkeypatch.setattr(client, "_get", fake_get)
    users = client.users()
    assert users == [{"id": "abc", "name": "Paul"}]
    assert calls["n"] == 2
