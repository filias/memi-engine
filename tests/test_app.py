"""Tests for the Flask app: routing, the game loop, and filtering.

Providers here override ``get_image`` with static data so the tests never
hit the network.
"""

import pytest

from memi_engine import CategoryProvider, MemiConfig, create_app, register


class StaticProvider(CategoryProvider):
    key = "demo:items"
    items = ["Alpha", "Beta", "Gamma"]

    def get_image(self, item):
        return {"name": item, "image": f"http://img.test/{item}.png"}


@pytest.fixture
def client():
    register(StaticProvider())
    app = create_app(MemiConfig(title="Test Memi"))
    return app.test_client()


def test_index_ok(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Test Memi" in resp.data


def test_about_ok(client):
    assert client.get("/about").status_code == 200


def test_favicon_is_svg(client):
    resp = client.get("/favicon.svg")
    assert resp.status_code == 200
    assert resp.mimetype == "image/svg+xml"


def test_review_route_removed(client):
    assert client.get("/review").status_code == 404


def test_random_returns_item(client):
    data = client.get("/api/random?cats=demo:items").get_json()
    assert data["item"] in StaticProvider.items
    assert data["image"].startswith("http://img.test/")


def test_unknown_category_400(client):
    assert client.get("/api/random?cats=nope:nope").status_code == 400


def test_all_seen_400(client):
    seen = ",".join(StaticProvider.items)
    resp = client.get(f"/api/random?cats=demo:items&seen={seen}")
    assert resp.status_code == 400


def test_override_name_uses_item_not_article_title():
    class Overriding(CategoryProvider):
        key = "demo:override"
        items = ["Lisbon"]
        override_name = True

        def get_image(self, item):
            return {"name": "Lisbon (Portugal)", "image": "http://img.test/x.png"}

    register(Overriding())
    app = create_app(MemiConfig())
    data = app.test_client().get("/api/random?cats=demo:override").get_json()
    assert data["name"] == "Lisbon"


def test_name_parenthetical_is_stripped(client):
    data = client.get("/api/random?cats=demo:items").get_json()
    assert "(" not in data["name"]


def test_tag_and_style_passthrough():
    class Tagged(CategoryProvider):
        key = "demo:tagged"
        items = ["Lion"]
        tag_style = "scientific"

        def get_image(self, item):
            return {"name": item, "image": "http://img.test/lion.png"}

        def get_tag(self, item):
            return "Panthera leo"

    register(Tagged())
    app = create_app(MemiConfig())
    data = app.test_client().get("/api/random?cats=demo:tagged").get_json()
    assert data["tag"] == "Panthera leo"
    assert data["tag_style"] == "scientific"


def test_filter_narrows_items():
    class Countries(CategoryProvider):
        key = "geo:countries"
        items = ["France", "Spain", "Japan"]
        filters = {"continent": {"europe": ["France", "Spain"], "asia": ["Japan"]}}

        def get_image(self, item):
            return {"name": item, "image": f"http://img.test/{item}.png"}

    register(Countries())
    app = create_app(MemiConfig())
    client = app.test_client()
    # Only Japan is in Asia, so repeated draws must always return Japan.
    for _ in range(5):
        data = client.get("/api/random?cats=geo:countries&continent=asia").get_json()
        assert data["item"] == "Japan"


def test_report_endpoint(client):
    resp = client.post("/api/report", json={"item": "Alpha", "cats": "demo:items"})
    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True}


def test_report_tolerates_non_json_body(client):
    # Must not 500 when the body isn't JSON.
    resp = client.post("/api/report", data="not json")
    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True}


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


# --- Shareable category landing pages ---------------------------------------


def test_cat_query_param_sets_initial_category(client):
    resp = client.get("/?cat=demo:items")
    assert resp.status_code == 200
    assert b'var INITIAL_CATEGORY = "demo:items";' in resp.data


def test_cat_query_param_unknown_is_ignored(client):
    resp = client.get("/?cat=nope:nope")
    assert resp.status_code == 200
    assert b"var INITIAL_CATEGORY = null;" in resp.data


