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
    SCRIPTS,
    MARKS,
    CCMP_SOFTDOT_DECOMPOSITION,
    CCMP_SOFTDOT_COMPOSITION,
)
from .utils import (
    Vec2,
    get_style_map_names,
    get_weight_class,
    get_width_class,
)
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
        italic_angle (float): The italic angle, in degrees, of a fully italic master.
        components (dict): A dictionary containing the components of glyphs.
        anchors (dict): A dictionary containing the anchors of glyphs.

        location (dict): The design space location of the font, in design coordinates.
        user_location (dict): The design space location of the font, in user coordinates.
        style_name (str): The style name of the font.
    """

    def __init__(self):
        self.bdf_font = None
        self.ufo_font = None

        self.glyph_offset = Vec2(0)
        self.strike_num = 1
        self.units_per_em = 2048
        self.units_per_element = Vec2(1)
        self.curves = "cubic"  # "quadratic" or "cubic"
        self.italic_angle = 0.0
        self.components = {}
        self.anchors = {}
        self.kerning = {}

        self.location = {}
        self.user_location = {}
        self.style_name = ""

        self.glyph_scale = Vec2(1)

    def setup(
        self,
        bdf_font: BDFFont,
        ufo_config: dict,
        location: dict,
        user_location: dict,
        style_name: str,
    ) -> None:
        """Set up the UFO font structure from a BDF font.

        Args:
            bdf_font: The BDF font object to convert.
            ufo_config: A dictionary containing UFO configuration settings.
            location: The design space location of the font, in design coordinates.
                The glyph geometry is built from these values.
            user_location: The design space location of the font, in user
                coordinates. The OS/2 weight and width classes are set from these values.
            style_name: The style name of the font at this design space location.
        """

        # Configure
        self.bdf_font = bdf_font
        self.ufo_font = ufoLib2.Font()

        self.glyph_offset = ufo_config["glyph_offset"]
        self.strike_num = ufo_config["strike_num"]
        self.units_per_em = ufo_config["units_per_em"]
        self.units_per_element = ufo_config["units_per_element"]
        self.use_element_glyph = ufo_config["use_element_glyph"]
        self.italic_angle = ufo_config["italic_angle"]
        self.components = ufo_config["components"]
        self.anchors = ufo_config["anchors"]
        self.kerning = ufo_config["kerning"]

        self.location = location
        self.user_location = user_location
        self.style_name = style_name

        self.glyph_scale = self.units_per_element * Vec2(self.location["wdth"] / 100, 1)

        # Set font info
        self._set_font_info()

        # Set features
        self._set_features()

        # Set element glyph
        if self.use_element_glyph:
            self._set_element_glyph()

        # Set glyphs
        self._set_glyphs()

        # Flatten components
        self._flatten_components()

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

        # Width and weight class, from the user space location
        width_class = get_width_class(self.user_location["wdth"])
        weight_class = get_weight_class(self.user_location["wght"])

        # Italic angle. UFO italic angles are counter-clockwise, so a forward
        # leaning italic has a negative angle.
        italic_angle = -self.italic_angle * self.location["ital"]
        if italic_angle == 0:
            italic_angle = 0.0

        # Names
        style_map_family_name, style_map_style_name = get_style_map_names(
            self.bdf_font.family_name, self.style_name
        )

        # Version
        version_components = self.bdf_font.font_version.split(";", 2)
        version_components[0] = version_components[0].removeprefix("Version ")
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

        # Set font info
        font_info = self.ufo_font.info

        font_info.familyName = self.bdf_font.family_name
        font_info.styleName = self.style_name
        font_info.styleMapFamilyName = style_map_family_name
        font_info.styleMapStyleName = style_map_style_name
        font_info.versionMajor, font_info.versionMinor = version_majorminor

        font_info.copyright = self.bdf_font.font_copyright
        font_info.unitsPerEm = self.units_per_em
        font_info.italicAngle = italic_angle
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
        # Bit 7 is USE_TYPO_METRICS. Bit 8 is WWS: the name table strings
        # describe a weight/width/slope family on their own, so name IDs 21 and
        # 22 are not needed. split_family_style_names() keeps the subfamily name
        # to a weight optionally followed by "Italic", moving every other style
        # component into the family name, and the WWS names are never set, so
        # the bit always applies. Bits 0 (italic), 5 (bold) and 6 (regular) are
        # derived from styleMapStyleName and must not be listed here.
        font_info.openTypeOS2Selection = [7, 8]
        font_info.openTypeOS2VendorID = "B2UF"
        # Panose: Latin Text, with bProportion set to 9 (Monospaced) for a
        # monospace font.
        panose_proportion = 9 if self.bdf_font.monospace else 0
        font_info.openTypeOS2Panose = [2, 0, 0, panose_proportion, 0, 0, 0, 0, 0, 0]
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

        font_info.postscriptIsFixedPitch = bool(self.bdf_font.monospace)

        font_info.postscriptUnderlineThickness = int(
            self.bdf_font.underline_thickness * self.units_per_element.y
        )
        font_info.postscriptUnderlinePosition = int(
            self.bdf_font.underline_position * self.units_per_element.y
        )

    def _set_features(self) -> None:
        lines = []

        # Properties
        script_tags = []
        script_langtags = []
        for character, (script_tag, script_langtag) in SCRIPTS.items():
            if character in self.bdf_font.names:
                script_tags.append(script_tag)
                script_langtags.append(script_langtag)

        # Set default script and language system
        self.ufo_font.lib["public.openTypeMeta"] = {
            "dlng": script_langtags,
            "slng": script_langtags,
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
        for script_tag in script_tags:
            lines.append(f"languagesystem {script_tag} dflt;")
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

    def _add_element_glyph(self, ufo_glyph, offset: Vec2) -> None:
        # Axes
        width = self.location["wdth"] / 100
        weight = self.location["wght"] / 400
        roundness = self.location["ROND"] / 100
        bleed = self.location["BLED"] / 100

        # Size
        element_size = self.units_per_element * Vec2(width, 1)
        half_size = element_size * Vec2(weight * 0.5)

        # Roundness
        half_size = half_size * Vec2(1 - roundness) + half_size.y * Vec2(roundness)
        corner_radius = Vec2(half_size.y * roundness)

        # Bleed
        outer_right = half_size + Vec2(element_size.x * bleed, 0)
        outer = half_size
        inner_right = outer_right - corner_radius
        inner = outer - corner_radius

        if self.curves == "quadratic":
            tangent_factor = Vec2(math.tan(math.radians(90 / 4)))
            midarc_factor = Vec2(math.cos(math.radians(45)))
            tangent_right = inner_right + corner_radius * tangent_factor
            midarc_right = inner_right + corner_radius * midarc_factor
            tangent = inner + corner_radius * tangent_factor
            midarc = inner + corner_radius * midarc_factor
            element_points = [
                [Vec2(outer_right.x, inner_right.y), "line"],
                [Vec2(outer_right.x, tangent_right.y), "offcurve"],
                [Vec2(midarc_right.x, midarc_right.y), "qcurve"],
                [Vec2(tangent_right.x, outer_right.y), "offcurve"],
                [Vec2(inner_right.x, outer_right.y), "qcurve"],
                [Vec2(-inner.x, outer_right.y), "line"],
                [Vec2(-tangent.x, outer_right.y), "offcurve"],
                [Vec2(-midarc.x, midarc_right.y), "qcurve"],
                [Vec2(-outer.x, tangent_right.y), "offcurve"],
                [Vec2(-outer.x, inner_right.y), "qcurve"],
                [Vec2(-outer.x, -inner_right.y), "line"],
                [Vec2(-outer.x, -tangent_right.y), "offcurve"],
                [Vec2(-midarc.x, -midarc_right.y), "qcurve"],
                [Vec2(-tangent.x, -outer_right.y), "offcurve"],
                [Vec2(-inner.x, -outer_right.y), "qcurve"],
                [Vec2(inner_right.x, -outer_right.y), "line"],
                [Vec2(tangent_right.x, -outer_right.y), "offcurve"],
                [Vec2(midarc_right.x, -midarc_right.y), "qcurve"],
                [Vec2(outer_right.x, -tangent_right.y), "offcurve"],
                [Vec2(outer_right.x, -inner_right.y), "qcurve"],
            ]
        elif self.curves == "cubic":
            tangent_factor = Vec2((4 / 3) * math.tan(math.radians(90 / 4)))
            tangent_right = inner_right + corner_radius * tangent_factor
            tangent = inner + corner_radius * tangent_factor
            element_points = [
                [Vec2(outer_right.x, inner_right.y), "line"],
                [Vec2(outer_right.x, tangent_right.y), "offcurve"],
                [Vec2(tangent_right.x, outer_right.y), "offcurve"],
                [Vec2(inner_right.x, outer_right.y), "curve"],
                [Vec2(-inner.x, outer_right.y), "line"],
                [Vec2(-tangent.x, outer_right.y), "offcurve"],
                [Vec2(-outer.x, tangent_right.y), "offcurve"],
                [Vec2(-outer.x, inner_right.y), "curve"],
                [Vec2(-outer.x, -inner_right.y), "line"],
                [Vec2(-outer.x, -tangent_right.y), "offcurve"],
                [Vec2(-tangent.x, -outer_right.y), "offcurve"],
                [Vec2(-inner.x, -outer_right.y), "curve"],
                [Vec2(inner_right.x, -outer_right.y), "line"],
                [Vec2(tangent_right.x, -outer_right.y), "offcurve"],
                [Vec2(outer_right.x, -tangent_right.y), "offcurve"],
                [Vec2(outer_right.x, -inner_right.y), "curve"],
            ]
        else:
            element_points = []

        ufo_points = []
        for point_offset, point_type in element_points:
            ufo_points.append(
                ufoLib2.objects.Point(offset.x + point_offset.x, offset.y + point_offset.y, point_type)
            )
        ufo_contour = ufoLib2.objects.Contour(ufo_points)

        ufo_glyph.appendContour(ufo_contour)

    def _set_element_glyph(self) -> None:
        element_glyph = self.ufo_font.newGlyph("_")
        self._add_element_glyph(element_glyph, Vec2(0))

    def _set_glyphs(self) -> None:
        for glyph_name, bdf_glyph in self.bdf_font.glyphs.items():
            glyph_character = bdf_glyph["character"]
            glyph_advance = bdf_glyph["advance"]

            ufo_glyph = self.ufo_font.newGlyph(glyph_name)
            ufo_glyph.unicode = ord(glyph_character)
            ufo_glyph.width = int(glyph_advance * self.glyph_scale.x)

            # A composition whose components draw the same element twice would
            # emit duplicate components at identical coordinates, so draw the
            # glyph from its bitmap instead.
            if glyph_name in self.components and not self._has_overlapping_elements(
                glyph_name
            ):
                self._add_components(
                    ufo_glyph, glyph_character, self.components[glyph_name]
                )
            else:
                self._add_bitmap(ufo_glyph, bdf_glyph)

    def _apply_italic(self, offset):
        y = offset.y - 0.5 * self.glyph_scale.y
        angle = self.italic_angle * self.location["ital"]

        italic_offset = Vec2(y * math.tan(math.radians(angle)), 0)

        return offset + italic_offset

    def _apply_jitter(self, offset):
        jitter = self.location["JITT"]

        jitter_offset = Vec2.random(jitter / 1000) * self.units_per_element

        return offset + jitter_offset

    def _get_element_positions(self, glyph_name: str) -> list[tuple[int, int]]:
        """Return the position of every element a glyph draws, in pixel units.

        A position repeats when the glyph draws an element there more than once.
        Composed glyphs are resolved recursively down to their bitmaps.

        The result is expressed in .bdf pixel space, which is shared by every
        master, so it cannot vary across the design space.

        Args:
            glyph_name: The name of the glyph.

        Returns:
            A list of (x, y) element positions, with repeats.
        """
        if glyph_name in self.components:
            return [
                (x + int(component_offset.x), y + int(component_offset.y))
                for component_name, component_offset in self.components[glyph_name]
                for x, y in self._get_element_positions(component_name)
            ]

        bdf_glyph = self.bdf_font.glyphs[glyph_name]
        bitmap = bdf_glyph["bitmap"]
        offset = bdf_glyph["offset"]

        return [
            (x + int(offset.x), y + int(offset.y))
            for y in range(bitmap.shape[0])
            for x in range(bitmap.shape[1])
            if bitmap[y][x]
        ]

    def _has_overlapping_elements(self, glyph_name: str) -> bool:
        """Report whether a composed glyph draws two elements at the same place.

        Args:
            glyph_name: The name of the glyph.

        Returns:
            True if any element position is drawn more than once.
        """
        positions = self._get_element_positions(glyph_name)
        if len(positions) == len(set(positions)):
            return False

        logger.info(
            "Glyph '%s' composes overlapping elements, storing precomposed glyph.",
            glyph_name,
        )

        return True

    def _get_mark_shift(self, character: str) -> float:
        """Return the horizontal nudge, in font units, of a glyph's ink and anchors.

        Marks are drawn in the .bdf aligned to the cell left of the origin, so
        attaching one to a base of the same width yields a GPOS offset of
        exactly (0, 0). That is the correct position, but it is indistinguishable
        from a font with no mark attachment at all, which Fontspector/Shaperglot
        report as an orphaned mark. Nudging every mark one unit left makes the
        offset non-zero without moving the mark by a visible amount.

        The nudge applies to a mark's outline and to its anchors alike, so the
        two cancel and the rendered position never changes. A glyph that embeds
        a mark as a component has no anchor to cancel against, so it must undo
        the component's nudge and apply its own instead.

        Args:
            character: The Unicode character of the glyph.

        Returns:
            The horizontal nudge, in font units.
        """
        return -1 if character in MARKS else 0

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

                        # Italic offset
                        offset = self._apply_italic(offset)

                        # Jitter offset
                        offset = self._apply_jitter(offset)

                        # Fix Fontspector/Shaperglot heuristics
                        offset.x += self._get_mark_shift(bdf_glyph_character)

                        if self.use_element_glyph:
                            ufo_component = ufoLib2.objects.Component("_")
                            ufo_component.transformation = [
                                1,
                                0,
                                0,
                                1,
                                math.floor(offset.x),
                                math.floor(offset.y),
                            ]

                            self._append_component(ufo_glyph, ufo_component)
                        else:
                            self._add_element_glyph(ufo_glyph, offset)

    def _add_components(self, ufo_glyph, glyph_character, glyph_components):
        for component_name, component_offset in glyph_components:
            component_character = self.bdf_font.glyphs[component_name]["character"]

            ufo_component = ufoLib2.objects.Component(component_name)
            offset = component_offset * self.glyph_scale

            # Italic offset
            offset = self._apply_italic(offset)

            # Fix Fontspector/Shaperglot heuristics. The component glyph already
            # carries its own nudge, so undo it and apply the composed glyph's.
            offset.x += self._get_mark_shift(glyph_character) - self._get_mark_shift(
                component_character
            )

            ufo_component.transformation = [
                1,
                0,
                0,
                1,
                math.floor(offset.x),
                math.floor(offset.y),
            ]

            self._append_component(ufo_glyph, ufo_component)

    def _append_component(self, ufo_glyph, ufo_component):
        """Append a component whose offset TrueType must not round to the grid.

        ufo2ft sets ROUND_XY_TO_GRID on every component by default. Hinting
        rasterizers (Windows GDI and DirectWrite) then round each element's
        offset to whole pixels while the element keeps its fractional size,
        which leaves empty pixel rows and columns inside filled areas whenever
        an element spans between 2 and 3 pixels (or 4 and 5, and so on).

        The identifier is the component's index, so the UFO output stays
        deterministic.

        Args:
            ufo_glyph: The glyph to append the component to.
            ufo_component: The component to append.
        """
        ufo_component.identifier = f"component{len(ufo_glyph.components)}"
        ufo_glyph.components.append(ufo_component)

        ufo_glyph.objectLib(ufo_component)["public.truetype.roundOffsetToGrid"] = False

    def _get_flat_components(self, glyph_name, dx, dy):
        """Resolve a component down to glyphs that are not pure composites.

        Args:
            glyph_name: The name of the component's base glyph.
            dx: The component's horizontal offset, in font units.
            dy: The component's vertical offset, in font units.

        Returns:
            A list of (base glyph name, dx, dy) tuples.
        """
        base_glyph = self.ufo_font[glyph_name]
        if not base_glyph.components or base_glyph.contours:
            return [(glyph_name, dx, dy)]

        return [
            flat_component
            for component in base_glyph.components
            for flat_component in self._get_flat_components(
                component.baseGlyph,
                dx + component.transformation.dx,
                dy + component.transformation.dy,
            )
        ]

    def _flatten_components(self):
        """Replace nested components with their referents.

        The build's FlattenComponentsFilter would do this anyway, but the
        components it creates lose their identifiers and with them the
        roundOffsetToGrid setting from _append_component. Flat sources leave
        the filter nothing to do in variable font builds.
        """
        for ufo_glyph in self.ufo_font:
            if not any(
                self.ufo_font[component.baseGlyph].components
                for component in ufo_glyph.components
            ):
                continue

            flat_components = [
                flat_component
                for component in ufo_glyph.components
                for flat_component in self._get_flat_components(
                    component.baseGlyph,
                    component.transformation.dx,
                    component.transformation.dy,
                )
            ]

            ufo_glyph.clearComponents()
            ufo_glyph.lib.pop("public.objectLibs", None)

            for base_glyph_name, dx, dy in flat_components:
                ufo_component = ufoLib2.objects.Component(base_glyph_name)
                ufo_component.transformation = [1, 0, 0, 1, dx, dy]

                self._append_component(ufo_glyph, ufo_component)

    def _set_anchors(self):
        for glyph_name, glyph_anchors in self.anchors.items():
            glyph_character = self.bdf_font.glyphs[glyph_name]["character"]
            glyph = self.ufo_font[glyph_name]

            for anchor_name, anchor_offset in glyph_anchors.items():
                absolute_anchor_offset = anchor_offset + self.glyph_offset
                ufo_offset = absolute_anchor_offset * self.glyph_scale

                # Italic offset
                ufo_offset = self._apply_italic(ufo_offset)

                # Fix Fontspector/Shaperglot heuristics
                ufo_offset.x += self._get_mark_shift(glyph_character)

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
