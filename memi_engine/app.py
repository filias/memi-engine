"""Generic Flask app for memi instances.

All category-specific logic lives in CategoryProviders. This module
handles routing, filtering, and the game loop — without knowing
anything about specific categories.
"""

from __future__ import annotations

import logging
import os
import random
import subprocess
from urllib.parse import quote
from xml.sax.saxutils import escape

from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
)
from werkzeug.middleware.proxy_fix import ProxyFix

from memi_engine import images, registry, seo
from memi_engine.config import MemiConfig
from memi_engine.menu import build_menu

_logger = logging.getLogger(__name__)

# Items excluded via the review system
_excluded_items: set[str] = set()


def create_app(config: MemiConfig, instance_static: str | None = None) -> Flask:
    """Create a Flask app for a memi instance.

    Args:
        config: MemiConfig with title, themes, footers, etc.
        instance_static: Path to the instance's static folder (for logos, etc.).
            If provided, files here are served alongside the engine's static files.
    """
    images.set_wikipedia_lang(config.wikipedia_lang)
    images.set_details_lang(config.html_lang)

    engine_dir = os.path.dirname(__file__)
    engine_templates = os.path.join(engine_dir, "templates")
    engine_static = os.path.join(engine_dir, "static")

    # Disable Flask's built-in static handler — we'll handle it ourselves
    app = Flask(
        __name__,
        template_folder=engine_templates,
        static_folder=None,
    )

    # Every memi site runs behind Caddy, which terminates HTTPS and proxies to
    # gunicorn on localhost. Without this the app only ever sees the plain-HTTP
    # inner hop, and would publish canonical and og: URLs on http://127.0.0.1.
    # One hop, and only the two headers that decide the origin.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=0, x_proto=1, x_host=1)

    # Custom static file handler: instance first, then engine
    static_dirs = (
        [instance_static, engine_static] if instance_static else [engine_static]
    )

    @app.route("/static/<path:filename>")
    def static(filename):
        for d in static_dirs:
            if d and os.path.isfile(os.path.join(d, filename)):
                return send_from_directory(d, filename)
        return "Not found", 404

    @app.route("/favicon.svg")
    def favicon():
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
            f'<rect width="64" height="64" rx="14" fill="{config.favicon_color}"/>'
            '<text x="32" y="46" font-family="system-ui,-apple-system,sans-serif" '
            'font-size="40" font-weight="700" text-anchor="middle" fill="#fff" '
            'letter-spacing="-1">m</text>'
            "</svg>"
        )
        return Response(svg, mimetype="image/svg+xml")

    # Detect git version
    if not config.version:
        try:
            config.version = (
                subprocess.check_output(
                    ["git", "rev-parse", "--short", "HEAD"],
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
        except Exception:
            config.version = "dev"

    # Load excluded items
    _load_excluded_items(app)

    # --- Languages ---
    #
    # The game's own language is served at /, each of config.languages under
    # /<code>/. Everything a page shows comes from that language's config.
    base_lang = config.lang
    configs = {base_lang: config}
    for code in config.languages:
        configs[code] = config.for_language(code)
    lang_cookie = "memi-lang"

    def _prefix(lang: str) -> str:
        return "" if lang == base_lang else f"/{lang}"

    def _switch(lang: str, path: str) -> list[dict]:
        """The header's language switch: each language's URL for this page."""
        if len(configs) < 2:
            return []
        return [
            {
                "code": code,
                "href": _prefix(code) + path if path != "/" else _prefix(code) + "/",
                "active": code == lang,
            }
            for code in configs
        ]

    def _preferred_elsewhere(lang: str, path: str):
        """Send a visitor who chose another language to that language's page.

        Only for the game's own language: a link shared in English stays in
        English for whoever opens it.
        """
        chosen = request.cookies.get(lang_cookie)
        if lang == base_lang and chosen in configs and chosen != base_lang:
            return redirect(_prefix(chosen) + path)
        return None

    # --- Routes ---

    def _site_url() -> str:
        """Origin that canonical, og: and sitemap URLs are built on."""
        pinned = config.site_url or os.environ.get("MEMI_SITE_URL")
        return (pinned or request.url_root).rstrip("/")

    def _page(meta: dict, path: str, lang: str = "") -> dict:
        """Head metadata for one page: what it is, and where it really lives.

        ``path`` is the page's path in the game's own language; ``lang`` picks
        which language's URL is canonical. With other languages, ``alternates``
        lists every version for hreflang.
        """
        lang = lang or base_lang
        full = (_prefix(lang) + path) if path != "/" else (_prefix(lang) + "/")
        return {
            "title": meta["title"],
            "description": meta["description"],
            "canonical": _site_url() + quote(full),
            "og_image": config.og_image,
            "alternates": [
                {"lang": code, "href": _site_url() + quote(link["href"])}
                for code, link in zip(configs, _switch(lang, path))
            ],
        }

    def _category_items(key: str) -> list[str]:
        provider = registry.get(key)
        if not provider:
            return []
        return [i for i in provider.items if i not in _excluded_items]

    def _category_page_meta(key: str, lang: str = "") -> dict:
        cfg = configs[lang or base_lang]
        return seo.category_meta(cfg, key, len(_category_items(key)))

    def _category_content(key: str, lang: str = "") -> dict:
        """The server-rendered half of a category landing page.

        The game itself is a canvas of JavaScript state, so without this the
        page is a heading and some buttons — roughly forty words, none of them
        about this category. The item names are the words people actually
        search, and they are already here; they just never reached the markup.
        """
        lang = lang or base_lang
        cfg = configs[lang]
        items = _category_items(key)
        shown = items[: cfg.contents_max]
        if lang != base_lang:
            provider = registry.get(key)
            shown = [provider.translate(i, lang) for i in shown]
        return {
            "label": seo.category_label(key, cfg.category_labels),
            "intro": seo.category_intro(cfg, key, len(items)),
            "count": len(items),
            # Not "items": Jinja resolves `category.items` to dict.items.
            "names": shown,
            "hidden": len(items) - len(shown),
        }

    def _render_index(initial_category=None, page=None, category=None,
                      lang="", path="/"):
        lang = lang or base_lang
        cfg = configs[lang]
        top_level, subs = build_menu(cfg.category_labels)
        # Collect all unique filters from all providers
        all_filters = _collect_filters()
        return render_template(
            "index.html",
            top_level=top_level,
            subcategories=subs,
            version=config.version,
            config=cfg,
            filters=all_filters,
            initial_category=initial_category,
            category_slugs=seo.canonical_slugs(registry.get_all()),
            category=category,
            # Real links to every category page. The menu is buttons wired to
            # JavaScript, so until now nothing on the site linked to a landing
            # page — they existed, and only the sitemap said so.
            category_index=sorted(
                (seo.category_label(key, cfg.category_labels), slug)
                for key, slug in seo.canonical_slugs(registry.get_all()).items()
            ),
            page=page or _page(seo.home_meta(cfg), "/", lang),
            lang=lang,
            prefix=_prefix(lang),
            languages=_switch(lang, path),
            lang_cookie=lang_cookie,
        )

    def index(lang=""):
        lang = lang or base_lang
        # ?cat=<key> opens the game straight into a category (shareable link);
        # otherwise fall back to config.default_category so the home page lands
        # on a live card instead of an empty "pick a category" screen.
        cat = request.args.get("cat", "")
        initial = cat if registry.get(cat) else None
        if initial is None and registry.get(config.default_category or ""):
            initial = config.default_category
        if not cat:
            elsewhere = _preferred_elsewhere(lang, "/")
            if elsewhere:
                return elsewhere
        # `?cat=` is the same page as that category's own URL, so it points at
        # it rather than competing with it. A bare `/` is the home page and
        # canonicalises to itself, even when a default category is showing.
        page = None
        path = "/"
        if cat and initial:
            slug = seo.canonical_slugs(registry.get_all()).get(initial)
            if slug:
                path = f"/{slug}"
                page = _page(_category_page_meta(initial, lang), path, lang)
        category = _category_content(initial, lang) if page else None
        return _render_index(initial, page, category, lang, path)

    def category_landing(slug, lang=""):
        lang = lang or base_lang
        # Pretty per-category landing pages, e.g. /food -> culture:food.
        key = seo.category_slugs(registry.get_all()).get(slug)
        if key is None:
            abort(404)
        # A category with a unique last segment answers at both /food and
        # /culture-food. Both keep working; the canonical names the short one
        # so the pair is never indexed as two pages.
        canonical = seo.canonical_slugs(registry.get_all()).get(key, slug)
        elsewhere = _preferred_elsewhere(lang, f"/{canonical}")
        if elsewhere:
            return elsewhere
        return _render_index(
            key,
            _page(_category_page_meta(key, lang), f"/{canonical}", lang),
            _category_content(key, lang),
            lang,
            f"/{canonical}",
        )

    def about(lang=""):
        lang = lang or base_lang
        elsewhere = _preferred_elsewhere(lang, "/about")
        if elsewhere:
            return elsewhere
        cfg = configs[lang]
        return render_template(
            "about.html",
            version=config.version,
            config=cfg,
            page=_page(seo.about_meta(cfg), "/about", lang),
            lang=lang,
            prefix=_prefix(lang),
            languages=_switch(lang, "/about"),
            lang_cookie=lang_cookie,
        )

    app.add_url_rule("/", "index", index)
    app.add_url_rule("/<slug>", "category_landing", category_landing)
    app.add_url_rule("/about", "about", about)
    for code in configs:
        if code == base_lang:
            continue
        # /en -> /en/, so the language's home has one address.
        app.add_url_rule(
            f"/{code}", f"index_{code}_bare",
            lambda code=code: redirect(f"/{code}/"),
        )
        app.add_url_rule(
            f"/{code}/", f"index_{code}", lambda code=code: index(code)
        )
        app.add_url_rule(
            f"/{code}/about", f"about_{code}", lambda code=code: about(code)
        )
        app.add_url_rule(
            f"/{code}/<slug>", f"category_landing_{code}",
            lambda slug, code=code: category_landing(slug, code),
        )

    @app.route("/robots.txt")
    def robots_txt():
        """Open the site to crawlers and point them at the sitemap.

        The game data endpoints are excluded: they answer with JSON a crawler
        can do nothing with, and /api/random is different on every request.
        """
        body = (
            "User-agent: *\n"
            "Allow: /\n"
            "Disallow: /api/\n"
            "\n"
            f"Sitemap: {_site_url()}/sitemap.xml\n"
        )
        return Response(body, mimetype="text/plain")

    @app.route("/sitemap.xml")
    def sitemap_xml():
        """Every page worth indexing, built from the registry.

        The category pages are reachable in the UI only by clicking a button,
        so without this a crawler finds the home page and nothing else. A new
        provider appears here the moment it registers — nothing to maintain.
        """
        base = _site_url()
        pages = ["/", "/about"]
        pages += [
            f"/{slug}"
            for slug in sorted(seo.canonical_slugs(registry.get_all()).values())
        ]
        paths = [
            (_prefix(code) + page) if page != "/" else (_prefix(code) + "/")
            for code in configs
            for page in pages
        ]
        urls = "".join(
            f"<url><loc>{escape(base + quote(path))}</loc></url>" for path in paths
        )
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"{urls}</urlset>"
        )
        return Response(body, mimetype="application/xml")

    @app.route("/api/random")
    def random_item():
        # A game played in another of its languages: answers and tags in it,
        # and the details panel from that Wikipedia edition.
        lang = request.args.get("lang", "")
        if lang not in configs:
            lang = base_lang
        token = images.use_details_lang(lang if lang != base_lang else None)
        try:
            return _random_item(lang)
        finally:
            images.reset_details_lang(token)

    def _random_item(lang):
        cats = request.args.get("cats", "")
        cat_list = [c for c in cats.split(",") if registry.get(c)]
        if not cat_list:
            return jsonify({"error": "Unknown category"}), 400

        seen = _seen_items(provider_items_for=cat_list)

        category = random.choice(cat_list)
        provider = registry.get(category)
        items = list(provider.items)

        # Apply filters
        for filter_name, filter_map in provider.filters.items():
            param = request.args.get(filter_name, "")
            if param:
                allowed = set()
                for val in param.split(","):
                    allowed.update(filter_map.get(val, []))
                items = [i for i in items if i in allowed]
                if not items:
                    return jsonify({"error": f"No items for {filter_name}"}), 400

        items = [i for i in items if i not in _excluded_items]
        unseen = [i for i in items if i not in seen]
        if not unseen:
            return jsonify({"error": "All items seen"}), 400
        candidates = random.sample(unseen, min(10, len(unseen)))

        for item in candidates:
            result = provider.get_image(item)
            if not result or not result.get("image"):
                continue

            result["item"] = item

            # Clean up name
            name = result.get("name", item)
            if "(" in name:
                name = name.split("(")[0].strip()
            result["name"] = name

            if provider.override_name:
                result["name"] = item
            if lang != base_lang:
                result["name"] = provider.translate(result["name"], lang)

            # Tag
            tag = provider.get_tag(item)
            if tag and lang != base_lang:
                tag = provider.translate(tag, lang)
            if tag:
                result["tag"] = tag
                if provider.tag_style:
                    result["tag_style"] = provider.tag_style

            # Clue
            clue = provider.get_clue(item)
            if clue:
                result["clue"] = clue

            if provider.light_bg:
                result["light_bg"] = True

            # Speaker button on reveal (any layout).
            audio = provider.get_audio(item)
            if audio:
                result["audio"] = audio

            # Details panel (enriched layout only — classic never shows it, so
            # don't pay for whatever the provider does to build it).
            if config.layout == "enriched":
                details = provider.get_details(item)
                if details:
                    result["details"] = details

            # Footers
            if provider.footers:
                result["footers"] = provider.footers

            return jsonify(result)

        return jsonify({"error": "No image found"}), 404

    @app.route("/api/report", methods=["POST"])
    def report():
        data = request.get_json(silent=True) or {}
        item = data.get("item", "")
        cats = data.get("cats", "")
        if item:
            _logger.info(f"REPORTED: {item} (categories: {cats})")
            logging.getLogger("reports").info(
                f"REPORTED: {item} (categories: {cats})"
            )
        return jsonify({"ok": True})

    @app.route("/healthz")
    def healthz():
        return jsonify({"status": "ok", "categories": len(registry.get_all())})

    return app


def _seen_items(provider_items_for: list[str]) -> set[str]:
    """The items this player has already seen, from the ``seen`` parameters.

    The page sends one ``seen=`` per item, since names can contain commas
    ("Pantheon, Rome"). A page loaded before that change still sends them
    joined by commas in a single value: split that, unless the whole value is
    itself an item.
    """
    values = request.args.getlist("seen")
    if len(values) == 1 and "," in values[0]:
        known = {
            item
            for key in provider_items_for
            for item in (registry.get(key).items if registry.get(key) else [])
        }
        if values[0] not in known:
            values = values[0].split(",")
    return {v for v in values if v}


def _collect_filters() -> dict:
    """Collect all unique filters across all providers.

    Returns a dict like:
    {
        "continents": {
            "categories": ["geography:countries:flags", ...],
            "options": ["africa", "america", "asia", ...]
        },
        ...
    }
    """
    filters: dict = {}
    for key, provider in registry.get_all().items():
        for filter_name, filter_map in provider.filters.items():
            if filter_name not in filters:
                filters[filter_name] = {
                    "categories": [],
                    "options": sorted(filter_map.keys()),
                }
            filters[filter_name]["categories"].append(key)
    return filters


def _load_excluded_items(app):
    """Load excluded items from file if it exists."""
    # Use current working directory for data files, not the engine package
    data_dir = os.getcwd()
    excluded_file = os.path.join(data_dir, "excluded_items.txt")
    if os.path.isfile(excluded_file):
        with open(excluded_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    _excluded_items.add(line)

    # Set up report logging (don't crash if we can't write)
    report_log = os.path.join(data_dir, "reported_items.log")
    try:
        handler = logging.FileHandler(report_log)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(message)s")
        )
        logging.getLogger("reports").addHandler(handler)
    except PermissionError:
        pass  # Reports won't be saved but app still works
    logging.getLogger("reports").setLevel(logging.INFO)
