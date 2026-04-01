"""
bdf2ufo

Glyph decomposition and anchor extraction for BDF to UFO font conversion.

(C) 2024-2026 Gissio
License: MIT
"""

import logging

import numpy as np
import unicodedata2 as unicodedata

from .bdf_font import BDFFont

from .data import CUSTOM_DECOMPOSITIONS
from .utils import Vec2, format_unicode_character, format_unicode_characters

# Definitions
logger = logging.getLogger(__name__)


def build_decomposition(bdf_font: BDFFont) -> dict:
    """
    Decompose glyphs and extract anchors from the given BDF font.

    Args:
        bdf_font (BDFFont): The BDF font object containing glyphs.

            Returns:
        dict: A dictionary mapping glyph names to their components and anchors.
    """
    components = {}

    for glyph_name, glyph in bdf_font.glyphs.items():
        glyph_character = glyph["character"]

        # Decompose
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

        # Get components
        glyph_components = _decompose_glyph(bdf_font, glyph, decomposition)

        if glyph_components == "missing":
            logger.info(
                "%s could be composed from [%s]",
                format_unicode_character(glyph_character),
                format_unicode_characters(decomposition),
            )
            continue

        elif glyph_components == "mismatch":
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
    target_bitmap = target_glyph["bitmap"]

    if canvas is None:
        canvas = np.zeros(target_bitmap.shape, np.uint8)

    if len(decomposition) == 0:
        if (target_bitmap == canvas).all():
            return []

        return "mismatch"

    component_character = decomposition[0]

    if component_character not in bdf_font.names:
        return "missing"

    composed_glyph_size = Vec2(target_bitmap.shape[1], target_bitmap.shape[0])

    component_name = bdf_font.names[component_character]
    component_glyph = bdf_font.glyphs[component_name]
    component_bitmap = component_glyph["bitmap"]
    component_glyph_size = Vec2(component_bitmap.shape[1], component_bitmap.shape[0])

    delta_size = composed_glyph_size - component_glyph_size

    for y in range(delta_size.y + 1):
        for x in range(delta_size.x + 1):
            canvas_copy = canvas.copy()

            if _paint_glyph(
                component_bitmap,
                x,
                y,
                canvas_copy,
            ):
                glyph_components = _decompose_glyph(
                    bdf_font, target_glyph, decomposition[1:], canvas_copy
                )

                if glyph_components == "missing":
                    return glyph_components

                elif isinstance(glyph_components, list):
                    component_offset = (
                        target_glyph["offset"] - component_glyph["offset"] + Vec2(x, y)
                    )

                    glyph_components.append((component_name, component_offset))

                    return glyph_components

    return "mismatch"


def _paint_glyph(src_bitmap, dest_x, dest_y, dest_bitmap):
    h, w = src_bitmap.shape
    y_slice = slice(dest_y, dest_y + h)
    x_slice = slice(dest_x, dest_x + w)

    dest_bitmap[y_slice, x_slice] |= src_bitmap

    return True
