"""
bdf2ufo

This module provides utility functions for the BDF to UFO conversion process.

(C) 2024-2026 Gissio
License: MIT
"""

import random
from typing import Iterable


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


def get_style_map_style_name(style_name: str) -> tuple[str, str]:
    """
    Determine the style map style name based on the family name and style name.    

    Args:
        family_name: The font family name.
        style_name: The font style name.

    Returns:
        The style map style name.
    """
    bold = False
    italic = False

    for style in style_name.split(" "):
        if style == "Bold":
            bold = True
        elif style == "Italic":
            italic = True

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

    return style_map_style_name


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
