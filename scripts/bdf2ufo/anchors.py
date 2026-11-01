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

    # Marks of a lower priority set their anchors first
    for priority in sorted({priority for _name, priority in MARKS.values()}):
        build_anchors_with_priority(bdf_font, components, anchors, priority)

    return anchors


def build_custom_anchors(bdf_font: BDFFont, custom_anchors: dict) -> dict:
    """Build custom anchors from the provided dictionary.

    Args:
        bdf_font: The BDF font object.
        custom_anchors: Dictionary of custom anchors, keyed by character or by
            glyph name (for unencoded glyphs such as "x.sc").

    Returns:
        Dictionary of processed custom anchors.

    Raises:
        ValueError: If a glyph with custom anchors is not in the font.
    """
    anchors = {}
    if custom_anchors is None:
        return anchors

    for glyph_key, glyph_anchor in custom_anchors.items():
        if glyph_key in bdf_font.names:
            glyph_name = bdf_font.names[glyph_key]
        elif glyph_key in bdf_font.glyphs:
            glyph_name = glyph_key
        else:
            raise ValueError(f"Custom anchors for missing glyph '{glyph_key}'")

        anchors[glyph_name] = {}
        for anchor_name, anchor_offset in glyph_anchor.items():
            anchors[glyph_name][anchor_name] = Vec2(anchor_offset)

    return anchors


def build_anchors_with_priority(
    bdf_font: BDFFont, components: dict, anchors: dict, priority: int
) -> None:
    """Build the anchors of the marks of one priority from composed glyphs.

    Every glyph composed from a base and a mark places a base anchor on the
    base and a mark anchor on the mark, where the mark sits in the composed
    glyph. An anchor that is set already is kept, and the other one is placed
    relative to it.

    Args:
        bdf_font: The BDF font object.
        components: Dictionary of glyph components.
        anchors: Dictionary of glyph anchors, updated in place.
        priority: The priority of the marks to build anchors for.
    """
    for composed_glyph_name, composed_glyph_components in components.items():
        # Composed glyphs with a mark and a base only
        if len(composed_glyph_components) != 2:
            continue

        (mark_glyph_name, mark_component_offset), (
            base_glyph_name,
            base_component_offset,
        ) = composed_glyph_components

        base_glyph_character = bdf_font.glyphs[base_glyph_name]["character"]
        mark_glyph = bdf_font.glyphs[mark_glyph_name]
        mark_glyph_character = mark_glyph["character"]

        if base_glyph_character in BASE_ANCHORS_EXCEPTIONS:
            continue

        if base_glyph_character in MARKS or mark_glyph_character not in MARKS:
            continue

        anchor_name, anchor_priority = MARKS[mark_glyph_character]
        if anchor_priority != priority:
            continue

        mark_anchor_name = f"_{anchor_name}"

        base_anchors = anchors.setdefault(base_glyph_name, {})
        mark_anchors = anchors.setdefault(mark_glyph_name, {})

        # The anchor position within the mark bitmap
        mark_glyph_size = Vec2(
            mark_glyph["bitmap"].shape[1], mark_glyph["bitmap"].shape[0]
        )
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

        mark_anchor_offset = mark_glyph["offset"] + anchor_offset
        base_anchor_offset = (
            mark_anchor_offset + mark_component_offset - base_component_offset
        )

        has_mark_anchor = mark_anchor_name in mark_anchors

        if anchor_name not in base_anchors:
            if has_mark_anchor:
                base_anchor_offset += mark_anchors[mark_anchor_name] - mark_anchor_offset

            base_anchors[anchor_name] = base_anchor_offset
            _log_added_anchor("base", anchor_name, base_glyph_name, composed_glyph_name)

        if not has_mark_anchor:
            mark_anchors[mark_anchor_name] = mark_anchor_offset + (
                base_anchors[anchor_name] - base_anchor_offset
            )
            _log_added_anchor(
                "mark", mark_anchor_name, mark_glyph_name, composed_glyph_name
            )


def _log_added_anchor(
    kind: str, anchor_name: str, glyph_name: str, composed_glyph_name: str
) -> None:
    logger.info(
        "Added %s anchor '%s' to glyph '%s' from composed glyph '%s'.",
        kind,
        anchor_name,
        glyph_name,
        composed_glyph_name,
    )
