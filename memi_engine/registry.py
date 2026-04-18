"""Global registry for category providers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from memi_engine.provider import CategoryProvider

_providers: dict[str, CategoryProvider] = {}


def register(provider: CategoryProvider) -> None:
    """Register a category provider."""
    _providers[provider.key] = provider


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
