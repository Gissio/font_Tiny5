"""
bdf2ufo

Ligature building for BDF to UFO font conversion.

(C) 2024-2026 Gissio
License: MIT
"""

import logging

import numpy as np

from .bdf_font import BDFFont
from .calt import DIGITS, HEX_LETTERS, CaltRules
from .data import LIGATURE_SPACER_NAME
from .utils import Vec2

# Definitions
logger = logging.getLogger(__name__)


def build_ligatures(bdf_font: BDFFont) -> dict:
    """Add the contextual alternates of the font and return their rules.

    The contextual alternates are unencoded glyphs: ligatures (".liga"), run
    pieces (".seq") and numeric forms (".num"); see CaltRules. A ligature or a
    run head is drawn as wide as its characters together.

    In a monospace font, a glyph of n characters is drawn n cells wide. It
    is turned into a glyph one cell wide, whose drawing extends over the n - 1
    cells to its left, which an empty spacer glyph fills. So every glyph keeps
    the monospace advance, and the cursor still moves one cell at a time.

    The glyphs are added after all other glyphs, so that the jitter of the
    other glyphs does not depend on whether ligatures are enabled.

    Args:
        bdf_font: The BDF font object.

    Returns:
        Dictionary with "rules", the CaltRules, "names", a dictionary from
        characters to glyph names, and "spacer", the name of the spacer glyph
        of a monospace font, or None.
    """
    monospace = bdf_font.monospace

    characters = {
        name: glyph["character"]
        for name, glyph in bdf_font.glyphs.items()
        if glyph["character"] is not None
    }
    rules = CaltRules(bdf_font.ligature_glyphs, characters, logger.warning)

    if not monospace and rules.has_runs():
        logger.warning("Runs need a monospace font, skipping the .seq glyphs")
        for line in list(rules.lines):
            rules.remove(rules.lines[line]["start"])

    # Glyphs whose advance does not fit their cells are left out
    if monospace:
        for name, cells in list(rules.cells.items()):
            advance = bdf_font.ligature_glyphs[name]["advance"]
            if name in rules.cells and advance != cells * monospace:
                logger.warning(
                    "'%s' has advance %d, expected %d for %d monospace cells, skipping",
                    name,
                    advance,
                    cells * monospace,
                    cells,
                )
                line = rules.remove(name)
                if line is not None:
                    logger.warning("Runs of '%s' have no %s, skipping them", line, name)

    for name, cells in rules.cells.items():
        glyph = bdf_font.ligature_glyphs[name]
        if monospace:
            glyph = dict(glyph)
            glyph["offset"] = glyph["offset"] - Vec2((cells - 1) * monospace, 0)
            glyph["advance"] = monospace

        bdf_font.glyphs[name] = glyph

    spacer = None
    if monospace and any(cells > 1 for cells in rules.cells.values()):
        if LIGATURE_SPACER_NAME in bdf_font.glyphs:
            raise ValueError(
                f"The font has a glyph named '{LIGATURE_SPACER_NAME}', which is "
                "reserved for the ligature spacer"
            )

        spacer = LIGATURE_SPACER_NAME
        bdf_font.glyphs[spacer] = {
            "character": None,
            "bitmap": np.zeros((1, 1), np.uint8),
            "offset": Vec2(0),
            "advance": monospace,
        }

    logger.info(
        "Added %d ligatures, %d run pieces and %d numeric forms",
        len(rules.ligatures),
        sum(len(pieces) for pieces in rules.lines.values())
        + sum(len(heads) for heads in rules.get_head_lists()),
        len(rules.numerics),
    )

    return {"rules": rules, "names": dict(bdf_font.names), "spacer": spacer}


