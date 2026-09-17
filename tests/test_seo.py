"""Tests for per-page search metadata, robots.txt and the sitemap.

The thing being guarded here is that the home page, the about page and each
category landing page are *distinguishable*: same markup, but their own title,
description and canonical. Before this they were one page repeated.
"""

import pytest

from memi_engine import CategoryProvider, MemiConfig, create_app, register, seo


class Monuments(CategoryProvider):
    key = "culture:monuments"
    items = ["Belem Tower", "Jeronimos"]

    def get_image(self, item):
        return {"name": item, "image": f"http://img.test/{item}.png"}


class Food(CategoryProvider):
    key = "culture:food"
    items = ["Pastel de nata"]

    def get_image(self, item):
        return {"name": item, "image": f"http://img.test/{item}.png"}


def make_client(**kwargs):
    register(Monuments())
    register(Food())
    defaults = dict(
        title="memi portugal",
        subtitle="pratica a tua memoria",
        about_html="<p>Um jogo de <b>memoria</b> sobre Portugal.</p>",
    )
    defaults.update(kwargs)
    return create_app(MemiConfig(**defaults)).test_client()


@pytest.fixture
def client():
    return make_client()


def head_of(client, path, **kwargs):
    return client.get(path, **kwargs).data.decode()


# --- Titles and descriptions ---

def test_home_title_pairs_title_and_subtitle(client):
    assert "<title>memi portugal — pratica a tua memoria</title>" in head_of(
        client, "/"
    )


def test_category_page_has_its_own_title(client):
    assert "<title>monuments — memi portugal</title>" in head_of(
        client, "/monuments"
    )


def test_two_category_pages_do_not_share_metadata(client):
    monuments = head_of(client, "/monuments")
    food = head_of(client, "/food")
    assert "monuments — memi portugal" in monuments
    assert "food — memi portugal" in food
    # The descriptions differ too — a shared one makes them look like
    # near-duplicates in results even when the titles differ.
    assert 'content="monuments' in monuments
    assert 'content="food' in food


def test_about_page_titled_in_the_instance_language(client):
    # config.label_about, not a hardcoded English "About".
    assert "<title>about — memi portugal</title>" in head_of(client, "/about")


def test_description_falls_back_to_about_copy(client):
    # about_html is the one place a game describes itself in its own language.
    assert 'name="description" content="Um jogo de memoria sobre Portugal."' in (
        head_of(client, "/")
    )


def test_description_falls_back_to_title_and_subtitle():
    client = make_client(about_html=None)
    assert (
        'name="description" content="memi portugal — pratica a tua memoria"'
        in head_of(client, "/")
    )


def test_explicit_description_wins():
    client = make_client(description="Jogo de memoria sobre monumentos.")
    assert 'content="Jogo de memoria sobre monumentos."' in head_of(client, "/")


def test_patterns_are_overridable():
    client = make_client(
        category_title="{category} ({count}) — jogo de memoria",
    )
    assert "<title>monuments (2) — jogo de memoria</title>" in head_of(
        client, "/monuments"
    )


# --- Language ---

def test_html_lang_comes_from_config():
    client = make_client(html_lang="pt")
    assert '<html lang="pt">' in head_of(client, "/")
    assert '<html lang="pt">' in head_of(client, "/about")


def test_html_lang_defaults_to_english(client):
    assert '<html lang="en">' in head_of(client, "/")


# --- Canonicals ---

def test_home_canonicalises_to_itself(client):
    assert '<link rel="canonical" href="http://localhost/">' in head_of(client, "/")


def test_dashed_slug_canonicalises_to_the_short_one(client):
    # /culture-monuments and /monuments are the same page; only one is indexed.
    assert '<link rel="canonical" href="http://localhost/monuments">' in head_of(
        client, "/culture-monuments"
    )


def test_query_string_form_canonicalises_to_the_slug(client):
    assert '<link rel="canonical" href="http://localhost/monuments">' in head_of(
        client, "/?cat=culture:monuments"
    )


