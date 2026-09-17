"""Configuration for a memi instance."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MemiConfig:
    """Configuration for a memi game instance.

    Attributes:
        title: Game title shown in the header.
        subtitle: Subtitle shown below the title.
        themes: List of available theme names.
        default_theme: Initial theme.
        sponsor_url: URL for the sponsor link (None to hide).
        sponsor_text: Text next to the heart icon.
        about_html: Custom HTML for the about page body.
        analytics_html: Analytics script HTML (e.g. GoatCounter).
        footers: Dict of footer_id -> HTML content for attribution footers.
        related_sites: List of sibling memi games to link from the about page.
            Each item is {"name": ..., "url": ...}.
        default_category: Category key to open into on the home page when no
            ?cat= / slug is given, so visitors land on a live card instead of an
            empty "pick a category" screen. None keeps the empty initial state.
        version: Version string shown in the footer (auto-detected from git).
    """

    title: str = "memi"
    subtitle: str = "practise your memory"
    themes: list[str] = field(
        default_factory=lambda: [
            "light", "yellow", "pink", "blue",
            "green", "brown", "grey", "dark",
        ]
    )
    default_theme: str = "light"
    sponsor_url: str | None = None
    sponsor_text: str = "sponsor"
    about_html: str | None = None
    analytics_html: str | None = None
    footers: dict[str, str] = field(default_factory=dict)
    related_sites: list[dict[str, str]] = field(default_factory=list)
    default_category: str | None = None
    version: str = ""

    # UI labels (for i18n)
    label_theme: str = "theme"
    label_about: str = "about"
    label_report: str = "report"
    label_reported: str = "reported"
    label_clues_on: str = "clues: on"
    label_clues_off: str = "clues: off"
    label_show_letter: str = "show letter"
    label_pick_category: str = "pick a category"
    label_loading: str = "loading..."
    label_all_done: str = "all done! click to start over"
    label_click_to_reveal: str = "click the image to reveal the answer"
    label_click_for_new: str = "click again for a new one"
    label_back: str = "back to playing"
    label_related_sites: str = "more memi games"
    label_more: str = "know more"
    done_html: str = ""  # Custom HTML shown when all items are done

    # Favicon: background of the rounded square (default dark goldenrod)
    favicon_color: str = "#b8860b"

    # Wikipedia language edition for the default image / "know more" helpers.
    wikipedia_lang: str = "en"

    # --- Search engines and link previews ---
    #
    # Every field here has a working default derived from the fields above, so
    # a game gets per-page titles, descriptions and canonicals without setting
    # any of them. See memi_engine/seo.py.

    # Canonical origin, e.g. "https://pt.memi.games". Leave None to take it
    # from the request (correct behind the usual Caddy reverse proxy, which
    # sends X-Forwarded-Proto and X-Forwarded-Host). Set it — or the
    # MEMI_SITE_URL env var — to pin canonical URLs to one host regardless of
    # what a request claims.
    site_url: str | None = None

    # <html lang>. The engine is English; the games mostly are not, and a page
    # that declares the wrong language is a page Google shows to the wrong
    # people. Set it per instance ("pt", "sk", "ca").
    html_lang: str = "en"

    # Meta description for the home page. Empty falls back to the opening of
    # about_html, which is already written in the instance's language.
    description: str = ""

    # Absolute URL of the link-preview image (og:image). None omits the tag;
    # the card still renders from the title and description.
    og_image: str | None = None

    # Title patterns. Placeholders: {title}, {subtitle} and, for a category
    # page, {category} — the category's label as the menu shows it.
    home_title: str = "{title} — {subtitle}"
    category_title: str = "{category} — {title}"

    # Description pattern for a category page. {description} is the site
    # description resolved above.
    category_description: str = "{category} — {description}"
