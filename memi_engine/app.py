"""Generic Flask app for memi instances.

All category-specific logic lives in CategoryProviders. This module
handles routing, filtering, and the game loop — without knowing
anything about specific categories.
"""

from __future__ import annotations

import logging
import random
import subprocess

from flask import Flask, jsonify, render_template, request

from memi_engine import registry
from memi_engine.config import MemiConfig
from memi_engine.menu import build_menu

_logger = logging.getLogger(__name__)

# Items excluded via the review system
_excluded_items: set[str] = set()


def create_app(config: MemiConfig, instance_static: str | None = None) -> Flask:
    """Create a Flask app for a memi instance.

    Args:
        config: MemiConfig with title, themes, footers, etc.
        instance_static: Path to the instance's static folder (for logos, etc.).
            If provided, files here are served alongside the engine's static files.
    """
    import os

    engine_dir = os.path.dirname(__file__)
    engine_templates = os.path.join(engine_dir, "templates")
    engine_static = os.path.join(engine_dir, "static")

    app = Flask(
        __name__,
        template_folder=engine_templates,
        static_folder=engine_static,
    )

    # If instance has its own static folder, serve those files too
    # at the same /static/ URL, checked first before engine files
    if instance_static:
        from flask import send_from_directory

        @app.route("/static/<path:filename>")
        def combined_static(filename):
            # Try instance static first
            instance_path = os.path.join(instance_static, filename)
            if os.path.isfile(instance_path):
                return send_from_directory(instance_static, filename)
            # Fall back to engine static
            return send_from_directory(engine_static, filename)

    # Detect git version
    if not config.version:
        try:
            config.version = (
                subprocess.check_output(
                    ["git", "rev-parse", "--short", "HEAD"],
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
        except Exception:
            config.version = "dev"

    # Load excluded items
    _load_excluded_items(app)

    # --- Routes ---

    @app.route("/")
    def index():
        top_level, subs = build_menu()
        # Collect all unique filters from all providers
        all_filters = _collect_filters()
        return render_template(
            "index.html",
            top_level=top_level,
            subcategories=subs,
            version=config.version,
            config=config,
            filters=all_filters,
        )

    @app.route("/about")
    def about():
        return render_template(
            "about.html", version=config.version, config=config
        )

    @app.route("/api/random")
    def random_item():
        cats = request.args.get("cats", "")
        cat_list = [c for c in cats.split(",") if registry.get(c)]
        if not cat_list:
            return jsonify({"error": "Unknown category"}), 400

        seen = (
            set(request.args.get("seen", "").split(","))
            if request.args.get("seen")
            else set()
        )

        category = random.choice(cat_list)
        provider = registry.get(category)
        items = list(provider.items)

        # Apply filters
        for filter_name, filter_map in provider.filters.items():
            param = request.args.get(filter_name, "")
            if param:
                allowed = set()
                for val in param.split(","):
                    allowed.update(filter_map.get(val, []))
                items = [i for i in items if i in allowed]
                if not items:
                    return jsonify({"error": f"No items for {filter_name}"}), 400

        items = [i for i in items if i not in _excluded_items]
        unseen = [i for i in items if i not in seen]
        if not unseen:
            return jsonify({"error": "All items seen"}), 400
        candidates = random.sample(unseen, min(10, len(unseen)))

        for item in candidates:
            result = provider.get_image(item)
            if not result or not result.get("image"):
                continue

            result["item"] = item

            # Clean up name
            name = result.get("name", item)
            if "(" in name:
                name = name.split("(")[0].strip()
            result["name"] = name

            if provider.override_name:
                result["name"] = item

            # Tag
            tag = provider.get_tag(item)
            if tag:
                result["tag"] = tag

            # Clue
            clue = provider.get_clue(item)
            if clue:
                result["clue"] = clue

            if provider.light_bg:
                result["light_bg"] = True

            # Footers
            if provider.footers:
                result["footers"] = provider.footers

            return jsonify(result)

        return jsonify({"error": "No image found"}), 404

    @app.route("/api/report", methods=["POST"])
    def report():
        data = request.json
        item = data.get("item", "")
        cats = data.get("cats", "")
        if item:
            _logger.info(f"REPORTED: {item} (categories: {cats})")
            logging.getLogger("reports").info(
                f"REPORTED: {item} (categories: {cats})"
            )
        return jsonify({"ok": True})

    @app.route("/review")
    def review():
        return render_template("review.html", reports=[], config=config)

    return app


def _collect_filters() -> dict:
    """Collect all unique filters across all providers.

    Returns a dict like:
    {
        "continents": {
            "categories": ["geography:countries:flags", ...],
            "options": ["africa", "america", "asia", ...]
        },
        ...
    }
    """
    filters: dict = {}
    for key, provider in registry.get_all().items():
        for filter_name, filter_map in provider.filters.items():
            if filter_name not in filters:
                filters[filter_name] = {
                    "categories": [],
                    "options": sorted(filter_map.keys()),
                }
            filters[filter_name]["categories"].append(key)
    return filters


def _load_excluded_items(app):
    """Load excluded items from file if it exists."""
    import os

    # Use current working directory for data files, not the engine package
    data_dir = os.getcwd()
    excluded_file = os.path.join(data_dir, "excluded_items.txt")
    if os.path.isfile(excluded_file):
        with open(excluded_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    _excluded_items.add(line)

    # Set up report logging
    report_log = os.path.join(data_dir, "reported_items.log")
    handler = logging.FileHandler(report_log)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(message)s")
    )
    logging.getLogger("reports").addHandler(handler)
    logging.getLogger("reports").setLevel(logging.INFO)
