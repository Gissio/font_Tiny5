"""
bdf2ufo

This module provides functionality to read BDF (Bitmap Distribution Format) files
and extract glyph data, font metadata, and typographic metrics.

(C) 2024-2026 Gissio
License: MIT
"""

import logging
import sys
from typing import Any, Union

import bdflib.reader
from fontTools.agl import UV2AGL
import numpy as np

from .utils import Vec2, combine_strings, filter_name
from .data import SLOPE_FROM_SLANT, WIDTH_CLASSES, WEIGHT_CLASSES

# Constants
DEFAULT_SUPERSCRIPT_SIZE = 0.5
DEFAULT_SUPERSCRIPT_OFFSET_Y_CAP_HEIGHT_RATIO = 0.5
DEFAULT_SUBSCRIPT_SIZE = 0.5
DEFAULT_SUBSCRIPT_OFFSET_Y_CAP_HEIGHT_RATIO = -0.25

# Definitions
logger = logging.getLogger(__name__)


class BDFFont:
    """Represents a font with glyphs and typographic metrics.

    This class reads a BDF (Bitmap Distribution Format) font file and extracts
    glyph data, font metadata, and typographic metrics.

    Attributes:
        glyphs: Dictionary mapping glyph names to Glyph objects.
        names: Dictionary mapping Unicode characters to glyph names.

        family_name: Font family name.
        style_name: Font style name (e.g., "Bold", "Italic").
        font_version: Font version string.
        font_copyright: Copyright information.
        designer: Font designer name.
        designer_url: URL of the font designer.
        manufacturer: Font manufacturer/foundry name.
        manufacturer_url: URL of the manufacturer.
        license: License text.
        license_url: URL of the license.

        boundingbox_min: Minimum x and y coordinates of the font's bounding box.
        boundingbox_max: Maximum x and y coordinates of the font's bounding box.
        ascent: Typographic ascender height.
        descent: Typographic descender depth (negative value).
        cap_height: Height of capital letters.
        x_height: Height of lowercase 'x'.

        underline_position: Position of underline.
        underline_thickness: Thickness of underline.
        strikeout_position: Position of strikeout line.
        strikeout_thickness: Thickness of strikeout line.

        superscript_scale: Horizontal and vertical scale for superscript glyphs.
        superscript_offset: Horizontal and vertical offset for superscript glyphs.

        subscript_scale: Horizontal and vertical scale for subscript glyphs.
        subscript_offset: Horizontal and vertical offset for subscript glyphs.
    """

    def __init__(self) -> None:
        self.glyphs = {}
        self.names = {}

        self.family_name = ""
        self.style_name = ""
        self.font_version = ""
        self.font_copyright = ""
        self.designer = ""
        self.designer_url = ""
        self.manufacturer = ""
        self.manufacturer_url = ""
        self.license = ""
        self.license_url = ""

        self.boundingbox_min = Vec2(0)
        self.boundingbox_max = Vec2(0)
        self.ascent = 0.0
        self.descent = 0.0
        self.cap_height = 0.0
        self.x_height = 0.0

        self.underline_position = 0.0
        self.underline_thickness = 0.0
        self.strikeout_position = 0.0
        self.strikeout_thickness = 0.0

        self.superscript_scale = Vec2(1)
        self.superscript_offset = Vec2(0)

        self.subscript_scale = Vec2(1)
        self.subscript_offset = Vec2(0)

    def load(self, path: str, config: dict) -> None:
        """Load a BDF font file and extract glyph and font metadata.

        Args:
            path: Path to the BDF font file.
            config: Configuration object containing parameters for loading the font.

        Raises:
            Exception: If an error occurs during BDF file reading or processing.
                       The exception is logged and re-raised.
        """

        # Parse BDF font
        with open(path, "rb") as handle:
            bdf = bdflib.reader.read_bdf(handle)

            bdf_name = bdf.name  # pylint: disable=no-member
            bdf_comments = bdf.comments  # pylint: disable=no-member
            bdf_glyphs = bdf.glyphs  # pylint: disable=no-member
            bdf_pt_size = bdf.ptSize  # pylint: disable=no-member

            boundingbox_min = Vec2(sys.maxsize, sys.maxsize)
            boundingbox_max = Vec2(-sys.maxsize, -sys.maxsize)

            cap_height = bdf_pt_size
            x_height = bdf_pt_size

            # Set font glyphs
            for glyph in bdf_glyphs:
                codepoint = glyph.codepoint
                character = chr(codepoint)

                if codepoint in UV2AGL:
                    name = UV2AGL[codepoint]
                else:
                    if codepoint > 0x20 and codepoint < 0x10000:
                        name = f"uni{codepoint:04X}"
                    elif codepoint >= 0x10000:
                        name = f"u{codepoint:06X}"
                    else:
                        name = glyph.name.decode("utf-8")

                if (
                    "notdef_character" in config
                    and character == config["notdef_character"]
                ):
                    name = ".notdef"

                else:
                    if "codepoint_range" in config and not self._match_codepoint(
                        codepoint, config["codepoint_range"]
                    ):
                        continue

                    # Sanitize glyph name
                    if not name[0].isalnum():
                        name = "_" + name

                    name = "".join(
                        [c if (c.isalnum() or c == ".") else "_" for c in name]
                    )

                    while name in self.glyphs:
                        name += "_"

                # Build bitmap
                bitmap = np.zeros((glyph.bbH, glyph.bbW), np.uint8)
                for y in range(glyph.bbH):
                    value = glyph.data[y]
                    for x in range(glyph.bbW):
                        bitmap[y][x] = (value >> (glyph.bbW - x - 1)) & 1

                # Crop bitmap
                if bitmap.any():
                    bitmap_coords = np.argwhere(bitmap)
                    y_min, x_min = bitmap_coords.min(axis=0)
                    y_max, x_max = bitmap_coords.max(axis=0)
                    y_max += 1
                    x_max += 1

                else:
                    y_min, x_min = 0, 0
                    y_max, x_max = 1, 1

                bitmap = bitmap[y_min:y_max, x_min:x_max]

                # Update font bounding box
                glyph_boundingbox_min = Vec2(
                    glyph.bbX + int(x_min),
                    glyph.bbY + int(y_min),
                )
                glyph_boundingbox_max = Vec2(
                    glyph_boundingbox_min.x + bitmap.shape[1],
                    glyph_boundingbox_min.y + bitmap.shape[0],
                )

                boundingbox_min.x = min(boundingbox_min.x, glyph_boundingbox_min.x)
                boundingbox_min.y = min(boundingbox_min.y, glyph_boundingbox_min.y)
                boundingbox_max.x = max(boundingbox_max.x, glyph_boundingbox_max.x)
                boundingbox_max.y = max(boundingbox_max.y, glyph_boundingbox_max.y)

                advance = glyph.advance

                # Build glyph
                glyph = {
                    "character": character,
                    "bitmap": bitmap,
                    "offset": glyph_boundingbox_min,
                    "advance": advance,
                }

                # Update cap_height and x_height based on specific glyphs
                if character == "A":
                    cap_height = bitmap.shape[0]
                elif character == "x":
                    x_height = bitmap.shape[0]

                self.glyphs[name] = glyph
                self.names[character] = name

            # Font variables
            style_name = ""
            setwidth_name = filter_name(
                self._get_bdf_property(bdf, "SETWIDTH_NAME", "")
            )
            style_component = ""
            for name in WIDTH_CLASSES:
                if name.lower() == setwidth_name:
                    style_component = name
                    break
            style_name = combine_strings(style_name, style_component)
            weight_name = filter_name(self._get_bdf_property(bdf, "WEIGHT_NAME", ""))
            style_component = "Regular"
            for name in WEIGHT_CLASSES:
                if name.lower() == weight_name:
                    style_component = name
                    break
            style_name = combine_strings(style_name, style_component)
            slant = filter_name(self._get_bdf_property(bdf, "SLANT", ""))
            if slant in SLOPE_FROM_SLANT:
                style_name = combine_strings(style_name, SLOPE_FROM_SLANT[slant])

            family_name = self._get_bdf_property(
                bdf, "FAMILY_NAME", bdf_name.decode("utf-8")
            )
            font_version = self._get_bdf_property(bdf, "FONT_VERSION", "")
            font_copyright = "\n".join([s.decode("utf-8") for s in bdf_comments])
            font_copyright = self._get_bdf_property(bdf, "COPYRIGHT", font_copyright)
            manufacturer = self._get_bdf_property(bdf, "FOUNDRY", "")

            ascent = self._get_bdf_property(bdf, "FONT_ASCENT", bdf_pt_size)
            descent = -self._get_bdf_property(bdf, "FONT_DESCENT", 0)
            cap_height = self._get_bdf_property(bdf, "CAP_HEIGHT", cap_height)
            x_height = self._get_bdf_property(bdf, "X_HEIGHT", x_height)

            underline_position = self._get_bdf_property(bdf, "UNDERLINE_POSITION", 0)
            underline_thickness = self._get_bdf_property(bdf, "UNDERLINE_THICKNESS", 0)

            strikeout_ascent = self._get_bdf_property(
                bdf, "STRIKEOUT_ASCENT", cap_height / 2
            )
            strikeout_descent = self._get_bdf_property(
                bdf, "STRIKEOUT_DESCENT", -cap_height / 2 + 1
            )
            strikeout_position = strikeout_ascent
            strikeout_thickness = strikeout_ascent + strikeout_descent

            superscript_scale = Vec2(DEFAULT_SUPERSCRIPT_SIZE)
            superscript_offset = Vec2(
                DEFAULT_SUPERSCRIPT_OFFSET_Y_CAP_HEIGHT_RATIO * self.cap_height
            )

            subscript_scale = Vec2(DEFAULT_SUBSCRIPT_SIZE)
            subscript_offset = Vec2(
                DEFAULT_SUBSCRIPT_OFFSET_Y_CAP_HEIGHT_RATIO * self.cap_height
            )

            # Font properties
            self._set_property(config, "style_name", style_name)
            self._set_property(config, "family_name", family_name)
            self._set_property(config, "font_version", font_version)
            self._set_property(config, "font_copyright", font_copyright)
            self._set_property(config, "designer", "")
            self._set_property(config, "designer_url", "")
            self._set_property(config, "manufacturer", manufacturer)
            self._set_property(config, "manufacturer_url", "")
            self._set_property(config, "license", "")
            self._set_property(config, "license_url", "")

            self.boundingbox_min = boundingbox_min
            self.boundingbox_max = boundingbox_max

            self._set_property(config, "ascent", ascent)
            self._set_property(config, "descent", descent)
            self._set_property(config, "cap_height", cap_height)
            self._set_property(config, "x_height", x_height)

            self._set_property(config, "underline_position", underline_position)
            self._set_property(config, "underline_thickness", underline_thickness)
            self._set_property(config, "strikeout_position", strikeout_position)
            self._set_property(config, "strikeout_thickness", strikeout_thickness)

            self._set_property(config, "superscript_scale", superscript_scale)
            self._set_property(config, "superscript_offset", superscript_offset)

            self._set_property(config, "subscript_scale", subscript_scale)
            self._set_property(config, "subscript_offset", subscript_offset)

    def _match_codepoint(self, codepoint: int, codepoint_range: str) -> bool:
        for token in codepoint_range.split(","):
            element = token.split("-", 1)
            if len(element) == 1:
                value = int(element[0], 0)

                if codepoint == value:
                    return True
            else:
                start = int(element[0], 0)
                end = int(element[1], 0)

                if start <= codepoint <= end:
                    return True

        return False

    def _get_bdf_property(
        self, bdf: Any, key: str, default_value: Union[str, int, float]
    ) -> Union[str, int, float]:
        key_bytes = key.encode("utf-8")

        if key_bytes in bdf.properties:
            value = bdf.properties[key_bytes]
            if isinstance(value, int):
                return value
            elif isinstance(value, bytes):
                return value.decode("utf-8")
            else:
                return value

        return default_value

    def _set_property(self, config: Any, key: str, default_value: Any) -> None:
        if key in config:
            if isinstance(default_value, Vec2):
                setattr(self, key, Vec2(config[key]))
            else:
                setattr(self, key, config[key])
        else:
            setattr(self, key, default_value)
