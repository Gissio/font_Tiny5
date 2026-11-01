"""
bdf2ufo

ccmp feature rules for BDF to UFO font conversion.

(C) 2024-2026 Gissio
License: MIT
"""

from .bdf_font import BDFFont
from .data import CCMP_SOFTDOT_COMPOSITION, CCMP_SOFTDOT_DECOMPOSITION


def build_ccmp(bdf_font: BDFFont) -> dict:
    """Build the substitutions of the ccmp feature.

    Args:
        bdf_font: The BDF font object.

    Returns:
        Dictionary with the "decomposition" substitutions, from glyph name to
        a list of glyph names, and the "softdot" substitutions, from glyph name
        to the glyph name used before a top mark.
    """
    decomposition = {}
    for source_character, target_characters in CCMP_SOFTDOT_DECOMPOSITION.items():
        if source_character in bdf_font.names and all(
            target_character in bdf_font.names
            for target_character in target_characters
        ):
            decomposition[bdf_font.names[source_character]] = [
                bdf_font.names[target_character]
                for target_character in target_characters
            ]

    softdot = {}
    for source_character, target_character in CCMP_SOFTDOT_COMPOSITION.items():
        if (
            source_character in bdf_font.names
            and target_character in bdf_font.names
        ):
            softdot[bdf_font.names[source_character]] = bdf_font.names[
                target_character
            ]

    return {"decomposition": decomposition, "softdot": softdot}


def get_ccmp_substitutes(ccmp: dict, glyph_name: str) -> list:
    """Return the glyphs that ccmp substitutes for a single glyph.

    For instance, ccmp substitutes "i" for U+0456, and "dotlessi" for that
    "i" when a top mark follows.

    Args:
        ccmp: The ccmp substitutions, from build_ccmp().
        glyph_name: The name of the glyph.

    Returns:
        A list of glyph names.
    """
    targets = ccmp["decomposition"].get(glyph_name, [])
    if len(targets) != 1:
        return []

    substitutes = list(targets)
    if targets[0] in ccmp["softdot"]:
        substitutes.append(ccmp["softdot"][targets[0]])

    return substitutes
