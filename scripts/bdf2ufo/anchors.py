"""
bdf2ufo

Anchor building for BDF to UFO font conversion.

(C) 2024-2026 Gissio
License: MIT
"""

import logging
import unicodedata

from .bdf_font import BDFFont
from .data import MARKS, BASE_ANCHORS_EXCEPTIONS, DEFAULT_ANCHOR_SCRIPTS
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

    # The letters and marks of some scripts that no composed glyph pairs
    build_default_anchors(bdf_font, anchors)

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

        mark_anchor_offset = _get_mark_anchor_offset(mark_glyph, anchor_name)
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


def build_default_anchors(bdf_font: BDFFont, anchors: dict) -> None:
    """Build the anchors that the composed glyphs do not give, for some scripts.

    In the scripts of DEFAULT_ANCHOR_SCRIPTS, such as Hebrew, any mark can
    follow any letter, while only a few letter and mark pairs have a
    precomposed glyph. For each anchor of the script's marks, one mark serves
    as the reference: the first that has the mark anchor already, or else the
    first mark, which gets the anchor where a composed glyph would place it.
    The other marks without the anchor get it at the same height, and at the
    same horizontal distance from their alignment point (centre, left or right
    edge of their pixels). Each letter without the anchor gets it at that
    height and distance from its own alignment point. A mark thus lands
    aligned with the letter, at the height at which it is drawn.

    Args:
        bdf_font: The BDF font object.
        anchors: Dictionary of glyph anchors, updated in place.
    """
    for ranges in DEFAULT_ANCHOR_SCRIPTS.values():
        script_marks = {}
        script_letters = []

        for glyph_name, glyph in bdf_font.glyphs.items():
            character = glyph["character"]
            if character is None or not any(
                first <= character <= last for first, last in ranges
            ):
                continue

            if character in MARKS:
                anchor_name, _priority = MARKS[character]
                script_marks.setdefault(anchor_name, []).append(glyph_name)
            elif unicodedata.category(character).startswith("L"):
                script_letters.append(glyph_name)

        for anchor_name, mark_glyph_names in script_marks.items():
            mark_anchor_name = f"_{anchor_name}"

            reference_name = next(
                (
                    glyph_name
                    for glyph_name in mark_glyph_names
                    if mark_anchor_name in anchors.get(glyph_name, {})
                ),
                mark_glyph_names[0],
            )
            reference_glyph = bdf_font.glyphs[reference_name]
            reference_anchors = anchors.setdefault(reference_name, {})
            if mark_anchor_name not in reference_anchors:
                reference_anchors[mark_anchor_name] = _get_mark_anchor_offset(
                    reference_glyph, anchor_name
                )
                _log_added_default_anchor("mark", mark_anchor_name, reference_name)

            # The anchor relative to the alignment point of the reference mark
            reference_offset = reference_anchors[mark_anchor_name] - Vec2(
                _get_alignment_x(reference_glyph, anchor_name), 0
            )

            for kind, glyph_names, glyph_anchor_name in (
                ("mark", mark_glyph_names, mark_anchor_name),
                ("base", script_letters, anchor_name),
            ):
                for glyph_name in glyph_names:
                    glyph_anchors = anchors.setdefault(glyph_name, {})
                    if glyph_anchor_name in glyph_anchors:
                        continue

                    glyph = bdf_font.glyphs[glyph_name]
                    glyph_anchors[glyph_anchor_name] = (
                        Vec2(_get_alignment_x(glyph, anchor_name), 0)
                        + reference_offset
                    )
                    _log_added_default_anchor(kind, glyph_anchor_name, glyph_name)


def _get_mark_anchor_offset(mark_glyph: dict, anchor_name: str) -> Vec2:
    """Return the position of a mark's anchor, where it touches its base.

    Args:
        mark_glyph: The BDF glyph of the mark.
        anchor_name: The anchor name, without the leading underscore.

    Returns:
        The anchor position, in pixels.
    """
    mark_glyph_size = Vec2(mark_glyph["bitmap"].shape[1], mark_glyph["bitmap"].shape[0])
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

    return mark_glyph["offset"] + anchor_offset


def _get_alignment_x(glyph: dict, anchor_name: str) -> int:
    """Return the horizontal point of a glyph that default anchors align.

    It is the left or right edge of the glyph's pixels for anchors named
    "...Left" or "...Right", and their centre otherwise, rounded as in
    _get_mark_anchor_offset.

    Args:
        glyph: The BDF glyph.
        anchor_name: The anchor name, without the leading underscore.

    Returns:
        The horizontal position, in pixels.
    """
    left = glyph["offset"].x
    width = glyph["bitmap"].shape[1]
    if anchor_name.endswith("Left"):
        return left
    if anchor_name.endswith("Right"):
        return left + width
    return left + int(width / 2)


def _log_added_default_anchor(kind: str, anchor_name: str, glyph_name: str) -> None:
    logger.info("Added default %s anchor '%s' to glyph '%s'.", kind, anchor_name, glyph_name)


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
