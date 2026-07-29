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
