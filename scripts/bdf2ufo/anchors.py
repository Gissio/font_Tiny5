"""
bdf2ufo

Anchor building for BDF to UFO font conversion.

(C) 2024-2026 Gissio
License: MIT
"""

import logging

from .bdf_font import BDFFont
from .data import MARKS, BASE_ANCHORS_EXCEPTIONS
from .utils import Vec2

# Definitions
logger = logging.getLogger(__name__)


def build_anchors(bdf_font: BDFFont, components: dict, custom_anchors: dict) -> dict:
    """Build anchors from BDF font components.

    Args:
        bdf_font: The BDF font object.
        components: Dictionary of glyph components.
        custom_anchors: Dictionary of custom anchors.

    Returns:
        Dictionary of anchors for the UFO font.
    """
    anchors = build_custom_anchors(bdf_font, custom_anchors)

    for priority in range(3):  # Adjust the range based on your priority levels
        build_anchors_with_priority(bdf_font, components, anchors, priority)

    return anchors


def build_custom_anchors(bdf_font: BDFFont, custom_anchors: dict) -> dict:
    """Build custom anchors from the provided dictionary.

    Args:
        bdf_font: The BDF font object.
        custom_anchors: Dictionary of custom anchors.

    Returns:
        Dictionary of processed custom anchors.
    """
    anchors = {}
    if custom_anchors is None:
        return anchors

    for glyph_character, glyph_anchor in custom_anchors.items():
        glyph_name = bdf_font.names[glyph_character]

        anchors[glyph_name] = {}
        for anchor_name, anchor_offset in glyph_anchor.items():
            anchors[glyph_name][anchor_name] = Vec2(anchor_offset)

    return anchors


def build_anchors_with_priority(
    bdf_font: BDFFont, components: dict, anchors: dict, priority: int
) -> dict:
    """Build anchors with specific priority for BDF font components.

    Args:
        bdf_font: The BDF font object.
        components: Dictionary of glyph components.
        anchors: Dictionary to store anchor positions.
        requested_priority: The priority level to filter anchors by.

    Returns:
        Dictionary of anchors for the UFO font.
    """
    for composed_glyph_name, composed_glyph_components in components.items():
        # Only process composed glyphs with exactly two components (base and mark).
        if len(composed_glyph_components) != 2:
            continue

        # Extract mark and base component information.
        mark_component = composed_glyph_components[0]
        mark_glyph_name = mark_component[0]
        mark_component_offset = mark_component[1]

        base_component = composed_glyph_components[1]
        base_glyph_name = base_component[0]
        base_component_offset = base_component[1]

        # Retrieve glyph information for the base and mark components.
        base_glyph = bdf_font.glyphs[base_glyph_name]
        base_glyph_character = base_glyph["character"]
        _base_glyph_size = Vec2(
            base_glyph["bitmap"].shape[1], base_glyph["bitmap"].shape[0]
        )
        _base_glyph_offset = base_glyph["offset"]

        mark_glyph = bdf_font.glyphs[mark_glyph_name]
        mark_glyph_character = mark_glyph["character"]
        mark_glyph_size = Vec2(
            mark_glyph["bitmap"].shape[1], mark_glyph["bitmap"].shape[0]
        )
        mark_glyph_offset = mark_glyph["offset"]

        # Check is base glyph is in the list of exceptions for anchor building.
        if base_glyph_character in BASE_ANCHORS_EXCEPTIONS:
            continue

        # Check if base glyph is not a mark and mark glyph is a mark.
        if base_glyph_character in MARKS or mark_glyph_character not in MARKS:
            continue

        # Check if anchor alignment matches requested alignment.
        anchor_name, anchor_priority = MARKS[mark_glyph_character]
        if anchor_priority != priority:
            continue

        base_anchor_name = f"{anchor_name}"
        mark_anchor_name = f"_{anchor_name}"

        if base_glyph_name not in anchors:
            anchors[base_glyph_name] = {}
        if mark_glyph_name not in anchors:
            anchors[mark_glyph_name] = {}

        # Calculate anchor offsets
        if anchor_name == "top":
            anchor_offset = Vec2(int(mark_glyph_size.x / 2), 0)
        elif anchor_name == "bottom":
            anchor_offset = Vec2(int(mark_glyph_size.x / 2), mark_glyph_size.y)
        elif anchor_name == "ogonek":
            anchor_offset = Vec2(0, mark_glyph_size.y)
        elif anchor_name == "center":
            anchor_offset = Vec2(int(mark_glyph_size.x / 2), int(mark_glyph_size.y / 2))
        else:
            anchor_offset = Vec2(0, 0)

        mark_anchor_offset = mark_glyph_offset + anchor_offset
        base_anchor_offset = (
            mark_anchor_offset + mark_component_offset - base_component_offset
        )

        # Calculate base and mark anchors
        if (
            base_anchor_name not in anchors[base_glyph_name]
            and mark_anchor_name not in anchors[mark_glyph_name]
        ):
            anchors[base_glyph_name][base_anchor_name] = base_anchor_offset
            anchors[mark_glyph_name][mark_anchor_name] = mark_anchor_offset

            logger.info(
                "Added base anchor '%s' to glyph '%s' from composed glyph '%s'.",
                base_anchor_name,
                base_glyph_name,
                composed_glyph_name,
            )
            logger.info(
                "Added mark anchor '%s' to glyph '%s' from composed glyph '%s'.",
                mark_anchor_name,
                mark_glyph_name,
                composed_glyph_name,
            )

        elif (
            base_anchor_name not in anchors[base_glyph_name]
            and mark_anchor_name in anchors[mark_glyph_name]
        ):
            mark_anchor_offset_set = anchors[mark_glyph_name][mark_anchor_name]

            anchors[base_glyph_name][base_anchor_name] = base_anchor_offset + (
                mark_anchor_offset_set - mark_anchor_offset
            )
            logger.info(
                "Added base anchor '%s' to glyph '%s' from composed glyph '%s'.",
                base_anchor_name,
                base_glyph_name,
                composed_glyph_name,
            )

        elif (
            base_anchor_name in anchors[base_glyph_name]
            and mark_anchor_name not in anchors[mark_glyph_name]
        ):
            base_anchor_offset_set = anchors[base_glyph_name][base_anchor_name]

            anchors[mark_glyph_name][mark_anchor_name] = mark_anchor_offset + (
                base_anchor_offset_set - base_anchor_offset
            )
            logger.info(
                "Added mark anchor '%s' to glyph '%s' from composed glyph '%s'.",
                mark_anchor_name,
                mark_glyph_name,
                composed_glyph_name,
            )
