"""
bdf2ufo

Alternate glyphs for BDF to UFO font conversion.

(C) 2024-2026 Gissio
License: MIT
"""

import logging

from .bdf_font import BDFFont
from .data import ALTERNATE_FEATURES

# Definitions
logger = logging.getLogger(__name__)


def build_alternates(bdf_font: BDFFont) -> dict:
    """Add the alternate glyphs of the font and return their substitutions.

    An alternate glyph is an unencoded glyph named after the encoded glyph it
    replaces, with the tag of its feature as suffix: for instance, "zero.zero"
    for the slashed zero of the "zero" feature.

    The glyphs are added after all other glyphs, ligatures included, so that
    the jitter of the other glyphs does not depend on them.

    Args:
        bdf_font: The BDF font object.

    Returns:
        Dictionary mapping each feature tag of ALTERNATE_FEATURES to a
        dictionary mapping glyph names to the names of their alternates.
    """
    alternates = {feature_tag: {} for feature_tag in ALTERNATE_FEATURES}

    for alternate_name, glyph in bdf_font.alternate_glyphs.items():
        base_name, feature_tag = alternate_name.rsplit(".", 1)

        if (
            base_name not in bdf_font.glyphs
            or bdf_font.glyphs[base_name]["character"] is None
        ):
            logger.warning(
                "Alternate '%s' names '%s', which is not an encoded glyph of the font, skipping",
                alternate_name,
                base_name,
            )
            continue

        if bdf_font.monospace and glyph["advance"] != bdf_font.monospace:
            logger.warning(
                "Alternate '%s' has advance %d, expected %d, skipping",
                alternate_name,
                glyph["advance"],
                bdf_font.monospace,
            )
            continue

        bdf_font.glyphs[alternate_name] = glyph
        alternates[feature_tag][base_name] = alternate_name

    for feature_tag, substitutions in alternates.items():
        if substitutions:
            logger.info(
                "Added %d alternates for '%s'", len(substitutions), feature_tag
            )

    return alternates


def get_alternate_features(alternates: dict) -> list:
    """Return the lines of the features that substitute the alternates.

    Args:
        alternates: The alternates, from build_alternates().

    Returns:
        A list of feature file lines, empty if the font has no alternates.
    """
    lines = []

    for feature_tag, substitutions in alternates.items():
        if len(substitutions) == 0:
            continue

        lines.append(f"feature {feature_tag} {{")
        for base_name, alternate_name in substitutions.items():
            lines.append(f"    sub {base_name} by {alternate_name};")
        lines.append(f"}} {feature_tag};")
        lines.append("")

    return lines
