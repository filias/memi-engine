"""Tests for ScientificNameProvider and the bundled database."""

from memi_engine import SCIENTIFIC_NAMES, ScientificNameProvider


class _Animals(ScientificNameProvider):
    key = "nature:animals"
    items = ["Lion", "Aardvark", "Acacia"]


def test_bundled_database_is_populated():
    assert len(SCIENTIFIC_NAMES) > 1000
    assert SCIENTIFIC_NAMES["Lion"] == "Panthera leo"


def test_tag_returns_latin_name_from_default_db():
    assert _Animals().get_tag("Lion") == "Panthera leo"


def test_tag_is_none_when_latin_equals_common_name():
    # "Acacia" maps to "Acacia" — no point showing it twice.
    assert _Animals().get_tag("Acacia") is None


def test_tag_is_none_for_unknown_item():
    assert _Animals().get_tag("Not An Animal") is None


def test_tag_style_is_scientific():
    assert _Animals().tag_style == "scientific"


def test_custom_mapping_overrides_default():
    class Plantas(ScientificNameProvider):
        key = "natureza:plantas"
        items = ["Sobreiro"]
        scientific_names = {"Sobreiro": "Quercus suber"}

    assert Plantas().get_tag("Sobreiro") == "Quercus suber"
    # Default DB no longer consulted for this provider.
    assert Plantas().get_tag("Lion") is None
