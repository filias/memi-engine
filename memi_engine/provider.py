"""CategoryProvider base class — the core abstraction of memi-engine.

Each category in a memi instance is a CategoryProvider subclass that
declares its items, filters, and how to fetch images/tags/clues.
"""

from __future__ import annotations


class CategoryProvider:
    """Base class for a memi category.

    Subclass this and override the methods you need. At minimum, set
    ``key`` and ``items``. The default ``get_image`` fetches from Wikipedia.

    Attributes:
        key: Category key like ``"nature:animals"`` — determines the menu
            structure (colon-separated levels).
        items: List of item names in this category.
        filters: Dict of filter_name -> {value: [items]}. The engine
            auto-generates filter UI and URL params from this.
        single_select: If True, only one subcategory can be active at a time.
        light_bg: If True, cards use a light background (good for logos).
        override_name: If True, the item key is used as the display name
            instead of the Wikipedia article title.
        footers: List of footer IDs to show when this category is active.
        submenu_default: If True, opening this category's submenu starts it
            playing (and lists it first) instead of waiting for a choice.
        map_zoom: Zoom of the details panel's map (enriched layout), pinned on
            the item's Wikidata coordinates. ``None`` (the default) for no map
            — right for things that aren't places, like food or people.
        map_bounds: Optional ``((lat_min, lat_max), (lon_min, lon_max))``.
            Coordinates outside it get no map: they belong to something other
            than what the card shows (a river's point is often its mouth).
        translations: For a game played in more than one language (see
            ``MemiConfig.languages``): ``{lang: {text: translation}}`` for the
            card's answer and tag, e.g. ``{"en": {"Golfinho-roaz": "Bottlenose
            dolphin", "rei": "king"}}``. Text with no entry shows as it is —
            right for most people's names.
    """

    key: str = ""
    items: list[str] = []
    filters: dict[str, dict[str, list[str]]] = {}
    single_select: bool = False
    light_bg: bool = False
    override_name: bool = False
    footers: list[str] = []
    tag_style: str | None = None  # "plain", "scientific", or None (auto-detect)
    submenu_default: bool = False
    map_zoom: int | None = None
    map_bounds: tuple[tuple[float, float], tuple[float, float]] | None = None
    translations: dict[str, dict[str, str]] = {}

    def __init__(self) -> None:
        # Copy the declarative class-level containers onto the instance so the
        # shared base defaults (and sibling instances) can never be mutated
        # through one provider. Inner filter data is app-owned and read-only.
        self.items = list(self.items)
        self.filters = dict(self.filters)
        self.footers = list(self.footers)

    def get_image(self, item: str) -> dict | None:
        """Return ``{"name": ..., "image": ...}`` or ``None``.

        The default implementation fetches the main image from the
        Wikipedia article for ``item``. Override for custom sources.
        """
        from memi_engine.images import get_wikipedia_image

        return get_wikipedia_image(item)

    def get_tag(self, item: str) -> str | None:
        """Return a tag/subtitle shown on the revealed card, or None."""
        return None

    def get_clue(self, item: str) -> str | None:
        """Return a clue shown before reveal (e.g. country name), or None."""
        return None

    def get_details(self, item: str) -> dict | None:
        """Return extra content for the enriched layout's details panel, or None.

        Only called when the game uses ``MemiConfig(layout="enriched")``. Every
        key is optional::

            {
                "text": "Longer description; blank lines start a paragraph.",
                "area": {"name": "Kazimierz", "url": "https://…"},
                "map": {"lat": 50.0513, "lon": 19.9465, "zoom": 17},
            }

        ``map`` shows an OpenStreetMap view pinned at ``lat``/``lon``; ``zoom``
        defaults to 17 (street level).

        The default reads the item's Wikipedia article (see
        :meth:`get_wikipedia_title`) — in the game's language (``html_lang``)
        when that edition has one: its opening paragraph as ``text``, and a
        ``map`` on its coordinates when the category sets ``map_zoom`` (and
        they fall inside ``map_bounds``, if set). Override to say something of
        your own; return ``None`` for no panel.
        """
        from memi_engine import images

        found = self.get_wikipedia_title(item)
        if not found:
            return None
        lang, title = found
        # In the game's own language when that edition has the article.
        want = images.details_lang()
        if want and want != lang:
            translated = images.wikipedia_langlink(title, lang, want)
            if translated:
                lang, title = want, translated
        article = images.get_wikipedia_article(title, lang)
        if not article:
            return None
        details: dict = {}
        if article["intro"]:
            details["text"] = article["intro"]
        coords = article["coords"]
        if self.map_zoom and coords and self._in_map_bounds(*coords):
            lat, lon = coords
            details["map"] = {"lat": lat, "lon": lon, "zoom": self.map_zoom}
        return details or None

    def get_wikipedia_title(self, item: str) -> tuple[str, str] | None:
        """``(lang, title)`` of the article the details panel describes.

        The default follows the card's "know more" link — the ``url`` that
        :meth:`get_image` returns — when it is a Wikipedia article, so the
        panel and the link always describe the same thing. Override for cards
        whose link goes elsewhere (or has none) but that do have an article.
        """
        from memi_engine.images import wikipedia_title_from_url

        result = self.get_image(item) or {}
        return wikipedia_title_from_url(result.get("url", ""))

    def _in_map_bounds(self, lat: float, lon: float) -> bool:
        if not self.map_bounds:
            return True
        (lat_min, lat_max), (lon_min, lon_max) = self.map_bounds
        return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max

    def translate(self, text: str, lang: str) -> str:
        """``text`` (an answer or a tag) in ``lang``, from ``translations``."""
        return self.translations.get(lang, {}).get(text, text)

    def get_audio(self, item: str) -> dict | None:
        """Return how to say the answer aloud, or None for no speaker button.

        ::

            {"text": "dziękuję", "lang": "pl-PL", "src": "/static/audio/dziekuje.mp3"}

        On reveal the card shows a speaker button. It plays ``src`` when given
        and falls back to the browser's speech synthesis of ``text`` in
        ``lang`` (a BCP 47 tag) when there is no recording or it fails to play.
        Add ``"before_reveal": True`` when hearing it is part of the question
        (listen, then name it): the button then shows as soon as the card loads.
        """
        return None


