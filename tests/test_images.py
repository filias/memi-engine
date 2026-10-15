"""Tests for memi_engine.images, with the network mocked out."""

import pytest

from memi_engine import images


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise OSError(self.status_code)


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
    images._article_cache.clear()
    images._langlink_cache.clear()
    saved = images._WIKIPEDIA_LANG
    yield
    images._cache.clear()
    images._article_cache.clear()
    images._langlink_cache.clear()
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


# --- Wikipedia articles (details panel) ---


def test_wikipedia_title_from_url():
    assert images.wikipedia_title_from_url(
        "https://pt.wikipedia.org/wiki/Torre_de_Bel%C3%A9m"
    ) == ("pt", "Torre de Belém")
    assert images.wikipedia_title_from_url(
        "https://en.m.wikipedia.org/wiki/Wawel_Castle#History"
    ) == ("en", "Wawel Castle")
    commons = "https://commons.wikimedia.org/wiki/File:X.jpg"
    assert images.wikipedia_title_from_url(commons) is None
    assert images.wikipedia_title_from_url("") is None


def _article_responses(monkeypatch, extract, coords):
    """Fake Wikipedia (``extract``, item Q1) and Wikidata (``coords``) answers."""
    calls = []

    def fake_get(url, **kwargs):
        calls.append({"url": url, **kwargs})
        if "wikidata" in url:
            claims = {}
            if coords:
                value = {"latitude": coords[0], "longitude": coords[1]}
                claims = {"P625": [{"mainsnak": {"datavalue": {"value": value}}}]}
            return FakeResponse({"claims": claims})
        page = {"extract": extract, "pageprops": {"wikibase_item": "Q1"}}
        return FakeResponse({"query": {"pages": {"1": page}}})

    monkeypatch.setattr(images.requests, "get", fake_get)
    return calls


def test_article_has_intro_and_wikidata_coords(monkeypatch):
    calls = _article_responses(monkeypatch, "A tower.\nMore.", (38.69, -9.21))
    article = images.get_wikipedia_article("Torre de Belém", "pt")
    assert article == {"intro": "A tower.", "coords": (38.69, -9.21)}
    assert calls[0]["url"] == "https://pt.wikipedia.org/w/api.php"
    assert calls[1]["params"]["entity"] == "Q1"


def test_article_defaults_to_configured_language(monkeypatch):
    images.set_wikipedia_lang("sk")
    calls = _article_responses(monkeypatch, "Hrad.", None)
    assert images.get_wikipedia_article("Bratislavský hrad")["coords"] is None
    assert calls[0]["url"] == "https://sk.wikipedia.org/w/api.php"


def test_missing_article_is_none(mock_get):
    mock_get["response"] = FakeResponse({"query": {"pages": {"-1": {"missing": ""}}}})
    assert images.get_wikipedia_article("No Such Thing") is None


def test_article_failures_are_not_cached(monkeypatch):
    def boom(*a, **k):
        raise OSError("network down")

    monkeypatch.setattr(images.requests, "get", boom)
    assert images.get_wikipedia_article("Wawel Castle", "en") is None
    assert images._article_cache == {}


def test_article_successes_are_cached(monkeypatch):
    calls = _article_responses(monkeypatch, "A castle.", None)
    images.get_wikipedia_article("Wawel Castle", "en")
    images.get_wikipedia_article("Wawel Castle", "en")
    assert len(calls) == 2  # one Wikipedia + one Wikidata request, once


def test_intro_drops_pronunciation_asides():
    raw = (
        "The Cloth Hall (Polish: Sukiennice, pronounced [sukʲɛˈɲːit͡sɛ]), is a "
        "historic cloth hall.\nSecond paragraph."
    )
    assert images.wikipedia_intro(raw) == "The Cloth Hall is a historic cloth hall."
    nested = (
        "Napoleonka (Polish: [napɔlɛˈɔnka] ; colloquially kremówka (Polish: "
        "[krɛˈmufka] ), is a Polish type of cream pie. It is made of puff pastry."
    )
    intro = images.wikipedia_intro(nested)
    assert intro.startswith("Napoleonka is a Polish type of cream pie.")


def test_intro_drops_other_language_names():
    raw = (
        "Krakus' Mound (in Polish. Kopiec Krakusa), also called Krak's Mound, "
        "is a tumulus."
    )
    assert images.wikipedia_intro(raw) == (
        "Krakus' Mound, also called Krak's Mound, is a tumulus."
    )