def test_plain_index_has_null_initial_category(client):
    resp = client.get("/")
    assert b"var INITIAL_CATEGORY = null;" in resp.data


def test_slug_landing_resolves_to_key(client):
    # demo:items -> last segment "items" is unique, so /items is the slug.
    resp = client.get("/items")
    assert resp.status_code == 200
    assert b'var INITIAL_CATEGORY = "demo:items";' in resp.data


def test_dashed_full_key_is_always_a_slug(client):
    resp = client.get("/demo-items")
    assert resp.status_code == 200
    assert b'var INITIAL_CATEGORY = "demo:items";' in resp.data


def test_unknown_slug_404(client):
    assert client.get("/nope").status_code == 404


def test_about_wins_over_slug_route(client):
    # The static /about rule must take precedence over /<slug>.
    assert client.get("/about").status_code == 200


def test_default_category_opens_on_home(client):
    # StaticProvider (demo:items) is registered by the fixture; set it default.
    app = create_app(MemiConfig(default_category="demo:items"))
    resp = app.test_client().get("/")
    assert b'var INITIAL_CATEGORY = "demo:items";' in resp.data


def test_default_category_unknown_is_ignored(client):
    app = create_app(MemiConfig(default_category="nope:nope"))
    resp = app.test_client().get("/")
    assert b"var INITIAL_CATEGORY = null;" in resp.data


def test_explicit_cat_overrides_default(client):
    app = create_app(MemiConfig(default_category="demo:items"))
    # No provider for other:thing, so ?cat wins only when valid; here it's
    # invalid, so we fall back to the default rather than to null.
    resp = app.test_client().get("/?cat=bogus")
    assert b'var INITIAL_CATEGORY = "demo:items";' in resp.data


def test_colliding_last_segments_need_the_dashed_slug():
    class Foo(CategoryProvider):
        key = "foo:all"
        items = ["x"]

        def get_image(self, item):
            return {"name": item, "image": "http://img.test/x.png"}

    class Bar(CategoryProvider):
        key = "bar:all"
        items = ["y"]

        def get_image(self, item):
            return {"name": item, "image": "http://img.test/y.png"}

    register(Foo())
    register(Bar())
    client = create_app(MemiConfig()).test_client()
    # Bare "all" is ambiguous -> 404; each dashed full key still resolves.
    assert client.get("/all").status_code == 404
    assert b'"foo:all"' in client.get("/foo-all").data
    assert b'"bar:all"' in client.get("/bar-all").data


# --- Layouts: classic (default) and enriched ---


class Detailed(CategoryProvider):
    key = "demo:detailed"
    items = ["Hevre"]

    def get_image(self, item):
        return {"name": item, "image": "http://img.test/hevre.png"}

    def get_details(self, item):
        return {
            "text": "A bar in an old prayer house.",
            "area": {"name": "Kazimierz", "url": "https://example.test/kazimierz"},
            "map": {"lat": 50.05, "lon": 19.94},
        }


def test_classic_layout_omits_details():
    register(Detailed())
    client = create_app(MemiConfig()).test_client()
    assert "details" not in client.get("/api/random?cats=demo:detailed").get_json()
    page = client.get("/").data.decode()
    assert 'class="layout-classic"' in page
    assert 'id="details"' not in page


def test_enriched_layout_passes_details_through():
    register(Detailed())
    client = create_app(MemiConfig(layout="enriched")).test_client()
    data = client.get("/api/random?cats=demo:detailed").get_json()
    assert data["details"]["area"]["name"] == "Kazimierz"
    assert data["details"]["map"] == {"lat": 50.05, "lon": 19.94}
    page = client.get("/").data.decode()
    assert 'class="layout-enriched"' in page
    assert 'id="details"' in page


def test_enriched_layout_without_details_sends_none(client):
    # StaticProvider keeps the base get_details -> None: no empty key either.
    register(StaticProvider())
    enriched = create_app(MemiConfig(layout="enriched")).test_client()
    assert "details" not in enriched.get("/api/random?cats=demo:items").get_json()


