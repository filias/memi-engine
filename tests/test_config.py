"""Tests for MemiConfig defaults and overrides."""

from memi_engine import MemiConfig


def test_defaults():
    cfg = MemiConfig()
    assert cfg.title == "memi"
    assert cfg.default_theme == "light"
    assert "light" in cfg.themes
    assert cfg.sponsor_url is None


def test_overrides():
    cfg = MemiConfig(title="Memi Lisboa", subtitle="pratica", default_theme="blue")
    assert cfg.title == "Memi Lisboa"
    assert cfg.subtitle == "pratica"
    assert cfg.default_theme == "blue"


def test_themes_are_independent_per_instance():
    a = MemiConfig()
    b = MemiConfig()
    a.themes.append("custom")
    assert "custom" not in b.themes
