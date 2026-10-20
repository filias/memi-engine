"""A game played in a second language (MemiConfig.languages)."""

import pytest

from memi_engine import CategoryProvider, MemiConfig, create_app, register
from memi_engine.menu import build_menu


class Animals(CategoryProvider):
    key = "natureza:animais"
    items = ["Golfinho-roaz", "Lince-ibérico"]
    override_name = True
    translations = {"en": {"Golfinho-roaz": "Bottlenose dolphin", "rei": "king"}}

    def get_image(self, item):
        return {"name": item, "image": f"http://img.test/{item}.png"}

    def get_tag(self, item):
        return "rei"


def _config(**extra):
    return MemiConfig(
        title="memi portugal",
        subtitle="pratica a tua memória",
        html_lang="pt",
        label_about="sobre",
        label_pick_category="escolhe uma categoria",
        category_labels={},
        languages={
            "en": {
                "subtitle": "practise your memory",
                "label_about": "about",
                "label_pick_category": "pick a category",
                "category_labels": {"natureza": "nature", "animais": "animals"},
            }
        },
        **extra,
    )


@pytest.fixture
def client():
    register(Animals())
    return create_app(_config()).test_client()


def test_own_language_at_root(client):
    html = client.get("/").get_data(as_text=True)
    assert '<html lang="pt">' in html
    assert "escolhe uma categoria" in html
    assert ">natureza</button>" in html


def test_other_language_under_its_prefix(client):
    html = client.get("/en/").get_data(as_text=True)
    assert '<html lang="en">' in html
    assert "practise your memory" in html
    assert "pick a category" in html
    # Menu shows the translation; the group is still looked up by its segment.
    assert "toggleSubmenu(\"natureza\")" in html and ">nature</button>" in html
    assert 'href="/en/about"' in html
    assert 'var PATH_PREFIX = "/en"' in html
    assert 'var GAME_LANG = "en"' in html


def test_bare_language_prefix_redirects(client):
    resp = client.get("/en")
    assert resp.status_code in (301, 302, 308)
    assert resp.headers["Location"].endswith("/en/")


def test_switch_links_this_page_in_each_language(client):
    html = client.get("/animais").get_data(as_text=True)
    assert 'href="/en/animais"' in html
    assert 'aria-current="true">pt<' in html
    html = client.get("/en/animais").get_data(as_text=True)
    assert 'href="/animais"' in html
    assert 'aria-current="true">en<' in html


def test_hreflang_alternates_and_canonical(client):
    html = client.get("/en/animais").get_data(as_text=True)
    assert '<link rel="canonical" href="http://localhost/en/animais">' in html
    assert 'hreflang="pt" href="http://localhost/animais"' in html
    assert 'hreflang="en" href="http://localhost/en/animais"' in html


def test_category_page_heading_and_contents_translated(client):
    html = client.get("/en/animais").get_data(as_text=True)
    assert "<h2>animals</h2>" in html
    assert "Bottlenose dolphin" in html
    # Untranslated items show as they are.
    assert "Lince-ibérico" in html


def test_about_in_other_language(client):
    html = client.get("/en/about").get_data(as_text=True)
    assert '<html lang="en">' in html
    assert 'href="/en/"' in html


def test_api_translates_answer_and_tag(client):
    seen = "Lince-ibérico"
    url = f"/api/random?cats=natureza:animais&seen={seen}&lang=en"
    data = client.get(url).get_json()
    assert data["name"] == "Bottlenose dolphin"
    assert data["tag"] == "king"
    assert data["item"] == "Golfinho-roaz"  # the key stays the same


def test_api_own_language_untouched(client):
    data = client.get("/api/random?cats=natureza:animais&seen=Lince-ibérico").get_json()
    assert data["name"] == "Golfinho-roaz"
    assert data["tag"] == "rei"


def test_api_unknown_language_is_own_language(client):
    url = "/api/random?cats=natureza:animais&seen=Lince-ibérico&lang=xx"
    data = client.get(url).get_json()
    assert data["name"] == "Golfinho-roaz"


def test_chosen_language_is_remembered_on_own_pages(client):
    client.set_cookie("memi-lang", "en")
    resp = client.get("/animais")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/en/animais")
    # An English link stays English; ?cat= links are left alone.
    assert client.get("/en/animais").status_code == 200
    assert client.get("/?cat=natureza:animais").status_code == 200


def test_sitemap_lists_every_language(client):
    xml = client.get("/sitemap.xml").get_data(as_text=True)
    for path in ("/", "/about", "/animais", "/en/", "/en/about", "/en/animais"):
        assert f"<loc>http://localhost{path}</loc>" in xml


def test_single_language_game_has_no_switch():
    register(Animals())
    html = create_app(MemiConfig()).test_client().get("/").get_data(as_text=True)
    assert "lang-switch" not in html
    assert 'rel="alternate"' not in html


def test_unknown_override_field_is_rejected():
    with pytest.raises(ValueError):
        config = MemiConfig(html_lang="pt", languages={"en": {"not_a_field": 1}})
        config.for_language("en")


def test_menu_labels_keep_segment_and_add_text():
    register(Animals())
    top, subs = build_menu({"natureza": "nature", "animais": "animals"})
    assert top == [{"label": "natureza", "has_submenu": True, "text": "nature"}]
    assert subs["natureza"][0]["label"] == "animais"
    assert subs["natureza"][0]["text"] == "animals"


def test_details_panel_follows_the_request_language():
    from memi_engine import images

    class Described(Animals):
        def get_details(self, item):
            return {"text": images.details_lang() or "-"}

    register(Described())
    client = create_app(_config(layout="enriched")).test_client()
    url = "/api/random?cats=natureza:animais&seen=Lince-ibérico"
    assert client.get(url + "&lang=en").get_json()["details"]["text"] == "en"
    assert client.get(url).get_json()["details"]["text"] == "pt"
    # Nothing leaks into the next request.
    assert images.details_lang() == "pt"
