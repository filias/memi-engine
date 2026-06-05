"""Tests for CategoryProvider instance isolation."""

from memi_engine import CategoryProvider


class Animals(CategoryProvider):
    key = "nature:animals"
    items = ["Lion", "Tiger"]
    filters = {"size": {"big": ["Lion"]}}
    footers = ["wiki"]


def test_instances_do_not_share_mutable_containers():
    a, b = Animals(), Animals()
    a.items.append("Bear")
    a.footers.append("extra")
    a.filters["size"] = {}
    assert b.items == ["Lion", "Tiger"]
    assert b.footers == ["wiki"]
    assert b.filters == {"size": {"big": ["Lion"]}}


def test_base_class_defaults_not_mutated():
    p = CategoryProvider()
    p.items.append("x")
    p.footers.append("y")
    # The class-level defaults must stay empty.
    assert CategoryProvider.items == []
    assert CategoryProvider.footers == []
