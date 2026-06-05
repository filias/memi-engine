"""Tests for memi_engine.images, with the network mocked out."""

import pytest

from memi_engine import images


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


@pytest.fixture
def mock_get(monkeypatch):
    """Patch images.requests.get; tests push canned responses and read calls."""
    calls = []
    box = {"response": FakeResponse({})}

    def fake_get(url, **kwargs):
        calls.append({"url": url, **kwargs})
        return box["response"]

    monkeypatch.setattr(images.requests, "get", fake_get)
    box["calls"] = calls
    return box


@pytest.fixture(autouse=True)
def reset_state():
    """Clear the image cache and restore the default Wikipedia language."""
    images._cache.clear()
    saved = images._WIKIPEDIA_LANG
    yield
    images._cache.clear()
    images.set_wikipedia_lang(saved)


_PAGE = {
    "query": {"pages": {"1": {"title": "Lion", "thumbnail": {"source": "http://img/lion.jpg"}}}}
}


def test_wikipedia_image_success(mock_get):
    mock_get["response"] = FakeResponse(_PAGE)
    result = images.get_wikipedia_image("Lion")
    assert result["image"] == "http://img/lion.jpg"
    assert result["url"] == "https://en.wikipedia.org/wiki/Lion"
    assert mock_get["calls"][0]["url"] == "https://en.wikipedia.org/w/api.php"


def test_wikipedia_image_failure_returns_none(mock_get):
    mock_get["response"] = FakeResponse({}, status_code=404)
    assert images.get_wikipedia_image("Nope") is None


def test_wikipedia_lang_is_configurable(mock_get):
    images.set_wikipedia_lang("pt")
    mock_get["response"] = FakeResponse(_PAGE)
    result = images.get_wikipedia_image("Leão")
    assert mock_get["calls"][0]["url"] == "https://pt.wikipedia.org/w/api.php"
    assert result["url"].startswith("https://pt.wikipedia.org/wiki/")


def test_commons_uses_commons_host_regardless_of_lang(mock_get):
    images.set_wikipedia_lang("pt")
    payload = {"query": {"pages": {"1": {"imageinfo": [{"url": "http://c/x.jpg"}]}}}}
    mock_get["response"] = FakeResponse(payload)
    result = images.get_commons_file_image("X.jpg")
    assert result["image"] == "http://c/x.jpg"
    assert mock_get["calls"][0]["url"] == "https://commons.wikimedia.org/w/api.php"


def test_result_is_cached(mock_get):
    mock_get["response"] = FakeResponse(_PAGE)
    images.get_wikipedia_image("Lion")
    images.get_wikipedia_image("Lion")
    assert len(mock_get["calls"]) == 1  # second call served from cache


def test_tmdb_skipped_without_api_key(monkeypatch, mock_get):
    monkeypatch.setattr(images, "TMDB_API_KEY", "")
    assert images.get_tmdb_image("Some Movie") is None
    assert mock_get["calls"] == []  # never hit the network
