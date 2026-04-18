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
    """

    key: str = ""
    items: list[str] = []
    filters: dict[str, dict[str, list[str]]] = {}
    single_select: bool = False
    light_bg: bool = False
    override_name: bool = False
    footers: list[str] = []

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
