"""
bdf2ufo

This module provides functionality to convert font data into UFO (Unified Font Object) format.

(C) 2024-2026 Gissio
License: MIT
"""

import logging
import math
from pathlib import Path

import ufoLib2

from .data import (
    WIDTH_CLASSES,
    WEIGHT_CLASSES,
    MARKS,
    CCMP_SOFTDOT_DECOMPOSITION,
    CCMP_SOFTDOT_COMPOSITION,
)
from .utils import Vec2, get_style_map_style_name
from .bdf_font import BDFFont


# Definitions
logger = logging.getLogger(__name__)


class UFOFont:
    """A class representing a UFO font being built from a BDF font.

    This class is responsible for setting up the UFO font structure, adding glyphs and anchors,
    and writing the final UFO files.

    Attributes:
        ufo_font (ufoLib2.Font): The UFO font object being built.

        glyph_offset (Vec2): The offset of glyphs in the X and Y directions.
        strike_num (int): The number of strikes to use for each glyph.
        units_per_em (int): The number of units per em in the UFO font.
        units_per_element (Vec2): The number of units per element in the X and Y directions.
        components (dict): A dictionary containing the components of glyphs.
        anchors (dict): A dictionary containing the anchors of glyphs.

        location (dict): A dictionary containing the location of the font in the design space.
    """

    def __init__(self):
        self.bdf_font = None
        self.ufo_font = None

        self.glyph_offset = Vec2(0)
        self.strike_num = 1
        self.units_per_em = 2048
        self.units_per_element = Vec2(1)
        self.curves = "cubic"  # "quadratic" or "cubic"
        self.components = {}
        self.anchors = {}
        self.kerning = {}

        self.location = {}

        self.glyph_scale = Vec2(1)

    def setup(self, bdf_font: BDFFont, ufo_config: dict, location: dict) -> None:
        """Set up the UFO font structure from a BDF font.

        Args:
            bdf_font: The BDF font object to convert.
            ufo_config: A dictionary containing UFO configuration settings.
            location: A dictionary containing the location of the font in the design space.
        """

        # Configure
        self.bdf_font = bdf_font
        self.ufo_font = ufoLib2.Font()

        self.glyph_offset = ufo_config["glyph_offset"]
        self.strike_num = ufo_config["strike_num"]
        self.units_per_em = ufo_config["units_per_em"]
        self.units_per_element = ufo_config["units_per_element"]
        self.components = ufo_config["components"]
        self.anchors = ufo_config["anchors"]
        self.kerning = ufo_config["kerning"]

        self.location = location

        self.glyph_scale = self.units_per_element * Vec2(self.location["wdth"] / 100, 1)

        # Set font info
        self._set_font_info()

        # Set features
        self._set_features()

        # Set element glyph
        self._set_element_glyph()

        # Set glyphs
        self._set_glyphs()

        # Set anchors
        self._set_anchors()

        # Set kerning
        self._set_kerning()

    def save(self, ufo_path: Path) -> None:
        """Save the UFO font to the specified path.

        Args:
            ufo_path: The Path object specifying where to write the UFO font.
        """
        self.ufo_font.save(ufo_path, overwrite=True, validate=False)

    def _set_font_info(self) -> None:
        # Ascenders and descenders
        line_ascender = self.bdf_font.ascent * self.units_per_element.y
        line_descender = self.bdf_font.descent * self.units_per_element.y
        line_height = line_ascender - line_descender

        descender = line_descender - int((self.units_per_em - line_height) / 2)
        ascender = self.units_per_em + descender

        # Width and weight class
        width_class = 5
        weight_class = 400
        for style_component in self.bdf_font.style_name.split(" "):
            if style_component in WIDTH_CLASSES:
                width_class = WIDTH_CLASSES[style_component]
            if style_component in WEIGHT_CLASSES:
                weight_class = WEIGHT_CLASSES[style_component]

        # Version
        version_components = self.bdf_font.font_version.split(";", 2)
        if version_components[0].startswith("Version "):
            version_components[0] = version_components[8:]
        font_version = "Version " + ";".join(version_components)

        version_number_components = version_components[0].split(".")
        version_majorminor = (1, 0)
        if len(version_number_components) == 2:
            try:
                version_majorminor = (
                    int(version_number_components[0]),
                    int(version_number_components[1]),
                )
            except ValueError:
                pass

        # gasp table
        gasp_table = [
            {
                "rangeMaxPPEM": 16,
                "rangeGaspBehavior": [1, 3],
            },
            {
                "rangeMaxPPEM": 65535,
                "rangeGaspBehavior": [0, 1, 2, 3],
            },
        ]

        # Set font info
        font_info = self.ufo_font.info

        font_info.familyName = self.bdf_font.family_name
        font_info.styleName = self.bdf_font.style_name
        font_info.styleMapFamilyName = self.bdf_font.family_name
        font_info.styleMapStyleName = get_style_map_style_name(self.bdf_font.style_name)
        font_info.versionMajor, font_info.versionMinor = version_majorminor

        font_info.copyright = self.bdf_font.font_copyright
        font_info.unitsPerEm = self.units_per_em
        font_info.descender = descender
        font_info.xHeight = self.bdf_font.x_height * self.units_per_element.y
        font_info.capHeight = self.bdf_font.cap_height * self.units_per_element.y
        font_info.ascender = ascender

        font_info.guidelines = []

        font_info.openTypeHheaAscender = line_ascender
        font_info.openTypeHheaDescender = line_descender
        font_info.openTypeHheaLineGap = 0

        font_info.openTypeNameDesigner = self.bdf_font.designer
        font_info.openTypeNameDesignerURL = self.bdf_font.designer_url
        font_info.openTypeNameManufacturer = self.bdf_font.manufacturer
        font_info.openTypeNameManufacturerURL = self.bdf_font.manufacturer_url
        font_info.openTypeNameLicense = self.bdf_font.license
        font_info.openTypeNameLicenseURL = self.bdf_font.license_url
        font_info.openTypeNameVersion = font_version

        font_info.openTypeOS2WidthClass = width_class
        font_info.openTypeOS2WeightClass = weight_class
        font_info.openTypeOS2Selection = [7]
        font_info.openTypeOS2VendorID = "B2UF"
        font_info.openTypeOS2Panose = [2, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        font_info.openTypeOS2FamilyClass = [0, 0]
        font_info.openTypeOS2TypoAscender = font_info.openTypeHheaAscender
        font_info.openTypeOS2TypoDescender = font_info.openTypeHheaDescender
        font_info.openTypeOS2TypoLineGap = font_info.openTypeHheaLineGap
        font_info.openTypeOS2WinAscent = max(
            self.bdf_font.boundingbox_max.y * self.units_per_element.y, 0
        )
        font_info.openTypeOS2WinDescent = max(
            -self.bdf_font.boundingbox_min.y * self.units_per_element.y, 0
        )
        font_info.openTypeOS2Type = []

        font_info.openTypeOS2SubscriptXSize = int(
            self.bdf_font.subscript_scale.x * self.units_per_em
        )
        font_info.openTypeOS2SubscriptYSize = int(
            self.bdf_font.subscript_scale.y * self.units_per_em
        )
        font_info.openTypeOS2SubscriptXOffset = int(
            self.bdf_font.subscript_offset.x * self.units_per_element.x
        )
        font_info.openTypeOS2SubscriptYOffset = int(
            self.bdf_font.subscript_offset.y * self.units_per_element.y
        )
        font_info.openTypeOS2SuperscriptXSize = int(
            self.bdf_font.superscript_scale.x * self.units_per_em
        )
        font_info.openTypeOS2SuperscriptYSize = int(
            self.bdf_font.superscript_scale.y * self.units_per_em
        )
        font_info.openTypeOS2SuperscriptXOffset = int(
            self.bdf_font.superscript_offset.x * self.units_per_element.x
        )
        font_info.openTypeOS2SuperscriptYOffset = int(
            self.bdf_font.superscript_offset.y * self.units_per_element.y
        )

        font_info.openTypeOS2StrikeoutSize = int(
            self.bdf_font.strikeout_thickness * self.units_per_element.y
        )
        font_info.openTypeOS2StrikeoutPosition = int(
            self.bdf_font.strikeout_position * self.units_per_element.y
        )

        font_info.postscriptUnderlineThickness = int(
            self.bdf_font.underline_thickness * self.units_per_element.y
        )
        font_info.postscriptUnderlinePosition = int(
            self.bdf_font.underline_position * self.units_per_element.y
        )

        font_info.openTypeGaspRangeRecords = gasp_table

    def _set_features(self) -> None:
        lines = []

        # Properties
        languages = []
        if "A" in self.bdf_font.names:
            languages.append("latn")
        if "А" in self.bdf_font.names:
            languages.append("cyrl")
        if "Α" in self.bdf_font.names:
            languages.append("grek")
        if "\u4e2d" in self.bdf_font.names:
            languages.append("hani")
        if "\uac00" in self.bdf_font.names:
            languages.append("hang")

        # Set default script and language system
        self.ufo_font.lib["public.openTypeMeta"] = {
            "dlng": languages,
            "slng": languages,
        }
           
        # Define classes
        all_bases = []
        all_marks = []
        top_marks = []
        for glyph_name, glyph_anchors in self.anchors.items():
            glyph_character = self.bdf_font.glyphs[glyph_name]["character"]

            if glyph_character not in MARKS:
                all_bases.append(glyph_name)
            else:
                for anchor_name, _anchor_offset in glyph_anchors.items():
                    if anchor_name == "_top":
                        top_marks.append(glyph_name)

        for glyph_name, glyph in self.bdf_font.glyphs.items():
            glyph_character = glyph["character"]

            if glyph_character in MARKS:
                all_marks.append(glyph_name)

        lines.append(f"@all_bases = [{' '.join(all_bases)}];")
        lines.append(f"@all_marks = [{' '.join(all_marks)}];")
        lines.append(f"@top_marks = [{' '.join(top_marks)}];")
        lines.append("")

        # Set default language systems
        lines.append("languagesystem DFLT dflt;")
        for language in languages:
            lines.append(f"languagesystem {language} dflt;")
        lines.append("")

        # Define ccmp feature
        i_decomposition_rules = {}
        for source_name, target_name in CCMP_SOFTDOT_DECOMPOSITION.items():
            if source_name in self.bdf_font.names and all(
                target_character in self.bdf_font.names
                for target_character in target_name
            ):
                source_name = self.bdf_font.names[source_name]
                target_names = [
                    self.bdf_font.names[target_character]
                    for target_character in target_name
                ]

                i_decomposition_rules[source_name] = target_names

        softdot_rules = {}
        for source_name, target_character in CCMP_SOFTDOT_COMPOSITION.items():
            if (
                source_name in self.bdf_font.names
                and target_character in self.bdf_font.names
            ):
                source_name = self.bdf_font.names[source_name]
                target_name = self.bdf_font.names[target_character]

                softdot_rules[source_name] = target_name

        lines.append("feature ccmp {")

        if len(i_decomposition_rules) > 0:
            lines.append("    lookup i_decomposition {")
            for source_name, target_name in i_decomposition_rules.items():
                lines.append(f"        sub {source_name} by {' '.join(target_name)};")
            lines.append("    } i_decomposition;")
            lines.append("")

        if len(softdot_rules) > 0:
            lines.append("    lookup softdot {")
            lines.append("        lookupflag UseMarkFilteringSet @top_marks;")
            for source_name, target_name in softdot_rules.items():
                lines.append(f"        sub {source_name}' @top_marks by {target_name};")
            lines.append("    } softdot;")

        lines.append("} ccmp;")
        lines.append("")

        # Define GDEF table
        lines.append("table GDEF {")
        lines.append("    GlyphClassDef @all_bases, [], @all_marks, [];")
        lines.append("} GDEF;")
        lines.append("")

        # Set features
        self.ufo_font.features.text = "\n".join(lines)

    def _set_element_glyph(self) -> None:
        size = self.units_per_element * Vec2(self.location["wght"] / 400)
        halfsize = size * Vec2(0.5)
        radius = halfsize * Vec2(self.location["ROND"] / 100)

        outer = halfsize + Vec2(
            (self.units_per_element.x - halfsize.x) * self.location["BLED"] / 100, 0
        )
        inner = outer - radius

        if self.curves == "quadratic":
            tangent = inner + radius * Vec2(math.tan(math.radians(90 / 4)))
            midarc = inner + radius * Vec2(math.cos(math.radians(45)))
            element_points = [
                [Vec2(outer.x, inner.y), "line"],
                [Vec2(outer.x, tangent.y), "offcurve"],
                [Vec2(midarc.x, midarc.y), "qcurve"],
                [Vec2(tangent.x, outer.y), "offcurve"],
                [Vec2(inner.x, outer.y), "qcurve"],
                [Vec2(-inner.x, outer.y), "line"],
                [Vec2(-tangent.x, outer.y), "offcurve"],
                [Vec2(-midarc.x, midarc.y), "qcurve"],
                [Vec2(-outer.x, tangent.y), "offcurve"],
                [Vec2(-outer.x, inner.y), "qcurve"],
                [Vec2(-outer.x, -inner.y), "line"],
                [Vec2(-outer.x, -tangent.y), "offcurve"],
                [Vec2(-midarc.x, -midarc.y), "qcurve"],
                [Vec2(-tangent.x, -outer.y), "offcurve"],
                [Vec2(-inner.x, -outer.y), "qcurve"],
                [Vec2(inner.x, -outer.y), "line"],
                [Vec2(tangent.x, -outer.y), "offcurve"],
                [Vec2(midarc.x, -midarc.y), "qcurve"],
                [Vec2(outer.x, -tangent.y), "offcurve"],
                [Vec2(outer.x, -inner.y), "qcurve"],
            ]
        elif self.curves == "cubic":
            tangent = inner + radius * Vec2((4 / 3) * math.tan(math.radians(90 / 4)))
            element_points = [
                [Vec2(outer.x, inner.y), "line"],
                [Vec2(outer.x, tangent.y), "offcurve"],
                [Vec2(tangent.x, outer.y), "offcurve"],
                [Vec2(inner.x, outer.y), "curve"],
                [Vec2(-inner.x, outer.y), "line"],
                [Vec2(-tangent.x, outer.y), "offcurve"],
                [Vec2(-outer.x, tangent.y), "offcurve"],
                [Vec2(-outer.x, inner.y), "curve"],
                [Vec2(-outer.x, -inner.y), "line"],
                [Vec2(-outer.x, -tangent.y), "offcurve"],
                [Vec2(-tangent.x, -outer.y), "offcurve"],
                [Vec2(-inner.x, -outer.y), "curve"],
                [Vec2(inner.x, -outer.y), "line"],
                [Vec2(tangent.x, -outer.y), "offcurve"],
                [Vec2(outer.x, -tangent.y), "offcurve"],
                [Vec2(outer.x, -inner.y), "curve"],
            ]
        else:
            element_points = []

        ufo_points = []
        for point_offset, point_type in element_points:
            ufo_points.append(
                ufoLib2.objects.Point(point_offset.x, point_offset.y, point_type)
            )
        ufo_contour = ufoLib2.objects.Contour(ufo_points)

        ufo_glyph = self.ufo_font.newGlyph("_")
        ufo_glyph.appendContour(ufo_contour)

    def _set_glyphs(self) -> None:
        for glyph_name, bdf_glyph in self.bdf_font.glyphs.items():
            glyph_character = bdf_glyph["character"]
            glyph_advance = bdf_glyph["advance"]

            ufo_glyph = self.ufo_font.newGlyph(glyph_name)
            ufo_glyph.unicode = ord(glyph_character)
            ufo_glyph.width = int(glyph_advance * self.glyph_scale.x)

            if glyph_name in self.components:
                self._add_components(ufo_glyph, self.components[glyph_name])
            else:
                self._add_bitmap(ufo_glyph, bdf_glyph)

    def _apply_slant(self, offset):
        y = offset.y - 0.5 * self.glyph_scale.y
        slant = -self.location["slnt"]

        slant_offset = Vec2(y * math.tan(slant * math.pi / 180), 0)

        return offset + slant_offset

    def _apply_jitter(self, offset):
        jitter = self.location["JITT"]

        jitter_offset = Vec2.random(jitter / 1000) * self.units_per_element

        return offset + jitter_offset

    def _add_bitmap(self, ufo_glyph, bdf_glyph):
        strike_num = self.strike_num

        bdf_glyph_character = bdf_glyph["character"]
        bdf_glyph_bitmap = bdf_glyph["bitmap"]
        bdf_glyph_offset = self.glyph_offset + bdf_glyph["offset"]

        for y in range(bdf_glyph_bitmap.shape[0]):
            for x in range(bdf_glyph_bitmap.shape[1]):
                for strike_index in range(strike_num):
                    if bdf_glyph_bitmap[y][x]:
                        offset = (
                            Vec2(x, y)
                            + Vec2(0.5)
                            + bdf_glyph_offset
                            + Vec2(0, -0.5 * strike_index)
                        ) * self.glyph_scale

                        # Slant offset
                        offset = self._apply_slant(offset)

                        # Jitter offset
                        offset = self._apply_jitter(offset)

                        # Fix Fontspector/Shaperglot heuristics
                        if bdf_glyph_character in MARKS:
                            offset.x -= 1

                        ufo_component = ufoLib2.objects.Component("_")
                        ufo_component.transformation = [
                            1,
                            0,
                            0,
                            1,
                            math.floor(offset.x),
                            math.floor(offset.y),
                        ]

                        ufo_glyph.components.append(ufo_component)

    def _add_components(self, ufo_glyph, glyph_components):
        for component_name, component_offset in glyph_components:
            component_character = self.bdf_font.glyphs[component_name]["character"]

            ufo_component = ufoLib2.objects.Component(component_name)
            offset = component_offset * self.glyph_scale

            # Slant offset
            offset = self._apply_slant(offset)

            # Fix Fontspector/Shaperglot heuristics
            if component_character in MARKS:
                offset.x -= 1

            if offset != (0, 0):
                ufo_component.transformation = [
                    1,
                    0,
                    0,
                    1,
                    math.floor(offset.x),
                    math.floor(offset.y),
                ]

            ufo_glyph.components.append(ufo_component)

    def _set_anchors(self):
        for glyph_name, glyph_anchors in self.anchors.items():
            glyph_character = self.bdf_font.glyphs[glyph_name]["character"]
            glyph = self.ufo_font[glyph_name]

            for anchor_name, anchor_offset in glyph_anchors.items():
                absolute_anchor_offset = anchor_offset + self.glyph_offset
                ufo_offset = absolute_anchor_offset * self.units_per_element

                # Slant offset
                ufo_offset = self._apply_slant(ufo_offset)

                # Fix Fontspector/Shaperglot heuristics
                if glyph_character in MARKS:
                    ufo_offset.x -= 1

                ufo_anchor = ufoLib2.objects.Anchor(
                    math.floor(ufo_offset.x),
                    math.floor(ufo_offset.y),
                    anchor_name,
                )

                glyph.anchors.append(ufo_anchor)

    def _set_kerning(self):
        if self.kerning is None:
            return

        # Build kerning groups
        left_groups = {}
        right_groups = {}

        group_index = 1
        for left_characters, right_characters, value in self.kerning:
            # Left group
            if len(left_characters) > 1:
                if left_characters in left_groups:
                    left_group_name = left_groups[left_characters]
                else:
                    left_group_name = f"public.kern1.group{group_index}"
                    self.ufo_font.groups[left_group_name] = [
                        self.bdf_font.names[c] for c in left_characters
                    ]
                    group_index += 1
            elif len(left_characters) == 1:
                left_group_name = self.bdf_font.names[left_characters[0]]

            if len(left_characters) > 0:
                left_groups[left_characters] = left_group_name

            # Right group
            if len(right_characters) > 1:
                if right_characters in right_groups:
                    right_group_name = right_groups[right_characters]
                else:
                    right_group_name = f"public.kern2.group{group_index}"
                    self.ufo_font.groups[right_group_name] = [
                        self.bdf_font.names[c] for c in right_characters
                    ]
                    group_index += 1
            elif len(right_characters) == 1:
                right_group_name = self.bdf_font.names[right_characters[0]]

            if len(right_characters) > 0:
                right_groups[right_characters] = right_group_name

        # Add kerning
        for left_characters, right_characters, value in self.kerning:
            left_group_name = left_groups[left_characters]
            right_group_name = right_groups[right_characters]

            self.ufo_font.kerning[(left_group_name, right_group_name)] = (
                value * self.units_per_element.x
            )
