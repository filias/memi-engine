"""Tests for the provider registry."""

from memi_engine import CategoryProvider, register, registry


def _provider(key, items):
    p = CategoryProvider()
    p.key = key
    p.items = items
    return p


def test_register_and_get():
    p = _provider("nature:animals", ["Lion"])
    register(p)
    assert registry.get("nature:animals") is p


def test_get_unknown_returns_none():
    assert registry.get("does:not:exist") is None


def test_register_same_key_overwrites():
    first = _provider("a:b", ["x"])
    second = _provider("a:b", ["y"])
    register(first)
    register(second)
    assert registry.get("a:b") is second


def test_get_categories_maps_key_to_items():
    register(_provider("a:b", ["x", "y"]))
    register(_provider("c:d", ["z"]))
    assert registry.get_categories() == {"a:b": ["x", "y"], "c:d": ["z"]}


def test_clear_empties_registry():
    register(_provider("a:b", ["x"]))
    registry.clear()
    assert registry.get_all() == {}


def test_register_as_class_decorator():
    @register
    class Animals(CategoryProvider):
        key = "nature:animals"
        items = ["Lion"]

    # The name stays bound to the class, and an instance is registered.
    assert Animals is not None and isinstance(Animals, type)
    assert isinstance(registry.get("nature:animals"), Animals)


def test_register_instance_still_works():
    p = _provider("a:b", ["x"])
    assert register(p) is p
    assert registry.get("a:b") is p
