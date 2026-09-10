"""
bdf2ufo

This module provides utility functions for the BDF to UFO conversion process.

(C) 2024-2026 Gissio
License: MIT
"""

import random
from typing import Iterable

from .data import STATIC_STYLES


def combine_strings(a: str, b: str) -> str:
    """
    Combine two strings with a space and strip whitespace.

    Args:
        a: The first string.
        b: The second string.

    Returns:
        The combined and stripped string.
    """
    return (a + " " + b).strip()


def filter_name(name: str) -> str:
    """Filter a name to contain only lowercase alphabetic characters.

    Args:
        name: The name string to filter.

    Returns:
        A string containing only lowercase alphabetic characters from the input name.
    """
    return "".join(c for c in name.lower() if c.isalpha())


def split_family_style_names(family_name: str, style_name: str) -> tuple[str, str]:
    """
    Split a family name and a style name following the Google Fonts naming scheme.

    Google Fonts only accepts a weight name, optionally followed by "Italic", as
    a style name (see https://googlefonts.github.io/gf-guide/statics.html).
    Every other style name component (e.g. "LCD") becomes part of the family
    name instead. These names end up in the name table's nameID 16 (typographic
    family name) and nameID 17 (typographic subfamily name).

    Args:
        family_name: The font family name.
        style_name: The font style name.

    Returns:
        A tuple with the typographic family name and the typographic subfamily name.
    """
    family_components = family_name.split()
    style_components = []

    for component in style_name.split():
        if component in STATIC_STYLES:
            style_components.append(component)
        elif component not in family_components:
            family_components.append(component)

    # "Regular" is implied by any other style name component
    if len(style_components) > 1:
        style_components = [c for c in style_components if c != "Regular"]

    return " ".join(family_components), " ".join(style_components) or "Regular"


def get_style_map_names(family_name: str, style_name: str) -> tuple[str, str]:
    """
    Determine the style map names of a family name and a style name.

    The style map names are the legacy, RIBBI-only names: the style map style
    name can only be one of "regular", "italic", "bold" or "bold italic", so any
    other style name component moves to the style map family name. These names
    end up in the name table's nameID 1 (family name) and nameID 2 (subfamily
    name).

    Args:
        family_name: The font family name.
        style_name: The font style name.

    Returns:
        A tuple with the style map family name and the style map style name.
    """
    family_components = family_name.split()
    bold = False
    italic = False

    for component in style_name.split():
        if component == "Bold":
            bold = True
        elif component == "Italic":
            italic = True
        elif component != "Regular" and component not in family_components:
            family_components.append(component)

    if not bold:
        if not italic:
            style_map_style_name = "regular"
        else:
            style_map_style_name = "italic"
    else:
        if not italic:
            style_map_style_name = "bold"
        else:
            style_map_style_name = "bold italic"

    return " ".join(family_components), style_map_style_name


class Vec2:
    """
    2D vector class for representing and manipulating (x, y) coordinates.
    """

    def __init__(
        self, x: float | Iterable[float] | None = None, y: float | None = None
    ):
        if x is None:
            self.x = 0.0
            self.y = 0.0
        elif y is None:
            if isinstance(x, Iterable):
                self.x, self.y = x
            else:
                self.x = x
                self.y = x
        else:
            self.x = x
            self.y = y

    @classmethod
    def random(
        cls,
        std: float = 1.0,  # ← standard deviation = sqrt(variance)
        limit: float = 1.0,
    ) -> "Vec2":
        """Create a Vec2 with components ~ Normal(mean, std²)"""
        while True:
            x = random.gauss(0, std)
            y = random.gauss(0, std)
            if (x**2 + y**2) ** 0.5 < limit:
                break

        return cls(x, y)

    def __add__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, other: "Vec2") -> "Vec2":  # element-wise multiplication
        return Vec2(self.x * other.x, self.y * other.y)

    def __rmul__(self, scalar: float) -> "Vec2":  # support scalar * vec
        return Vec2(self.x * scalar, self.y * scalar)

    def __repr__(self):
        return f"({self.x}, {self.y})"


def format_unicode_character(character):
    """
    Convert a Unicode character to its string representation.

    Args:
        character: A Unicode character.

    Returns:
        A string representation of the Unicode character in the format "U+XXXX".
    """
    return "U+" + f"{ord(character):04x}"


def format_unicode_characters(components):
    """
    Convert a list of Unicode characters to a string representation.

    Args:
        components: A list of Unicode characters.

    Returns:
        A string representation of the list of Unicode characters, where each character is represented in the format "U+XXXX" and separated by commas.
    """
    return ", ".join([format_unicode_character(character) for character in components])
