"""Scientific-name support.

Provides :class:`ScientificNameProvider`, a :class:`~memi_engine.CategoryProvider`
that tags each item with its binomial (Latin) name, and the bundled
:data:`SCIENTIFIC_NAMES` database mapping English common names to Latin names.
"""

from __future__ import annotations

from memi_engine.provider import CategoryProvider
from memi_engine.scientific_names import SCIENTIFIC_NAMES

__all__ = ["ScientificNameProvider", "SCIENTIFIC_NAMES"]


class ScientificNameProvider(CategoryProvider):
    """A category whose reveal tag is the item's scientific (Latin) name.

    Set :attr:`scientific_names` to a ``{display_name: latin_name}`` mapping.
    It defaults to the bundled English database (:data:`SCIENTIFIC_NAMES`), so
    English nature categories work out of the box; localized games pass their
    own mapping. The tag is shown only when the Latin name differs from the
    display name (skipping items like ``"Acacia"`` whose common and Latin names
    are identical), and is rendered in the italic *scientific* style.

    Example::

        from memi_engine import ScientificNameProvider, register

        class Animals(ScientificNameProvider):
            key = "nature:animals"
            items = ["Lion", "Tiger", "Aardvark"]
            # uses the bundled English database by default

        class Plantas(ScientificNameProvider):
            key = "natureza:plantas"
            items = ["Sobreiro", "Oliveira"]
            scientific_names = {
                "Sobreiro": "Quercus suber",
                "Oliveira": "Olea europaea",
            }

        register(Animals())
        register(Plantas())
    """

    scientific_names: dict[str, str] = SCIENTIFIC_NAMES
    tag_style = "scientific"

    def get_tag(self, item: str) -> str | None:
        latin = self.scientific_names.get(item)
        if latin and latin.lower() != item.lower():
            return latin
        return None
