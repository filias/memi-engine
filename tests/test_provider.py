"""Tests for CategoryProvider: instance isolation and the default details panel."""

import pytest

from memi_engine import CategoryProvider, images


class Animals(CategoryProvider):
    key = "nature:animals"
    items = ["Lion", "Tiger"]
    filters = {"size": {"big": ["Lion"]}}
    footers = ["wiki"]


def test_instances_do_not_share_mutable_containers():
    a, b = Animals(), Animals()
    a.items.append("Bear")
    a.footers.append("extra")
    a.filters["size"] = {}
    assert b.items == ["Lion", "Tiger"]
    assert b.footers == ["wiki"]
    assert b.filters == {"size": {"big": ["Lion"]}}


def test_base_class_defaults_not_mutated():
    p = CategoryProvider()
    p.items.append("x")
    p.footers.append("y")
    # The class-level defaults must stay empty.
    assert CategoryProvider.items == []
    assert CategoryProvider.footers == []


# --- Default details panel: the card's Wikipedia article ---


@pytest.fixture(autouse=True)
def details_lang():
    """No panel language unless a test sets one; restore it afterwards."""
    saved = images._DETAILS_LANG
    images.set_details_lang(None)
    yield
    images._DETAILS_LANG = saved


class Places(CategoryProvider):
    key = "places"
    items = ["Belém Tower"]
    map_zoom = 16

    def get_image(self, item):
        return {"image": "x.jpg", "url": "https://pt.wikipedia.org/wiki/Torre_de_Bel%C3%A9m"}


def _article(monkeypatch, intro, coords):
    seen = []

    def fake(title, lang=None):
        seen.append((title, lang))
        return {"intro": intro, "coords": coords}

    monkeypatch.setattr(images, "get_wikipedia_article", fake)
    return seen


def test_details_follow_the_know_more_article(monkeypatch):
    seen = _article(monkeypatch, "A tower.", (38.6916, -9.2160))
    assert Places().get_details("Belém Tower") == {
        "text": "A tower.",
        "map": {"lat": 38.6916, "lon": -9.2160, "zoom": 16},
    }
    assert seen == [("Torre de Belém", "pt")]


def test_no_map_unless_the_category_asks(monkeypatch):
    _article(monkeypatch, "A tower.", (38.6916, -9.2160))

    class Food(Places):
        map_zoom = None

    assert Food().get_details("Belém Tower") == {"text": "A tower."}


def test_coordinates_outside_bounds_get_no_map(monkeypatch):
    _article(monkeypatch, "A river.", (54.36, 18.95))  # the Vistula's mouth

    class Green(Places):
        map_bounds = ((49.96, 50.13), (19.79, 20.22))

    assert Green().get_details("Belém Tower") == {"text": "A river."}


def test_no_details_without_a_wikipedia_link(monkeypatch):
    seen = _article(monkeypatch, "Never used.", None)

    class Logos(Places):
        def get_image(self, item):
            return {"image": "x.png", "url": "https://commons.wikimedia.org/wiki/File:X.png"}

    assert Logos().get_details("Belém Tower") is None
    assert seen == []


def test_wikipedia_title_can_be_overridden(monkeypatch):
    seen = _article(monkeypatch, "A district.", None)

    class Districts(Places):
        def get_image(self, item):
            return {"image": "map.svg"}

        def get_wikipedia_title(self, item):
            return ("pt", f"Distrito de {item}")

    assert Districts().get_details("Lisboa") == {"text": "A district."}
    assert seen == [("Distrito de Lisboa", "pt")]


def test_failed_article_lookup_gives_no_details(monkeypatch):
    monkeypatch.setattr(images, "get_wikipedia_article", lambda title, lang=None: None)
    assert Places().get_details("Belém Tower") is None


def test_details_switch_to_the_games_language(monkeypatch):
    seen = _article(monkeypatch, "Uma torre.", None)
    links = []

    def langlink(title, from_lang, to_lang):
        links.append((title, from_lang, to_lang))
        return "Belém Tower"

    monkeypatch.setattr(images, "wikipedia_langlink", langlink)
    images.set_details_lang("en-GB")
    Places().get_details("Belém Tower")
    assert links == [("Torre de Belém", "pt", "en")]
    assert seen == [("Belém Tower", "en")]


def test_details_keep_the_linked_edition_without_a_counterpart(monkeypatch):
    seen = _article(monkeypatch, "Uma torre.", None)
    monkeypatch.setattr(images, "wikipedia_langlink", lambda *a: None)
    images.set_details_lang("sk")
    assert Places().get_details("Belém Tower") == {"text": "Uma torre."}
    assert seen == [("Torre de Belém", "pt")]