def get_ligature_feature(ligatures: dict) -> list:
    """Return the lines of the calt feature, from the rules of build_ligatures().

    The lookups follow CaltRules.shape() step by step: ligatures, longest
    first, then the heads of runs, then their line characters, then numeric
    forms.

    Args:
        ligatures: The ligatures, from build_ligatures().

    Returns:
        A list of feature file lines, empty if the font has no contextual
        alternates.
    """
    rules = ligatures.get("rules")
    if rules is None or len(rules.cells) == 0:
        return []

    names = ligatures["names"]
    spacer = ligatures["spacer"]

    def glyph(char):
        return names[char]

    def slot(chars, glyph_names=()):
        items = [glyph(char) for char in chars if char in names] + list(glyph_names)
        return items[0] if len(items) == 1 else "[" + " ".join(items) + "]"

    def context(slots):
        return [slot(*item) for item in slots]

    lines = []

    # Without a spacer, each ligature substitutes from a lookup of its own,
    # referenced from the context
    if spacer is None:
        for ligature_name, chars in rules.ligatures:
            lookup_name = _get_lookup_name(ligature_name) + "_sub"
            lines.append(f"lookup {lookup_name} {{")
            lines.append(f"    sub {' '.join(glyph(c) for c in chars)} by {ligature_name};")
            lines.append(f"}} {lookup_name};")
            lines.append("")

    lines.append("feature calt {")

    # Ligatures
    for ligature_name, chars in rules.ligatures:
        lookup_name = _get_lookup_name(ligature_name)
        components = [glyph(c) for c in chars]
        marked = [components[0] + "'"] + components[1:]

        lines.append(f"    lookup {lookup_name} {{")
        for before, after in rules.get_ignored_contexts(chars):
            ignored = [glyph(c) for c in before] + marked + [glyph(c) for c in after]
            lines.append(f"        ignore sub {' '.join(ignored)};")
        if spacer is None:
            lookups = " ".join(f"{c}'" for c in components[1:])
            lines.append(f"        sub {marked[0]} lookup {lookup_name}_sub {lookups};")
        else:
            lines += _get_spaced_rules(components, [], [], ligature_name, spacer)
        lines.append(f"    }} {lookup_name};")

    # Heads of runs: between two lines, then after and before each line
    for role, step_line, index, items in rules.get_head_lookups():
        lookup_name = f"calt_run_{role}_{index}"
        if step_line is not None:
            lookup_name = f"calt_run_{role}_{glyph(step_line)}_{index}"
        lines.append(f"    lookup {lookup_name} {{")
        for head, line, name in items:
            for before, after in rules.get_head_contexts(role, line, name):
                lines += _get_spaced_rules(
                    [glyph(c) for c in head], context(before), context(after), name, spacer
                )
        lines.append(f"    }} {lookup_name};")

    # Line characters of runs
    if rules.lines:
        lines.append("    lookup calt_run_lines {")
        for line, pieces in rules.lines.items():
            left, rights = rules.get_line_contexts(line)
            left = slot(*left)
            rights = [" ".join(context(right)) for right in rights]
            for right in rights:
                lines.append(f"        sub {left} {glyph(line)}' {right} by {pieces['middle']};")
            lines.append(f"        sub {left} {glyph(line)}' by {pieces['end']};")
            for right in rights:
                lines.append(f"        sub {glyph(line)}' {right} by {pieces['start']};")
        lines.append("    } calt_run_lines;")

    # Numeric forms
    if rules.numerics:
        digits = slot(DIGITS)
        lines.append("    lookup calt_numerics {")
        for char, name in rules.numerics.items():
            lines.append(f"        sub {digits} {glyph(char)}' {digits} by {name};")
            if "0" in names:
                lines.append(f"        sub {glyph('0')} {glyph(char)}' {slot(HEX_LETTERS)} by {name};")
        lines.append("    } calt_numerics;")

    lines.append("} calt;")
    lines.append("")

    return lines


def _get_spaced_rules(
    components: list, backtrack: list, lookahead: list, name: str, spacer: str
) -> list:
    """Return the rules that turn each component into the spacer, and the
    last one into the glyph. The rule for the last component comes first, as
    the earlier components are already spacers when it applies."""
    rules = []
    for index in reversed(range(len(components))):
        context = backtrack + [spacer] * index
        context.append(components[index] + "'")
        context += components[index + 1 :] + lookahead
        target = name if index == len(components) - 1 else spacer
        rules.append(f"        sub {' '.join(context)} by {target};")

    return rules


def _get_lookup_name(ligature_name: str) -> str:
    """Return the calt lookup name of a ligature."""
    return "calt_" + ligature_name.rsplit(".", 1)[0]
