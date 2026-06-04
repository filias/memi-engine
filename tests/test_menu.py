"""Tests for the key -> menu-tree builder."""

from memi_engine import CategoryProvider, register
from memi_engine.menu import build_menu


def _register(key):
    p = CategoryProvider()
    p.key = key
    p.items = ["item"]
    register(p)


def test_single_level_key_is_top_level_leaf():
    _register("space")
    top_level, subs = build_menu()
    assert {"label": "space", "key": "space"} in top_level
    assert "space" not in subs


def test_two_level_key_creates_submenu():
    _register("nature:animals")
    _register("nature:plants")
    top_level, subs = build_menu()

    parents = [t for t in top_level if t["label"] == "nature"]
    assert parents == [{"label": "nature", "has_submenu": True}]

    labels = {child["label"] for child in subs["nature"]}
    assert labels == {"animals", "plants"}


def test_label_is_last_segment_of_key():
    # The engine renders the last key segment as the on-screen label.
    _register("geography:countries")
    _, subs = build_menu()
    assert subs["geography"][0]["label"] == "countries"
    assert subs["geography"][0]["key"] == "geography:countries"


def test_three_level_key_nests_groups():
    _register("nature:plants:flowers")
    _register("nature:plants:trees")
    _, subs = build_menu()
    plants_group = next(c for c in subs["nature"] if c["label"] == "plants")
    leaf_labels = {c["label"] for c in plants_group["children"]}
    assert leaf_labels == {"flowers", "trees"}


def test_all_sorts_first():
    _register("nature:zebra")
    _register("nature:all")
    _register("nature:lion")
    _, subs = build_menu()
    assert subs["nature"][0]["label"] == "all"