def test_intro_drops_english_respellings():
    cases = {
        "Nashville ( NASH-vil) is the capital of Tennessee.":
            "Nashville is the capital of Tennessee.",
        "Yucca ( YUK-ə) is a genus.": "Yucca is a genus.",
        "Castilleja ( kə-STIL-ee-ə or KAS-til-AY-ə), commonly known as paintbrush, "
        "is a genus.": "Castilleja, commonly known as paintbrush, is a genus.",
        "John Huston ( HEW-stən; August 5, 1906 – August 28, 1987) was a director.":
            "John Huston (August 5, 1906 – August 28, 1987) was a director.",
    }
    for raw, clean in cases.items():
        assert images.wikipedia_intro(raw) == clean
    # Hyphenated words in an ordinary aside stay.
    raw = "The war (Franco-Prussian, 1870) ended."
    assert images.wikipedia_intro(raw) == raw


def test_intro_drops_orphaned_separators():
    raw = "Gamelan (;Javanese: ꦒꦩꦼꦭꦤ꧀, romanized: gamelan) is an ensemble."
    assert images.wikipedia_intro(raw) == "Gamelan is an ensemble."


def test_intro_drops_portuguese_asides():
    raw = (
        "O Sporting Clube de Portugal ComC • MHIH • OB (pronúncia em português: "
        "[ˈspɔɾtĩɡ(ɨ) ˈkluβ(ɨ)]), mais conhecido como Sporting, é um clube."
    )
    assert images.wikipedia_intro(raw) == (
        "O Sporting Clube de Portugal, mais conhecido como Sporting, é um clube."
    )
    raw = "Lisboa (pronúncia em português europeu: [liʒˈβoɐ]) é a capital de Portugal."
    assert images.wikipedia_intro(raw) == "Lisboa é a capital de Portugal."
    raw = "O Porto (AFI: [ˈpoɾtu] ( ouvir)) é uma cidade portuguesa."
    assert images.wikipedia_intro(raw) == "O Porto é uma cidade portuguesa."


def test_intro_trims_at_sentences_not_abbreviations():
    raw = "First sentence here. Second one is near St. Mary's altar. " + "Long " * 30
    assert images.wikipedia_intro(raw, limit=80) == (
        "First sentence here. Second one is near St. Mary's altar."
    )
    raw = "Foi rei de Portugal. Filho de D. Afonso Henriques, n. 1154. " + "Longo " * 30
    assert images.wikipedia_intro(raw, limit=80) == (
        "Foi rei de Portugal. Filho de D. Afonso Henriques, n. 1154."
    )


def test_intro_keeps_first_sentence_even_when_long():
    raw = "Word " * 200 + ". Next."
    assert images.wikipedia_intro(raw, limit=50).startswith("Word Word")


def test_langlink_finds_the_other_editions_title(mock_get):
    page = {"langlinks": [{"lang": "pt", "*": "Torre de Belém"}]}
    mock_get["response"] = FakeResponse({"query": {"pages": {"1": page}}})
    assert images.wikipedia_langlink("Belém Tower", "en", "pt") == "Torre de Belém"
    assert mock_get["calls"][0]["params"]["lllang"] == "pt"
    assert images.wikipedia_langlink("Belém Tower", "en", "pt") == "Torre de Belém"
    assert len(mock_get["calls"]) == 1  # cached


def test_langlink_same_language_needs_no_request(mock_get):
    assert images.wikipedia_langlink("Tagus", "en", "en") == "Tagus"
    assert mock_get["calls"] == []


def test_langlink_missing_and_failed(monkeypatch, mock_get):
    mock_get["response"] = FakeResponse({"query": {"pages": {"1": {"title": "X"}}}})
    assert images.wikipedia_langlink("X", "en", "pt") is None

    def boom(*a, **k):
        raise OSError("network down")

    monkeypatch.setattr(images.requests, "get", boom)
    assert images.wikipedia_langlink("Y", "en", "pt") is None
    assert ("Y", "en", "pt") not in images._langlink_cache


def test_details_lang_takes_the_primary_subtag():
    saved = images._DETAILS_LANG
    images.set_details_lang("pt-PT")
    assert images._DETAILS_LANG == "pt"
    images.set_details_lang(None)
    assert images._DETAILS_LANG is None
    images._DETAILS_LANG = saved
