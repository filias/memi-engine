"""Build a nested menu structure from registered category providers."""

from __future__ import annotations

from memi_engine.registry import get_categories


def build_menu():
    """Build a nested menu structure from registered categories.

    Supports up to 4 levels: parent:group:subgroup:label

    Returns (top_level, subcategories) where:
    - top_level: sorted list of {"label": ..., "key": ... or "has_submenu": True}
    - subcategories: dict of parent -> list of children (recursively nested)
    """
    categories = get_categories()
    top_level_keys = set()
    subs = {}

    for key in categories:
        parts = key.split(":")
        if len(parts) == 1:
            top_level_keys.add(key)
        elif len(parts) == 2:
            parent, label = parts
            top_level_keys.add(parent)
            subs.setdefault(parent, []).append({"key": key, "label": label})
        elif len(parts) == 3:
            parent, group, label = parts
            top_level_keys.add(parent)
            parent_list = subs.setdefault(parent, [])
            sub_group = _find_or_create_group(parent_list, group)
            sub_group["children"].append({"key": key, "label": label})
        elif len(parts) == 4:
            parent, group, subgroup, label = parts
            top_level_keys.add(parent)
            parent_list = subs.setdefault(parent, [])
            group_node = _find_or_create_group(parent_list, group)
            sub_node = _find_or_create_group(group_node["children"], subgroup)
            sub_node["children"].append({"key": key, "label": label})

    top_level = []
    for name in sorted(top_level_keys):
        if name in subs:
            top_level.append({"label": name, "has_submenu": True})
        else:
            top_level.append({"label": name, "key": name})

    _sort_children(subs)

    return top_level, subs


def _find_or_create_group(items, label):
    for item in items:
        if item.get("label") == label and "children" in item:
            return item
    node = {"label": label, "children": []}
    items.append(node)
    return node


def _sort_children(subs):
    if isinstance(subs, dict):
        for cat in subs:
            _sort_list(subs[cat])
    elif isinstance(subs, list):
        _sort_list(subs)


def _sort_list(items):
    for item in items:
        if "children" in item:
            _sort_list(item["children"])
    items.sort(key=lambda s: (s.get("label", "") != "all", s.get("label", "")))
