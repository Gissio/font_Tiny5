"""
bdf2ufo

Design space module for managing variable font design spaces.

(C) 2024-2026 Gissio
License: MIT
"""

import logging
import os
from pathlib import Path
import random

import fontTools
import fontTools.designspaceLib

from .data import WEIGHT_CLASSES, AXES_INFO
from .utils import Vec2, combine_strings, get_style_map_style_name
from .bdf_font import BDFFont
from .decomposition import build_decomposition
from .anchors import build_anchors
from .ufo_font import UFOFont

# Constants
DEFAULT_STRIKE_COUNT_SINGLE = 1
DEFAULT_STRIKE_COUNT_DOUBLE = 2

# Definitions
logger = logging.getLogger(__name__)


class DesignSpace:
    """
    DesignSpace class for managing font design space operations.
    This class handles the conversion of BDF fonts to UFO (Unified Font Object) format
    with support for variable fonts. It manages design space axes, instances, masters,
    and generates designspace documents.

    Attributes:
        bdf_font: The source BDF font object.
        random_seed (int): Seed for random number generation.

        ufo_config (dict): Configuration for UFO generation.

        default_axis_values (dict): Default values for axes.
        variable_axes (dict): Dictionary of variable axes with their properties (min, default, max).
        variable_instances (dict): Dictionary of variable instances with their axis locations.
    """

    def __init__(self):
        self.bdf_font = None
        self.random_seed = 0

        self.ufo_config = {}

        self.default_axis_values = {}
        self.variable_axes = {}
        self.variable_instances = {}

    def setup(self, bdf_font: BDFFont, config: dict) -> None:
        """Configure the design space with command-line arguments and BDF font.

        Args:
            bdf_font: The source BDF font object to configure with.
            config: Parsed configuration object containing configuration options.
        """
        self.bdf_font = bdf_font
        self.random_seed = config.get("random_seed", 0)

        # Composite glyphs
        components = build_decomposition(bdf_font)

        # Anchors
        anchors = build_anchors(bdf_font, components, config.get("custom_anchors", {}))

        # UFO font generation parameters
        self.ufo_config["glyph_offset"] = Vec2(config.get("glyph_offset", [0, 0]))
        self.ufo_config["strike_num"] = (
            DEFAULT_STRIKE_COUNT_DOUBLE
            if config.get("double_strike", False)
            else DEFAULT_STRIKE_COUNT_SINGLE
        )
        self.ufo_config["units_per_em"] = config.get("units_per_em", 2048)

        default_units_per_element_y = int(
            self.ufo_config["units_per_em"] / (bdf_font.ascent - bdf_font.descent)
        )
        self.ufo_config["units_per_element"] = Vec2(
            config.get(
                "units_per_element",
                [default_units_per_element_y, default_units_per_element_y],
            )
        )
        self.ufo_config["components"] = components
        self.ufo_config["anchors"] = anchors
        self.ufo_config["kerning"] = config.get("kerning", [])

        # Default axis values
        self.default_axis_values = {}

        default_axis_values = config.get("default_axis_values", {})
        for axis_tag, axis_value in default_axis_values.items():
            if axis_tag not in AXES_INFO:
                raise ValueError(
                    f"Invalid axis '{axis_tag}' in default axis values configuration"
                )

            self.default_axis_values[axis_tag] = float(axis_value)

        for axis_tag, axis_info in AXES_INFO.items():
            if axis_tag not in self.default_axis_values:
                self.default_axis_values[axis_tag] = axis_info.get(
                    "default", AXES_INFO[axis_tag]["default"]
                )

        # Variable axes
        self.variable_axes = {}

        variable_axes = config.get("variable_axes", {})
        for axis_tag, axis_values in variable_axes.items():
            if axis_tag not in AXES_INFO:
                raise ValueError(f"Invalid variable axis '{axis_tag}' in configuration")

            self.variable_axes[axis_tag] = {
                "min": axis_values.get("min", AXES_INFO[axis_tag]["min"]),
                "max": axis_values.get("max", AXES_INFO[axis_tag]["max"]),
            }

        # Variable instances
        self.variable_instances = {}

        variable_instances = config.get("variable_instances", {"": {}})
        for instance_name, instance_location in variable_instances.items():
            for axis_tag, axis_value in instance_location.items():
                if axis_tag not in self.variable_axes:
                    raise ValueError(
                        f"Instance '{instance_name}' references undefined axis '{axis_tag}'"
                    )

            for axis_tag, axis_value in self.default_axis_values.items():
                if axis_tag not in instance_location:
                    instance_location[axis_tag] = axis_value

            self.variable_instances[instance_name] = instance_location

    def build(self, output_path: Path) -> None:
        """Build the design space by writing masters and designspace document.

        Args:
            output_path: The directory path where master UFO files and designspace document will be written.
        """
        output_path = Path(output_path)

        os.makedirs(output_path, exist_ok=True)

        self._write_masters(output_path)

        self._write_designspace(output_path)

    def _get_masters(self) -> list:
        masters = {}

        # Default master
        default_name, default_location = self._get_master(self.default_axis_values)
        masters[default_name] = default_location

        # Masters for each variable axis
        for axis_name, axis_value in self.variable_axes.items():
            variable_axes = self.default_axis_values.copy()

            variable_axes[axis_name] = axis_value["min"]
            name, location = self._get_master(variable_axes)
            masters[name] = location

            variable_axes[axis_name] = axis_value["max"]
            name, location = self._get_master(variable_axes)
            masters[name] = location

        # Masters for wght and ROND axes combinations
        if "wght" in self.variable_axes and "ROND" in self.variable_axes:
            for wght_limits in ["min", "max"]:
                for rond_limits in ["min", "max"]:
                    variable_axes = self.default_axis_values.copy()

                    variable_axes["wght"] = self.variable_axes["wght"][wght_limits]
                    variable_axes["ROND"] = self.variable_axes["ROND"][rond_limits]

                    name, location = self._get_master(variable_axes)
                    masters[name] = location

        return [
            {"name": name, "location": location} for name, location in masters.items()
        ]

    def _get_master(self, axes: dict) -> dict:
        name = []
        location = {}

        for axis_name in self.variable_axes:
            name.append(f"{axis_name}{int(axes[axis_name])}")
            location[axis_name] = axes[axis_name]

        for axis_tag, axis_value in self.default_axis_values.items():
            if axis_tag not in location:
                location[axis_tag] = axis_value

        return "_".join(name), location

    def _write_masters(self, output_path: Path) -> None:
        for master in self._get_masters():
            master_name = master["name"]
            master_location = master["location"]

            ufo_file_name = (
                self._get_file_name(self.bdf_font.family_name, master_name) + ".ufo"
            )

            logger.info("Building %s...", ufo_file_name)

            random.seed(self.random_seed)

            ufo_font = UFOFont()

            ufo_font.setup(self.bdf_font, self.ufo_config, master_location)

            ufo_font.save(output_path / ufo_file_name)

    def _write_designspace(self, output_path: Path) -> None:
        designspace_filename = (
            self._get_file_name(self.bdf_font.family_name, "") + ".designspace"
        )

        # Build designspace document
        designspace = fontTools.designspaceLib.DesignSpaceDocument()

        # Axes
        for axis_tag, axis_info in self.variable_axes.items():
            axis_name = AXES_INFO[axis_tag]["name"]

            designspace.addAxisDescriptor(
                tag=axis_tag,
                name=axis_name,
                minimum=int(axis_info["min"]),
                maximum=int(axis_info["max"]),
                default=int(self.default_axis_values[axis_tag]),
            )

        # Sources
        for master in self._get_masters():
            master_file_name = self._get_file_name(
                self.bdf_font.family_name, master["name"]
            )

            master_location = {}
            for axis_tag, axis_value in master["location"].items():
                axis_name = AXES_INFO[axis_tag]["name"]

                master_location[axis_name] = int(axis_value)

            designspace.addSourceDescriptor(
                filename=master_file_name + ".ufo",
                name=master_file_name,
                familyName=self.bdf_font.family_name,
                location=master_location,
            )

        # Instances
        for name, master_location in self.variable_instances.items():
            family_name = self.bdf_font.family_name

            instance_file_name = self._get_file_name(family_name, name)

            if name in WEIGHT_CLASSES:
                instance_family_name = family_name
                instance_style_name = name
            else:
                instance_family_name = combine_strings(family_name, name)
                instance_style_name = "Regular"

            instance_style_map_style_name = get_style_map_style_name(name)

            instance_location = {}
            for axis_tag, axis_value in master_location.items():
                axis_name = AXES_INFO[axis_tag]["name"]

                instance_location[axis_name] = int(axis_value)

            designspace.addInstanceDescriptor(
                name=instance_file_name,
                filename=instance_file_name + ".ufo",
                familyName=instance_family_name,
                styleName=instance_style_name,
                styleMapFamilyName=instance_family_name,
                styleMapStyleName=instance_style_map_style_name,
                location=instance_location,
            )

        designspace.write(output_path / designspace_filename)

    def _get_file_name(self, family_name: str, style_name: str) -> str:
        family_name = family_name.replace(" ", "")
        style_name = style_name.replace(" ", "")

        if style_name == "":
            return family_name
        else:
            return f"{family_name}-{style_name}"