def test_unknown_cat_does_not_move_the_home_canonical(client):
    assert '<link rel="canonical" href="http://localhost/">' in head_of(
        client, "/?cat=nope:nope"
    )


def test_canonical_follows_the_proxy_headers(client):
    # Caddy terminates HTTPS; without ProxyFix the canonical would be the
    # http://127.0.0.1 inner hop.
    html = head_of(
        client,
        "/monuments",
        headers={"X-Forwarded-Proto": "https", "X-Forwarded-Host": "pt.memi.games"},
    )
    assert '<link rel="canonical" href="https://pt.memi.games/monuments">' in html


def test_site_url_pins_the_origin():
    client = make_client(site_url="https://pt.memi.games")
    html = head_of(client, "/monuments", headers={"X-Forwarded-Host": "evil.test"})
    assert '<link rel="canonical" href="https://pt.memi.games/monuments">' in html


# --- Link previews ---

def test_og_tags_track_the_page(client):
    html = head_of(client, "/food")
    assert '<meta property="og:title" content="food — memi portugal">' in html
    assert '<meta property="og:url" content="http://localhost/food">' in html
    assert '<meta name="twitter:card" content="summary">' in html


def test_og_image_when_configured():
    client = make_client(og_image="https://pt.memi.games/static/card.png")
    html = head_of(client, "/")
    assert (
        '<meta property="og:image" '
        'content="https://pt.memi.games/static/card.png">' in html
    )
    assert '<meta name="twitter:card" content="summary_large_image">' in html


# --- robots.txt and sitemap.xml ---

def test_robots_allows_the_site_and_blocks_the_api(client):
    body = client.get("/robots.txt").data.decode()
    assert "Allow: /" in body
    assert "Disallow: /api/" in body


def test_robots_points_at_the_sitemap(client):
    body = client.get("/robots.txt").data.decode()
    assert "Sitemap: http://localhost/sitemap.xml" in body


def test_robots_is_plain_text(client):
    assert client.get("/robots.txt").mimetype == "text/plain"


def test_sitemap_lists_every_page_worth_indexing(client):
    body = client.get("/sitemap.xml").data.decode()
    for path in ("/", "/about", "/monuments", "/food"):
        assert f"<loc>http://localhost{path}</loc>" in body


def test_sitemap_omits_the_duplicate_dashed_slugs(client):
    # Both slugs work, but submitting both would ask Google to index the
    # same category twice.
    body = client.get("/sitemap.xml").data.decode()
    assert "culture-monuments" not in body


def test_sitemap_is_xml(client):
    assert client.get("/sitemap.xml").mimetype == "application/xml"


def test_sitemap_does_not_shadow_a_category_slug(client):
    # The static rules must win over /<slug>.
    assert client.get("/robots.txt").status_code == 200
    assert client.get("/sitemap.xml").status_code == 200


# --- seo helpers ---

def test_strip_html_unescapes_and_collapses():
    assert seo.strip_html("<p>a &mdash;\n  b</p>") == "a — b"


def test_shorten_prefers_a_sentence_break():
    text = "A whole first sentence that fills the window. " + "x" * 200
    assert seo.shorten(text, 60) == "A whole first sentence that fills the window."


def test_shorten_ignores_a_sentence_break_that_wastes_the_window():
    # Cutting at "Hi." would throw away most of the snippet, so it fills.
    assert seo.shorten("Hi. " + "alpha " * 20, 40).startswith("Hi. alpha")


def test_shorten_does_not_put_an_ellipsis_after_a_full_stop():
    assert not seo.shorten("Short one. " + "x" * 90, 60).endswith(".…")


def test_shorten_falls_back_to_a_word_break():
    assert seo.shorten("alpha beta gamma delta", 12) == "alpha beta…"


def test_shorten_leaves_short_text_alone():
    assert seo.shorten("alpha", 60) == "alpha"


def test_colliding_last_segments_keep_the_dashed_slug():
    keys = ["culture:all", "nature:all", "culture:food"]
    assert seo.canonical_slugs(keys) == {
        "culture:all": "culture-all",
        "nature:all": "nature-all",
        "culture:food": "food",
    }
