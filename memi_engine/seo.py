"""Search-engine metadata for a memi instance.

The engine serves one game from many URLs — ``/``, a ``/<slug>`` landing page
per category, and ``/about``. Until each of those carries its own title,
description and canonical they are, to a crawler, the same page repeated: the
category is only ever a JavaScript variable, so nothing in the markup says
which one you are looking at.

Everything here is derived from what an instance already declares — its title,
subtitle, about copy and registered categories — so a game gets per-page
metadata without adding configuration. The patterns on ``MemiConfig`` are the
override for instances that want their own wording.
"""

from __future__ import annotations

import re
from collections import Counter

# Roughly where Google truncates the snippet. Not a hard rule on their side,
# but a description that survives intact reads better than an ellipsis.
DESCRIPTION_MAX = 160

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_ENTITIES = {
    "&mdash;": "—", "&ndash;": "–", "&nbsp;": " ",
    "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'",
}


def strip_html(html: str) -> str:
    """Plain text from a fragment of HTML, whitespace collapsed.

    ``about_html`` is hand-written per instance and is the one place a game
    already describes itself in its own language, which makes it the best
    fallback for a meta description.
    """
    text = _TAG_RE.sub(" ", html or "")
    for entity, char in _ENTITIES.items():
        text = text.replace(entity, char)
    return _WS_RE.sub(" ", text).strip()


def shorten(text: str, limit: int = DESCRIPTION_MAX) -> str:
    """Trim to ``limit`` characters, preferring a sentence then a word break."""
    text = text.strip()
    if len(text) <= limit:
        return text
    window = text[: limit + 1]
    for end in (". ", "! ", "? "):
        cut = window.rfind(end)
        if cut > limit // 2:
            return window[: cut + 1].strip()
    cut = window.rfind(" ")
    trimmed = (window[:cut] if cut > 0 else window[:limit]).rstrip(" ,;:-–—")
    # A cut that happens to land on a full stop is already a clean ending; an
    # ellipsis after it just reads as a typo.
    return trimmed if trimmed.endswith((".", "!", "?")) else trimmed + "…"


def category_label(key: str) -> str:
    """Display label for a category key — its last segment, as the menu shows it.

    ``"cultura:monumentos"`` -> ``"monumentos"``.
    """
    return key.rsplit(":", 1)[-1]


def category_slugs(keys) -> dict[str, str]:
    """Map every URL slug to its category key.

    A key's last ``:``-segment is a slug when that segment is unique
    (``culture:food`` -> ``food``); the full dashed key is always available too
    (``culture-food``), and is the *only* slug for segments that would collide
    (e.g. several ``…:all`` categories, which all end in ``all``).
    """
    keys = list(keys)
    last = {k: category_label(k) for k in keys}
    counts = Counter(last.values())
    slugs: dict[str, str] = {}
    for k in keys:
        if counts[last[k]] == 1:
            slugs[last[k]] = k
        slugs.setdefault(k.replace(":", "-"), k)
    return slugs


def canonical_slugs(keys) -> dict[str, str]:
    """Map each category key to the one slug that represents it.

    The inverse of :func:`category_slugs`, and the reason it exists: a category
    with a unique last segment is reachable at both ``/food`` and
    ``/culture-food``. Both keep working — links to either are already out
    there — but only the short one goes in the sitemap, and the long one
    canonicalises to it, so the pair is never indexed as two pages.
    """
    preferred: dict[str, str] = {}
    for slug, key in category_slugs(keys).items():
        current = preferred.get(key)
        if current is None or len(slug) < len(current):
            preferred[key] = slug
    return preferred


def site_description(config) -> str:
    """The instance's own description, in the instance's own language.

    ``MemiConfig.description`` when set, else the opening of ``about_html``,
    which every game writes in its own language. The title/subtitle pair is the
    last resort: short, but never empty and never the wrong language.
    """
    if config.description:
        return config.description
    about = shorten(strip_html(config.about_html or ""))
    return about or f"{config.title} — {config.subtitle}"


def _format(pattern: str, **values: str) -> str:
    """Apply a config pattern, tolerating a placeholder the instance dropped."""
    try:
        return pattern.format(**values).strip()
    except (KeyError, IndexError):
        return values.get("title", "")


def home_meta(config) -> dict[str, str]:
    return {
        "title": _format(
            config.home_title, title=config.title, subtitle=config.subtitle
        ),
        "description": site_description(config),
    }


def about_meta(config) -> dict[str, str]:
    return {
        "title": f"{config.label_about} — {config.title}",
        "description": site_description(config),
    }


def category_meta(config, key: str, count: int = 0) -> dict[str, str]:
    """Title and description for one category's landing page.

    ``count`` is how many items the category holds; it is not in either default
    pattern, but an instance can use ``{count}`` to say so ("monumentos — 34
    monumentos portugueses to name").
    """
    values = {
        "category": category_label(key),
        "title": config.title,
        "subtitle": config.subtitle,
        "count": str(count),
    }
    return {
        "title": _format(config.category_title, **values),
        "description": shorten(
            _format(
                config.category_description,
                description=site_description(config),
                **values,
            )
        ),
    }