class AggregateProvider(CategoryProvider):
    """An "all" provider whose contents are the union of its sibling providers.

    Set only ``key`` (e.g. ``"nature:all"``). The aggregate collects every
    registered provider sharing its parent prefix (``"nature:"``) — except other
    aggregates and itself — and exposes the union of their items (deduped, order
    preserved). Image, tag and clue lookups delegate to the member that owns the
    item, so each category keeps its own behaviour.

    Members are resolved lazily from the registry, so a newly added sibling
    category flows into the aggregate automatically — no list to maintain.
    """

    def __init__(self) -> None:
        # `items` is a computed property here, so skip the base list-copy.
        self.filters = dict(self.filters)
        self.footers = list(self.footers)

    @property
    def _prefix(self) -> str:
        return self.key.rsplit(":", 1)[0] + ":"

    def _members(self) -> list[CategoryProvider]:
        from memi_engine.registry import get_all

        prefix = self._prefix
        members = []
        for key, prov in get_all().items():
            if prov is self or isinstance(prov, AggregateProvider):
                continue
            if key.startswith(prefix):
                members.append(prov)
        return members

    @property
    def items(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for prov in self._members():
            for item in prov.items:
                if item not in seen:
                    seen.add(item)
                    result.append(item)
        return result

    @items.setter
    def items(self, value):  # tolerate base-class assignment, ignore it
        pass

    def _owner(self, item: str) -> CategoryProvider | None:
        for prov in self._members():
            if item in prov.items:
                return prov
        return None

    def get_image(self, item: str) -> dict | None:
        owner = self._owner(item)
        return owner.get_image(item) if owner else super().get_image(item)

    def get_tag(self, item: str) -> str | None:
        owner = self._owner(item)
        return owner.get_tag(item) if owner else None

    def get_clue(self, item: str) -> str | None:
        owner = self._owner(item)
        return owner.get_clue(item) if owner else None

    def get_details(self, item: str) -> dict | None:
        owner = self._owner(item)
        return owner.get_details(item) if owner else None

    def get_audio(self, item: str) -> dict | None:
        owner = self._owner(item)
        return owner.get_audio(item) if owner else None

    def translate(self, text: str, lang: str) -> str:
        for prov in self._members():
            translated = prov.translate(text, lang)
            if translated != text:
                return translated
        return text
