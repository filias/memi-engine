"""Global registry for category providers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from memi_engine.provider import CategoryProvider

_providers: dict[str, CategoryProvider] = {}


def register(
    provider: CategoryProvider | type[CategoryProvider],
) -> CategoryProvider | type[CategoryProvider]:
    """Register a category provider.

    Accepts a provider instance, or a ``CategoryProvider`` subclass so it can
    be used as a class decorator::

        @register
        class Animals(CategoryProvider):
            key = "nature:animals"
            items = ["Lion", "Tiger"]

    Returns its argument unchanged.
    """
    instance = provider() if isinstance(provider, type) else provider
    _providers[instance.key] = instance
    return provider


def get(key: str) -> CategoryProvider | None:
    """Get a provider by key."""
    return _providers.get(key)


def get_all() -> dict[str, CategoryProvider]:
    """Return all registered providers."""
    return dict(_providers)


def get_categories() -> dict[str, list[str]]:
    """Return {key: items} for all providers — used by the menu builder."""
    return {k: v.items for k, v in _providers.items()}


def clear() -> None:
    """Clear all providers (useful for testing)."""
    _providers.clear()