def test_aggregate_delegates_details():
    from memi_engine import AggregateProvider

    class All(AggregateProvider):
        key = "demo:all"

    register(Detailed())
    register(All())
    client = create_app(MemiConfig(layout="enriched")).test_client()
    data = client.get("/api/random?cats=demo:all").get_json()
    assert data["details"]["text"] == "A bar in an old prayer house."


def test_unknown_layout_is_rejected():
    with pytest.raises(ValueError):
        MemiConfig(layout="fancy")


# --- Menu handlers survive quotes in category names ---


def test_apostrophe_in_key_cannot_break_the_onclick():
    import html
    import re

    class Tips(StaticProvider):
        key = "marta's tips"

    class Group(StaticProvider):
        key = "it's:fun"

    register(Tips())
    register(Group())
    page = create_app(MemiConfig()).test_client().get("/").data.decode()
    handlers = [html.unescape(h) for h in re.findall(r"onclick='([^']*)'", page)]
    # Inside the single-quoted attribute the apostrophe is a JSON ' escape,
    # so it can neither close the attribute nor the JS string.
    select = 'selectCategory("marta\\u0027s tips"); this.classList.add("active")'
    assert select in handlers
    assert 'toggleSubmenu("it\\u0027s")' in handlers


def test_enriched_panel_has_a_title_slot_above_the_area():
    register(Detailed())
    client = create_app(MemiConfig(layout="enriched")).test_client()
    page = client.get("/").data.decode()
    assert page.index('id="details-title"') < page.index('id="details-area"')


# --- Audio: speaker button on reveal ---


class Spoken(CategoryProvider):
    key = "demo:spoken"
    items = ["thank you"]

    def get_image(self, item):
        return {"name": "dziękuję", "image": "http://img.test/card.svg"}

    def get_audio(self, item):
        return {
            "text": "dziękuję", "lang": "pl-PL", "src": "/static/audio/dziekuje.mp3"
        }


def test_audio_passes_through_in_any_layout():
    register(Spoken())
    for layout in ("classic", "enriched"):
        client = create_app(MemiConfig(layout=layout)).test_client()
        data = client.get("/api/random?cats=demo:spoken").get_json()
        assert data["audio"] == {
            "text": "dziękuję", "lang": "pl-PL", "src": "/static/audio/dziekuje.mp3"
        }


def test_no_audio_key_without_get_audio(client):
    assert "audio" not in client.get("/api/random?cats=demo:items").get_json()


def test_aggregate_delegates_audio():
    from memi_engine import AggregateProvider

    class All(AggregateProvider):
        key = "demo:all"

    register(Spoken())
    register(All())
    client = create_app(MemiConfig()).test_client()
    data = client.get("/api/random?cats=demo:all").get_json()
    assert data["audio"]["lang"] == "pl-PL"


def test_speaker_button_is_labelled_from_config():
    register(Spoken())
    client = create_app(MemiConfig(label_listen="posłuchaj")).test_client()
    page = client.get("/").data.decode()
    assert 'id="speak-btn"' in page
    assert 'aria-label="posłuchaj"' in page


def test_about_links_are_styled_for_every_theme():
    from pathlib import Path

    import memi_engine

    css = (Path(memi_engine.__file__).parent / "static/css/style.css").read_text()
    assert ".content p a:not(.back-link)," in css and "color: var(--accent);" in css


class Commas(CategoryProvider):
    key = "demo:commas"
    items = ["Pantheon, Rome", "Colosseum"]

    def get_image(self, item):
        return {"name": item, "image": f"http://img.test/{item}.png"}


def test_seen_item_with_a_comma_counts_as_seen():
    register(Commas())
    client = create_app(MemiConfig()).test_client()
    url = "/api/random?cats=demo:commas&seen=Pantheon%2C%20Rome"
    for _ in range(10):
        assert client.get(url).get_json()["item"] == "Colosseum"
    both = url + "&seen=Colosseum"
    assert client.get(both).status_code == 400  # all seen


def test_old_comma_joined_seen_still_works():
    register(Commas())
    client = create_app(MemiConfig()).test_client()
    resp = client.get("/api/random?cats=demo:commas&seen=Colosseum,Other")
    assert resp.get_json()["item"] == "Pantheon, Rome"
