"""Build a nested menu structure from registered category providers."""

from __future__ import annotations

from memi_engine.registry import get, get_categories


def build_menu(labels: dict[str, str] | None = None):
    """Build a nested menu structure from registered categories.

    Supports up to 4 levels: parent:group:subgroup:label

    Returns (top_level, subcategories) where:
    - top_level: sorted list of {"label": ..., "key": ... or "has_submenu": True}
    - subcategories: dict of parent -> list of children (recursively nested)

    ``labels`` maps key segments to what the menu shows for them (a game in a
    second language). Every entry keeps its segment as ``label`` — the JS looks
    groups up by it — and adds ``text`` when the shown label differs.
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
            subs.setdefault(parent, []).append(_leaf(key, label))
        elif len(parts) == 3:
            parent, group, label = parts
            top_level_keys.add(parent)
            parent_list = subs.setdefault(parent, [])
            sub_group = _find_or_create_group(parent_list, group)
            sub_group["children"].append(_leaf(key, label))
        elif len(parts) == 4:
            parent, group, subgroup, label = parts
            top_level_keys.add(parent)
            parent_list = subs.setdefault(parent, [])
            group_node = _find_or_create_group(parent_list, group)
            sub_node = _find_or_create_group(group_node["children"], subgroup)
            sub_node["children"].append(_leaf(key, label))

    top_level = []
    for name in sorted(top_level_keys):
        if name in subs:
            top_level.append({"label": name, "has_submenu": True})
        else:
            top_level.append({"label": name, "key": name})

    _sort_children(subs)
    if labels:
        _apply_labels(top_level, labels)
        for children in subs.values():
            _apply_labels(children, labels)

    return top_level, subs


def _apply_labels(items, labels):
    for item in items:
        text = labels.get(item["label"])
        if text:
            item["text"] = text
        if "children" in item:
            _apply_labels(item["children"], labels)


def _find_or_create_group(items, label):
    for item in items:
        if item.get("label") == label and "children" in item:
            return item
    node = {"label": label, "children": []}
    items.append(node)
    return node


def _leaf(key, label):
    """A submenu entry; ``default`` marks the category its submenu opens on."""
    leaf = {"key": key, "label": label}
    provider = get(key)
    if provider is not None and provider.submenu_default:
        leaf["default"] = True
    return leaf


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
    # An own "all" category first, then the submenu's default, then A-Z.
    items.sort(
        key=lambda s: (
            s.get("label", "") != "all",
            not s.get("default", False),
            s.get("label", ""),
        )
    )
