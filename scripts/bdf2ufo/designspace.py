"""
bdf2ufo

Design space module for managing variable font design spaces.

(C) 2024-2026 Gissio
License: MIT
"""

import itertools
import logging
import os
from pathlib import Path
import random

import fontTools
import fontTools.designspaceLib
from fontTools.varLib.models import piecewiseLinearMap

from .data import (
    AXES_INFO,
    DEFAULT_ITALIC_ANGLE,
    WEIGHT_NAME_FROM_WGHT,
    WIDTH_NAME_FROM_WDTH,
)
from .utils import (
    Vec2,
    get_style_map_names,
    get_weight_class,
    get_width_class,
    split_family_style_names,
)
from .bdf_font import BDFFont
from .decomposition import build_decomposition
from .anchors import build_anchors
from .ufo_font import UFOFont

# Constants
DEFAULT_STRIKE_COUNT_SINGLE = 1
DEFAULT_STRIKE_COUNT_DOUBLE = 2
COMBINATION_AXES = ("wght", "wdth", "ROND", "BLED")

# The axes whose style name components come first, in this order. The remaining
# axes follow in the order they are defined in AXES_INFO.
STYLE_NAME_AXES = ("wdth", "wght", "ital")

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

        All axis values of the configuration are user coordinates. The axis maps
        convert them to design coordinates, which the masters are built from.
        Axes without an axis map have identical user and design coordinates.

        default_axis_values (dict): Default values for axes, in user coordinates.
        variable_axes (dict): Dictionary of variable axes with their user space range (min, max).
        axis_maps (dict): Dictionary of axis maps, each a sorted list of (user, design) pairs.
        variable_instances (dict): Dictionary of variable instances with their user space locations.
    """

    def __init__(self):
        self.bdf_font = None
        self.random_seed = 0

        self.ufo_config = {}

        self.default_axis_values = {}
        self.variable_axes = {}
        self.axis_maps = {}
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
        self.ufo_config["use_element_glyph"] = config.get("use_element_glyph", True)
        self.ufo_config["italic_angle"] = float(
            config.get("italic_angle", DEFAULT_ITALIC_ANGLE)
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

            self._check_axis_range(
                axis_tag, self.default_axis_values[axis_tag], "Default axis value"
            )

        # Axis maps
        self.axis_maps = {}

        axis_maps = config.get("axis_maps", {})
        for axis_tag, axis_map in axis_maps.items():
            if axis_tag not in self.variable_axes:
                raise ValueError(
                    f"Axis map references undefined variable axis '{axis_tag}'"
                )

            self.axis_maps[axis_tag] = self._parse_axis_map(axis_tag, axis_map)

        # Variable instances
        self.variable_instances = {}

        variable_instances = config.get("variable_instances", {"": {}})
        for instance_name, instance_location in variable_instances.items():
            for axis_tag, axis_value in instance_location.items():
                if axis_tag not in self.variable_axes:
                    raise ValueError(
                        f"Instance '{instance_name}' references undefined axis '{axis_tag}'"
                    )

                self._check_axis_range(
                    axis_tag, axis_value, f"Instance '{instance_name}'"
                )

            for axis_tag, axis_value in self.default_axis_values.items():
                if axis_tag not in instance_location:
                    instance_location[axis_tag] = axis_value

            self.variable_instances[instance_name] = instance_location

    def _check_axis_range(self, axis_tag: str, axis_value: float, context: str) -> None:
        """Check that a user space value lies within the range of a variable axis.

        Args:
            axis_tag: The tag of the variable axis.
            axis_value: The user space value.
            context: A description of the value's origin, for the error message.
        """
        axis_range = self.variable_axes[axis_tag]

        if not axis_range["min"] <= axis_value <= axis_range["max"]:
            raise ValueError(
                f"{context}: '{axis_tag}' value {axis_value} is outside the axis "
                f"range {axis_range['min']}-{axis_range['max']}"
            )

    def _parse_axis_map(self, axis_tag: str, axis_map: dict) -> list:
        """Parse and validate the axis map of a variable axis.

        Args:
            axis_tag: The tag of the variable axis.
            axis_map: The axis map, a dictionary from user to design values.

        Returns:
            The axis map, as a list of (user, design) pairs sorted by user value.
        """
        if not isinstance(axis_map, dict) or not axis_map:
            raise ValueError(
                f"Axis map of '{axis_tag}' must map user values to design values"
            )

        mapping = sorted((float(user), float(design)) for user, design in axis_map.items())

        # The map must span the axis range, so that every user value has a
        # design value
        axis_range = self.variable_axes[axis_tag]
        if mapping[0][0] != axis_range["min"] or mapping[-1][0] != axis_range["max"]:
            raise ValueError(
                f"Axis map of '{axis_tag}' covers user values "
                f"{mapping[0][0]:g}-{mapping[-1][0]:g}, but the variable axis range is "
                f"{axis_range['min']}-{axis_range['max']}. Set the min and max of "
                f"'{axis_tag}' in variable_axes to the first and last axis map keys."
            )

        # The map must be strictly increasing, so that it can be inverted
        for (user_a, design_a), (user_b, design_b) in zip(mapping, mapping[1:]):
            if user_b <= user_a or design_b <= design_a:
                raise ValueError(
                    f"Axis map of '{axis_tag}' must have strictly increasing "
                    "user and design values"
                )

        return mapping

    def _map_forward(self, axis_tag: str, user_value: float) -> float:
        """Convert a user space axis value to a design space axis value."""
        if axis_tag not in self.axis_maps:
            return user_value

        return piecewiseLinearMap(user_value, dict(self.axis_maps[axis_tag]))

    def _get_design_location(self, user_location: dict) -> dict:
        """Convert a user space location to a design space location."""
        return {
            axis_tag: self._map_forward(axis_tag, axis_value)
            for axis_tag, axis_value in user_location.items()
        }

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
        default_name, default_master = self._get_master(self.default_axis_values)
        masters[default_name] = default_master

        # Masters for each variable axis
        for axis_name, axis_value in self.variable_axes.items():
            variable_axes = self.default_axis_values.copy()

            variable_axes[axis_name] = axis_value["min"]
            name, master = self._get_master(variable_axes)
            masters[name] = master

            variable_axes[axis_name] = axis_value["max"]
            name, master = self._get_master(variable_axes)
            masters[name] = master

        # Masters for all combinations of the combination axes, except those
        # where both ROND and BLED are at their maximum
        combination_axes = {}

        for axis_name in COMBINATION_AXES:
            if axis_name not in self.variable_axes:
                continue

            axis_values = self.variable_axes[axis_name]
            combination_axes[axis_name] = sorted(
                {
                    axis_values["min"],
                    self.default_axis_values[axis_name],
                    axis_values["max"],
                }
            )

        for axis_combination in itertools.product(*combination_axes.values()):
            variable_axes = self.default_axis_values.copy()
            variable_axes.update(zip(combination_axes, axis_combination))

            if (
                "ROND" in combination_axes
                and "BLED" in combination_axes
                and variable_axes["ROND"] == self.variable_axes["ROND"]["max"]
                and variable_axes["BLED"] == self.variable_axes["BLED"]["max"]
            ):
                continue

            name, master = self._get_master(variable_axes)
            masters[name] = master

        return [{"name": name, **master} for name, master in masters.items()]

    def _get_master(self, axes: dict) -> tuple[str, dict]:
        """Get the name and locations of a master.

        Args:
            axes: The user space location of the master.

        Returns:
            The name of the master, from its design space location, and a
            dictionary with its design ("location") and user ("user_location")
            space locations.
        """
        name = []
        user_location = {}

        for axis_name in self.variable_axes:
            user_location[axis_name] = axes[axis_name]

        for axis_tag, axis_value in self.default_axis_values.items():
            if axis_tag not in user_location:
                user_location[axis_tag] = axis_value

        location = self._get_design_location(user_location)

        for axis_name in self.variable_axes:
            name.append(f"{axis_name}{int(location[axis_name])}")

        return "_".join(name), {"location": location, "user_location": user_location}

    def _get_master_style_name(self, location: dict) -> str:
        """Build the style name of a master from its user space location.

        Axes at their default value are elided, so the default master gets the
        style name of the source .bdf font.

        Args:
            location: The user space location of the master.

        Returns:
            The style name of the master.
        """
        axis_tags = [tag for tag in STYLE_NAME_AXES if tag in self.variable_axes]
        axis_tags += [tag for tag in self.variable_axes if tag not in STYLE_NAME_AXES]

        style_components = []
        for axis_tag in axis_tags:
            axis_value = location[axis_tag]

            if axis_value == self.default_axis_values[axis_tag]:
                continue

            if axis_tag == "wght" and axis_value in WEIGHT_NAME_FROM_WGHT:
                style_components.append(WEIGHT_NAME_FROM_WGHT[axis_value])
            elif axis_tag == "wdth" and axis_value in WIDTH_NAME_FROM_WDTH:
                style_components.append(WIDTH_NAME_FROM_WDTH[axis_value])
            elif axis_tag == "ital":
                style_components.append("Italic")
            else:
                style_components.append(
                    f"{AXES_INFO[axis_tag]['name']}{int(axis_value)}"
                )

        return " ".join(style_components) or self.bdf_font.style_name or "Regular"

    def _write_masters(self, output_path: Path) -> None:
        for master in self._get_masters():
            master_name = master["name"]
            master_location = master["location"]
            master_user_location = master["user_location"]
            master_style_name = self._get_master_style_name(master_user_location)

            ufo_file_name = (
                self._get_file_name(self.bdf_font.family_name, master_name) + ".ufo"
            )

            logger.info("Building %s...", ufo_file_name)

            random.seed(self.random_seed)

            ufo_font = UFOFont()

            ufo_font.setup(
                self.bdf_font,
                self.ufo_config,
                master_location,
                master_user_location,
                master_style_name,
            )

            ufo_font.save(output_path / ufo_file_name)

    def _write_designspace(self, output_path: Path) -> None:
        designspace_filename = (
            self._get_file_name(self.bdf_font.family_name, "") + ".designspace"
        )

        # Build designspace document
        designspace = fontTools.designspaceLib.DesignSpaceDocument()

        # Axes, with their range in user coordinates
        for axis_tag, axis_info in self.variable_axes.items():
            axis_name = AXES_INFO[axis_tag]["name"]

            designspace.addAxisDescriptor(
                tag=axis_tag,
                name=axis_name,
                minimum=int(axis_info["min"]),
                maximum=int(axis_info["max"]),
                default=int(self.default_axis_values[axis_tag]),
                map=self.axis_maps.get(axis_tag, []),
            )

        # Sources, in design coordinates
        for master in self._get_masters():
            master_file_name = self._get_file_name(
                self.bdf_font.family_name, master["name"]
            )

            master_location = {}
            for axis_tag, axis_value in master["location"].items():
                axis_name = AXES_INFO[axis_tag]["name"]

                master_location[axis_name] = axis_value

            designspace.addSourceDescriptor(
                filename=master_file_name + ".ufo",
                name=master_file_name,
                familyName=self.bdf_font.family_name,
                styleName=self._get_master_style_name(master["user_location"]),
                location=master_location,
            )

        # Instances, converted from user to design coordinates
        for name, user_location in self.variable_instances.items():
            family_name = self.bdf_font.family_name

            instance_file_name = self._get_file_name(family_name, name)

            instance_family_name, instance_style_name = split_family_style_names(
                family_name, name
            )
            (
                instance_style_map_family_name,
                instance_style_map_style_name,
            ) = get_style_map_names(instance_family_name, instance_style_name)

            instance_location = {}
            for axis_tag, axis_value in self._get_design_location(
                user_location
            ).items():
                axis_name = AXES_INFO[axis_tag]["name"]

                instance_location[axis_name] = axis_value

            # The OS/2 weight and width classes of the instance on mapped axes,
            # from its user space location. Otherwise, fontmake interpolates
            # them from the masters in design space, which is wrong for
            # non-linear axis maps.
            instance_font_info = {}
            if "wght" in self.axis_maps:
                instance_font_info["openTypeOS2WeightClass"] = get_weight_class(
                    user_location["wght"]
                )
            if "wdth" in self.axis_maps:
                instance_font_info["openTypeOS2WidthClass"] = get_width_class(
                    user_location["wdth"]
                )

            designspace.addInstanceDescriptor(
                name=instance_file_name,
                filename=instance_file_name + ".ufo",
                familyName=instance_family_name,
                styleName=instance_style_name,
                styleMapFamilyName=instance_style_map_family_name,
                styleMapStyleName=instance_style_map_style_name,
                location=instance_location,
                lib=(
                    {"public.fontInfo": instance_font_info}
                    if instance_font_info
                    else {}
                ),
            )

        designspace.write(output_path / designspace_filename)

    def _get_file_name(self, family_name: str, style_name: str) -> str:
        family_name = family_name.replace(" ", "")
        style_name = style_name.replace(" ", "")

        if style_name == "":
            return family_name
        else:
            return f"{family_name}-{style_name}"
