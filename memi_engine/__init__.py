"""memi-engine: build your own memi memory card game.

Usage:
    from memi_engine import CategoryProvider, MemiConfig, create_app, register

    class MyCategory(CategoryProvider):
        key = "my:category"
        items = ["Item 1", "Item 2"]

    register(MyCategory())

    app = create_app(MemiConfig(title="My Memi"))
"""

from memi_engine.app import create_app
from memi_engine.config import MemiConfig
from memi_engine.provider import CategoryProvider
from memi_engine.registry import register

__all__ = ["CategoryProvider", "MemiConfig", "create_app", "register"]
