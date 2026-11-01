"""
bdf2ufo

Glyph decomposition and element positions for BDF to UFO font conversion.

(C) 2024-2026 Gissio
License: MIT
"""

import logging

import numpy as np
import unicodedata2 as unicodedata

from .bdf_font import BDFFont
from .data import CUSTOM_DECOMPOSITIONS
from .utils import Vec2, format_unicode_character, format_unicode_characters

# Constants
_MISSING = "missing"
_MISMATCH = "mismatch"

# Definitions
logger = logging.getLogger(__name__)


def build_decomposition(bdf_font: BDFFont) -> dict:
    """Find the glyphs that can be composed from the glyphs of their decomposition.

    A glyph is composed when its bitmap is exactly the union of the bitmaps of
    the characters of its Unicode (or custom) decomposition, at some offsets.

    Args:
        bdf_font: The BDF font object.

    Returns:
        Dictionary mapping glyph names to their components, a list of
        (component glyph name, offset) tuples with the base last.
    """
    components = {}

    for glyph_name, glyph in bdf_font.glyphs.items():
        glyph_character = glyph["character"]

        # Unencoded glyphs have no decomposition
        if glyph_character is None:
            continue

        if glyph_character in CUSTOM_DECOMPOSITIONS:
            decomposition_string = CUSTOM_DECOMPOSITIONS[glyph_character]
        else:
            decomposition_string = unicodedata.decomposition(glyph_character)

        if decomposition_string.startswith("<compat> "):
            decomposition_string = decomposition_string[9:]

        if decomposition_string == "" or decomposition_string.startswith("<"):
            continue

        decomposition = "".join(
            [chr(int(c, 16)) for c in decomposition_string.split() if c != "0020"]
        )

        glyph_components = _decompose_glyph(bdf_font, glyph, decomposition)

        if glyph_components == _MISSING:
            logger.info(
                "%s could be composed from [%s]",
                format_unicode_character(glyph_character),
                format_unicode_characters(decomposition),
            )
            continue

        if glyph_components == _MISMATCH:
            logger.warning(
                "%s cannot be composed from [%s], storing precomposed glyph",
                format_unicode_character(glyph_character),
                format_unicode_characters(decomposition),
            )
            continue

        logger.info(
            "%s composed with [%s]",
            format_unicode_character(glyph_character),
            format_unicode_characters(decomposition),
        )

        components[glyph_name] = glyph_components

    return components


def _decompose_glyph(bdf_font, target_glyph, decomposition, canvas=None):
    """Find offsets at which the decomposition paints the target bitmap.

    Tries every position of the first character's bitmap within the target
    bitmap, then decomposes the rest recursively.

    Returns:
        A list of (component glyph name, offset) tuples with the first
        character last, _MISSING if a character has no glyph, or _MISMATCH.
    """
    target_bitmap = target_glyph["bitmap"]

    if canvas is None:
        canvas = np.zeros(target_bitmap.shape, np.uint8)

    if len(decomposition) == 0:
        return [] if (target_bitmap == canvas).all() else _MISMATCH

    component_character = decomposition[0]
    if component_character not in bdf_font.names:
        return _MISSING

    component_name = bdf_font.names[component_character]
    component_glyph = bdf_font.glyphs[component_name]
    component_bitmap = component_glyph["bitmap"]
    height, width = component_bitmap.shape

    for y in range(target_bitmap.shape[0] - height + 1):
        for x in range(target_bitmap.shape[1] - width + 1):
            painted_canvas = canvas.copy()
            painted_canvas[y : y + height, x : x + width] |= component_bitmap

            glyph_components = _decompose_glyph(
                bdf_font, target_glyph, decomposition[1:], painted_canvas
            )

            if glyph_components == _MISSING:
                return _MISSING

            if isinstance(glyph_components, list):
                component_offset = (
                    target_glyph["offset"] - component_glyph["offset"] + Vec2(x, y)
                )
                glyph_components.append((component_name, component_offset))

                return glyph_components

    return _MISMATCH


def get_pieces(components: dict, glyph_name: str, offset: Vec2 = None) -> list:
    """Resolve a glyph to its non-composed components, innermost base first.

    Args:
        components: Dictionary of glyph components.
        glyph_name: The name of the glyph.
        offset: The offset of the glyph, in pixel units, or None for no offset.

    Returns:
        A list of (glyph name, offset) tuples.
    """
    if offset is None:
        offset = Vec2(0)

    if glyph_name not in components:
        return [(glyph_name, offset)]

    # Decompositions list the base last
    return [
        piece
        for component_name, component_offset in reversed(components[glyph_name])
        for piece in get_pieces(components, component_name, offset + component_offset)
    ]


def get_element_positions(bdf_font: BDFFont, components: dict, glyph_name: str) -> list:
    """Return the position of every element a glyph draws, in pixel units.

    A position repeats when the glyph draws an element there more than once.
    Composed glyphs are resolved down to their bitmaps.

    Args:
        bdf_font: The BDF font object.
        components: Dictionary of glyph components.
        glyph_name: The name of the glyph.

    Returns:
        A list of (x, y) element positions, with repeats.
    """
    positions = []

    for piece_name, offset in get_pieces(components, glyph_name):
        glyph = bdf_font.glyphs[piece_name]
        bitmap = glyph["bitmap"]
        glyph_offset = glyph["offset"] + offset

        positions += [
            (x + int(glyph_offset.x), y + int(glyph_offset.y))
            for y in range(bitmap.shape[0])
            for x in range(bitmap.shape[1])
            if bitmap[y][x]
        ]

    return positions


def get_bitmap(positions: set) -> tuple:
    """Draw element positions into a cropped bitmap.

    Args:
        positions: A set of (x, y) element positions, in pixel units.

    Returns:
        The bitmap and its offset.
    """
    x_min = min(x for x, _y in positions)
    y_min = min(y for _x, y in positions)
    x_max = max(x for x, _y in positions) + 1
    y_max = max(y for _x, y in positions) + 1

    bitmap = np.zeros((y_max - y_min, x_max - x_min), np.uint8)
    for x, y in positions:
        bitmap[y - y_min][x - x_min] = 1

    return bitmap, Vec2(x_min, y_min)
