"""
bdf2ufo

This module provides functionality to convert font data into UFO (Unified Font Object) format.

(C) 2024-2026 Gissio
License: MIT
"""

import logging
import math
from pathlib import Path

import numpy as np
import ufoLib2

from .data import (
    SCRIPTS,
    MARKS,
    MAX_JITTER_OFFSET,
    SMALL_CAPS_DOTTED_I_LANGUAGES,
)
from .alternates import get_alternate_features
from .ligatures import get_ligature_feature
from .utils import (
    is_mark,
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
        self.use_element_glyph = True
        self.curves = "cubic"  # "quadratic" or "cubic"
        self.italic_angle = 0.0
        self.italic_slope = 0.0
        self.jitter_enabled = False
        self.components = {}
        self.precomposed = set()
        self.anchors = {}
        self.ccmp = {}
        self.small_caps = {}
        self.ligatures = {}
        self.alternates = {}
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
        self.jitter_enabled = ufo_config["jitter_enabled"]
        self.components = ufo_config["components"]
        self.precomposed = ufo_config["precomposed"]
        self.anchors = ufo_config["anchors"]
        self.ccmp = ufo_config["ccmp"]
        self.small_caps = ufo_config["small_caps"]
        self.ligatures = ufo_config["ligatures"]
        self.alternates = ufo_config["alternates"]
        self.kerning = ufo_config["kerning"]

        self.location = location
        self.user_location = user_location
        self.style_name = style_name

        self.glyph_scale = self.units_per_element * Vec2(self.location["wdth"] / 100, 1)
        self.italic_slope = math.tan(math.radians(self.italic_angle * self.location["ital"]))

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
        # The JITT axis moves elements by less than MAX_JITTER_OFFSET elements
        # in any direction, at any location of the design space. The glyph
        # offsets are also rounded down to whole font units, which moves an
        # element at most one unit further down.
        jitter = (
            MAX_JITTER_OFFSET * self.units_per_element.y if self.jitter_enabled else 0
        )
        rounding = 1 if self.jitter_enabled else 0
        top = self.bdf_font.boundingbox_max.y * self.units_per_element.y
        bottom = -self.bdf_font.boundingbox_min.y * self.units_per_element.y
        font_info.openTypeOS2WinAscent = math.ceil(max(top + jitter, 0))
        font_info.openTypeOS2WinDescent = math.ceil(max(bottom + jitter + rounding, 0))
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

        # Scripts of the font
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

            if not is_mark(glyph_character):
                all_bases.append(glyph_name)
            else:
                for anchor_name, _anchor_offset in glyph_anchors.items():
                    if anchor_name == "_top":
                        top_marks.append(glyph_name)

        for glyph_name, glyph in self.bdf_font.glyphs.items():
            glyph_character = glyph["character"]

            if is_mark(glyph_character):
                all_marks.append(glyph_name)

        lines.append(f"@all_bases = [{' '.join(all_bases)}];")
        lines.append(f"@all_marks = [{' '.join(all_marks)}];")
        lines.append(f"@top_marks = [{' '.join(top_marks)}];")
        lines.append("")

        # Set default language systems
        lines.append("languagesystem DFLT dflt;")
        for script_tag in script_tags:
            lines.append(f"languagesystem {script_tag} dflt;")

        # The languages with a dotted small cap i get a language system of their
        # own, which every feature joins. Otherwise only smcp would list it, and
        # text in these languages would lose ccmp and c2sc.
        dotted_i = self.small_caps.get("dotted_i", {}) if "latn" in script_tags else {}
        dotted_i_languages = SMALL_CAPS_DOTTED_I_LANGUAGES if dotted_i else ()
        for language_tag in dotted_i_languages:
            lines.append(f"languagesystem latn {language_tag};")
        lines.append("")

        # Define ccmp feature
        i_decomposition_rules = self.ccmp["decomposition"]
        softdot_rules = self.ccmp["softdot"]

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

        # Define smcp and c2sc features, with one lookup per script. Latin
        # also applies to the default script.
        for feature_tag in ("smcp", "c2sc"):
            script_substitutions = {
                script_tag: substitutions
                for script_tag, substitutions in self.small_caps.get(
                    feature_tag, {}
                ).items()
                if script_tag in script_tags and len(substitutions) > 0
            }
            if len(script_substitutions) == 0:
                continue

            # The dotted small cap of "i" in the languages that dot their
            # capital I. Its lookup comes before the Latin one, so that it
            # substitutes "i" first.
            smcp_dotted_i = dotted_i if feature_tag == "smcp" else {}

            if smcp_dotted_i:
                lines.append("lookup smcp_dotted_i {")
                for source_name, target_name in smcp_dotted_i.items():
                    lines.append(f"    sub {source_name} by {target_name};")
                lines.append("} smcp_dotted_i;")
                lines.append("")

            lines.append(f"feature {feature_tag} {{")
            for script_tag, substitutions in script_substitutions.items():
                lookup_name = f"{feature_tag}_{script_tag}"

                if script_tag == "latn":
                    lines.append("    script DFLT;")
                else:
                    lines.append(f"    script {script_tag};")

                lines.append(f"    lookup {lookup_name} {{")
                for source_name, target_name in substitutions.items():
                    lines.append(f"        sub {source_name} by {target_name};")
                lines.append(f"    }} {lookup_name};")

                if script_tag == "latn":
                    lines.append(f"    script {script_tag};")
                    lines.append(f"    lookup {lookup_name};")

                    # A feature that names a script only applies in the language
                    # systems it lists, so these list them as well
                    for language_tag in dotted_i_languages:
                        lines.append(f"    language {language_tag};")
                        if smcp_dotted_i:
                            lines.append("    lookup smcp_dotted_i;")
            lines.append(f"}} {feature_tag};")
            lines.append("")

        # Define calt feature with the ligatures
        lines += get_ligature_feature(self.ligatures)

        # Define the features of the alternates, such as zero
        lines += get_alternate_features(self.alternates)

        # Define GDEF table
        lines.append("table GDEF {")
        lines.append("    GlyphClassDef @all_bases, [], @all_marks, [];")
        lines.append("} GDEF;")
        lines.append("")

        # Set features
        self.ufo_font.features.text = "\n".join(lines)

    def _get_element_sizes(self) -> tuple:
        """Return the sizes of an element at this location, in font units.

        Returns:
            The half size of the element, its corner radius, and the half size
            of its right side, which the bleed extends.
        """
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

        return half_size, corner_radius, outer_right

    def get_overlapping_glyph_names(self) -> set:
        """Return the glyphs whose elements overlap at this location.

        Two elements overlap if their boxes share an area, so elements that
        only touch do not. Rounded corners are ignored, which can count two
        diagonal neighbours whose rounded corners just miss each other. Only
        glyphs drawn from element components are checked.

        Returns:
            A set of glyph names.
        """
        half_size, _corner_radius, outer_right = self._get_element_sizes()
        reach = Vec2(half_size.x + outer_right.x, 2 * half_size.y)

        overlapping_glyph_names = set()
        for ufo_glyph in self.ufo_font:
            offsets = sorted(
                (component.transformation.dx, component.transformation.dy)
                for component in ufo_glyph.components
                if component.baseGlyph == "_"
            )
            if any(
                x2 - x1 < reach.x and abs(y2 - y1) < reach.y
                for index, (x1, y1) in enumerate(offsets)
                for x2, y2 in offsets[index + 1 :]
            ):
                overlapping_glyph_names.add(ufo_glyph.name)

        return overlapping_glyph_names

    def set_overlap_flags(self, glyph_names: set) -> None:
        """Mark glyphs as having overlapping contours.

        ufo2ft turns the mark into the overlap bit of the glyf table, which tells
        rasterizers that fill the contours with the non-zero rule, such as
        Apple's, to expect overlaps.

        Args:
            glyph_names: The names of the glyphs.
        """
        for glyph_name in glyph_names:
            self.ufo_font[glyph_name].lib["public.truetype.overlap"] = True

    def _add_element_glyph(self, ufo_glyph, offset: Vec2) -> None:
        """Add the contour of an element: a rectangle with rounded corners,
        whose right side the bleed extends.

        Each corner runs from one side to the next: along its arc from the
        point where the straight side ends, through the off-curve points (and
        the mid-arc point of quadratic curves), to the point where the next
        side starts. The corners on the vertical sides (top right, bottom left)
        start on the vertical side, the others on the horizontal side, so their
        points come in reverse order.

        Args:
            ufo_glyph: The glyph to add the contour to.
            offset: The center of the element.
        """
        half_size, corner_radius, outer_right = self._get_element_sizes()
        outer = half_size
        inner_right = outer_right - corner_radius
        inner = outer - corner_radius

        if self.curves == "quadratic":
            tangent_factor = Vec2(math.tan(math.radians(90 / 4)))
            midarc_factor = Vec2(math.cos(math.radians(45)))
            types = ["line", "offcurve", "qcurve", "offcurve", "qcurve"]
        elif self.curves == "cubic":
            tangent_factor = Vec2((4 / 3) * math.tan(math.radians(90 / 4)))
            midarc_factor = None
            types = ["line", "offcurve", "offcurve", "curve"]
        else:
            return

        def get_side(outer_side, inner_side):
            # The outer, tangent, inner and mid-arc coordinates of a side
            tangent_side = inner_side + corner_radius * tangent_factor
            midarc_side = inner_side + corner_radius * midarc_factor if midarc_factor else None
            return outer_side, tangent_side, inner_side, midarc_side

        right = get_side(outer_right, inner_right)
        left = get_side(outer, inner)

        points = []
        for x_side, x_sign, y_sign, reverse in (
            (right, 1, 1, False),
            (left, -1, 1, True),
            (left, -1, -1, False),
            (right, 1, -1, True),
        ):
            x_outer, x_tangent, x_inner, x_midarc = (
                None if value is None else x_sign * value.x for value in x_side
            )
            y_outer, y_tangent, y_inner, y_midarc = (
                None if value is None else y_sign * value.y for value in right
            )

            corner = [(x_outer, y_inner), (x_outer, y_tangent)]
            if midarc_factor:
                corner.append((x_midarc, y_midarc))
            corner += [(x_tangent, y_outer), (x_inner, y_outer)]
            if reverse:
                corner.reverse()

            points += zip(corner, types)

        ufo_glyph.appendContour(
            ufoLib2.objects.Contour(
                [
                    ufoLib2.objects.Point(offset.x + x, offset.y + y, point_type)
                    for (x, y), point_type in points
                ]
            )
        )

    def _set_element_glyph(self) -> None:
        element_glyph = self.ufo_font.newGlyph("_")
        self._add_element_glyph(element_glyph, Vec2(0))

    def _set_glyphs(self) -> None:
        for glyph_name, bdf_glyph in self.bdf_font.glyphs.items():
            glyph_character = bdf_glyph["character"]
            glyph_advance = bdf_glyph["advance"]

            ufo_glyph = self.ufo_font.newGlyph(glyph_name)
            if glyph_character is not None:
                ufo_glyph.unicode = ord(glyph_character)
            ufo_glyph.width = int(glyph_advance * self.glyph_scale.x)

            # A composition whose components draw the same element twice would
            # emit duplicate components at identical coordinates, so draw the
            # glyph from its bitmap instead.
            if glyph_name in self.components and glyph_name not in self.precomposed:
                self._add_components(
                    ufo_glyph, glyph_character, self.components[glyph_name]
                )
            else:
                self._add_bitmap(ufo_glyph, bdf_glyph)

    def _apply_italic(self, offset):
        y = offset.y - 0.5 * self.glyph_scale.y

        return offset + Vec2(y * self.italic_slope, 0)

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
        """Draw a glyph from its bitmap, one element per pixel and strike.

        The arithmetic runs on plain numbers, in the same order as the Vec2
        operations of the other glyph parts, so the offsets are the same.
        """
        scale_x, scale_y = self.glyph_scale.x, self.glyph_scale.y
        offset_x = self.glyph_offset.x + bdf_glyph["offset"].x
        offset_y = self.glyph_offset.y + bdf_glyph["offset"].y
        mark_shift = self._get_mark_shift(bdf_glyph["character"])

        # A master without jitter draws no random numbers: its jitter offsets
        # would all be zero
        jitter = self.location["JITT"] / 1000

        for y, x in np.argwhere(bdf_glyph["bitmap"]).tolist():
            for strike_index in range(self.strike_num):
                element_x = ((x + 0.5) + offset_x + 0) * scale_x
                element_y = ((y + 0.5) + offset_y + -0.5 * strike_index) * scale_y

                # Italic offset
                element_x += (element_y - 0.5 * scale_y) * self.italic_slope

                # Jitter offset
                if jitter:
                    jitter_offset = Vec2.random(jitter, MAX_JITTER_OFFSET)
                    element_x += jitter_offset.x * self.units_per_element.x
                    element_y += jitter_offset.y * self.units_per_element.y

                # Fix Fontspector/Shaperglot heuristics
                element_x += mark_shift

                if self.use_element_glyph:
                    self._append_component(
                        ufo_glyph, self._get_component("_", Vec2(element_x, element_y))
                    )
                else:
                    self._add_element_glyph(ufo_glyph, Vec2(element_x, element_y))

    def _add_components(self, ufo_glyph, glyph_character, glyph_components):
        for component_name, component_offset in glyph_components:
            component_character = self.bdf_font.glyphs[component_name]["character"]

            offset = self._apply_italic(component_offset * self.glyph_scale)

            # Fix Fontspector/Shaperglot heuristics. The component glyph already
            # carries its own nudge, so undo it and apply the composed glyph's.
            offset.x += self._get_mark_shift(glyph_character) - self._get_mark_shift(
                component_character
            )

            self._append_component(ufo_glyph, self._get_component(component_name, offset))

    @staticmethod
    def _get_component(glyph_name: str, offset) -> ufoLib2.objects.Component:
        """Return a component of a glyph at an offset, rounded down to font units."""
        ufo_component = ufoLib2.objects.Component(glyph_name)
        ufo_component.transformation = [
            1,
            0,
            0,
            1,
            math.floor(offset.x),
            math.floor(offset.y),
        ]

        return ufo_component

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

        # A kerning side of several characters is a group, numbered across
        # both sides in order of appearance; a single character is its glyph
        groups = {"public.kern1": {}, "public.kern2": {}}
        group_count = 0

        def get_side(prefix, characters):
            nonlocal group_count
            if len(characters) == 1:
                return self.bdf_font.names[characters[0]]
            if characters not in groups[prefix]:
                group_count += 1
                group_name = f"{prefix}.group{group_count}"
                self.ufo_font.groups[group_name] = [self.bdf_font.names[c] for c in characters]
                groups[prefix][characters] = group_name

            return groups[prefix][characters]

        for left_characters, right_characters, value in self.kerning:
            left = get_side("public.kern1", left_characters)
            right = get_side("public.kern2", right_characters)

            self.ufo_font.kerning[(left, right)] = value * self.units_per_element.x
