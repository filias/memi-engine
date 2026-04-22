"""Configuration for a memi instance."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MemiConfig:
    """Configuration for a memi game instance.

    Attributes:
        title: Game title shown in the header.
        subtitle: Subtitle shown below the title.
        themes: List of available theme names.
        default_theme: Initial theme.
        sponsor_url: URL for the sponsor link (None to hide).
        sponsor_text: Text next to the heart icon.
        about_html: Custom HTML for the about page body.
        analytics_html: Analytics script HTML (e.g. GoatCounter).
        footers: Dict of footer_id -> HTML content for attribution footers.
        version: Version string shown in the footer (auto-detected from git).
    """

    title: str = "memi"
    subtitle: str = "practise your memory"
    themes: list[str] = field(
        default_factory=lambda: [
            "light", "yellow", "pink", "blue",
            "green", "brown", "grey", "dark",
        ]
    )
    default_theme: str = "light"
    sponsor_url: str | None = None
    sponsor_text: str = "sponsor"
    about_html: str | None = None
    analytics_html: str | None = None
    footers: dict[str, str] = field(default_factory=dict)
    version: str = ""

    # UI labels (for i18n)
    label_theme: str = "theme"
    label_about: str = "about"
    label_report: str = "report"
    label_reported: str = "reported"
    label_clues_on: str = "clues: on"
    label_clues_off: str = "clues: off"
    label_show_letter: str = "show letter"
    label_pick_category: str = "pick a category"
    label_loading: str = "loading..."
    label_all_done: str = "all done! click to start over"
    label_click_to_reveal: str = "click the image to reveal the answer"
    label_click_for_new: str = "click again for a new one"
    label_back: str = "back to playing"
    done_html: str = ""  # Custom HTML shown when all items are done
