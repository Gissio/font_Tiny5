"""
bdf2ufo

Small caps building for BDF to UFO font conversion.

(C) 2024-2026 Gissio
License: MIT
"""

import logging
import unicodedata as python_unicodedata
from typing import NamedTuple, Optional

import unicodedata2 as unicodedata

from .bdf_font import BDFFont
from .ccmp import get_ccmp_substitutes
from .data import (
    MARKS,
    SMALL_CAPS_ALIASES,
    SMALL_CAPS_LOWERCASE,
    SMALL_CAPS_SCRIPTS,
)
from .decomposition import get_bitmap, get_element_positions, get_pieces
from .utils import Vec2, format_unicode_character, get_glyph_name

# Constants
SMALL_CAPS_SUFFIX = ".sc"

# Definitions
logger = logging.getLogger(__name__)


class _BuiltGlyph(NamedTuple):
    """A small cap glyph built for an accented letter."""

    description: str
    positions: set
    advance_glyph_name: str
    components: Optional[list] = None
    anchors: Optional[dict] = None


def build_small_caps(
    bdf_font: BDFFont, components: dict, anchors: dict, ccmp: dict
) -> dict:
    """Build the Latin and Cyrillic small caps of the smcp and c2sc features.

    The small cap of a lowercase letter is, in order of preference:
    - the glyph named after the letter with a ".sc" suffix, such as "x.sc" or
      "uni0431.sc";
    - an existing glyph: the letter itself if it is in SMALL_CAPS_LOWERCASE
      (its lowercase is drawn as a small cap, such as Cyrillic "в") or is a
      Unicode small capital (U+0280), its Unicode small capital (U+1D00 for
      "a"), or the small cap of the letter in SMALL_CAPS_ALIASES ("i" for
      "ı");
    - for an accented letter whose base letter is its own small cap, the
      letter itself;
    - for any other accented letter, a new ".sc" glyph built from the small
      cap of its base letter and the accents of its capital, moved by the
      difference between the base anchors of the small cap and the capital
      base, such as "top". If the font has no such capital, the marks of the
      canonical decomposition are attached with their mark anchors instead.

    A letter that is its own small cap is substituted by a ".sc" copy of
    itself, a glyph with the letter as its only component, so that smcp and
    c2sc change the glyph, as shaping checks such as Shaperglot's expect.

    No anchors are assumed for small caps: they only have the anchors that the
    font configuration gives them. A warning lists the base anchors of a
    capital that its small cap lacks.

    A script only gets substitutions when every base letter of its alphabet in
    SMALL_CAPS_SCRIPTS has a small cap. The substitutions of each script are
    kept apart, so that a glyph that ccmp substitutes for a letter of another
    script, such as "i" for U+0456, takes the small cap of the script of the
    text.

    The new glyphs are added to the BDF font and, when they are composed, to
    the components and, with the anchors propagated from their marks, to the
    anchors.

    Args:
        bdf_font: The BDF font object.
        components: Dictionary of glyph components.
        anchors: Dictionary of glyph anchors.
        ccmp: The ccmp substitutions, from build_ccmp().

    Returns:
        Dictionary mapping "smcp" and "c2sc" to the substitutions of each
        feature, as a dictionary mapping an OpenType script tag to the
        substitutions of that script, from source glyph name to small cap
        glyph name.
    """
    builder = _SmallCapsBuilder(bdf_font, components, anchors)

    complete_script_tags = builder.get_complete_script_tags()

    smcp = {}
    c2sc = {}

    for character, glyph_name in list(bdf_font.names.items()):
        script = SMALL_CAPS_SCRIPTS.get(_get_script(character))
        if script is None:
            continue

        script_tag = script[0]
        category = unicodedata.category(character)

        # Lowercase letters with an uppercase form, so that IPA letters keep
        # their shape
        if category == "Ll" and (
            _get_uppercase(character) != character or character in SMALL_CAPS_ALIASES
        ):
            feature, lowercase, capital = smcp, character, _get_uppercase(character)
        elif category == "Lu":
            feature, lowercase, capital = c2sc, _get_lowercase(character), character
        else:
            continue

        is_base_letter = len(unicodedata.normalize("NFD", lowercase)) == 1
        is_complete = script_tag in complete_script_tags

        # Accented small caps of an incomplete script would never be used
        if not is_complete and not is_base_letter:
            continue

        small_cap_name = builder.get_small_cap(lowercase, capital)

        if small_cap_name is None:
            if (
                feature is smcp
                and is_base_letter
                and "SMALL CAPITAL" not in unicodedata.name(character)
            ):
                logger.info(
                    "%s has no small cap, %s%s could be added",
                    format_unicode_character(character),
                    glyph_name,
                    SMALL_CAPS_SUFFIX,
                )
            continue

        if not is_complete:
            continue

        builder.check_anchors(small_cap_name, capital)

        # A letter that is its own small cap is substituted by its copy
        if small_cap_name == builder.bdf_font.names.get(lowercase):
            small_cap_name = builder.get_copy(small_cap_name)

        substitutions = feature.setdefault(script_tag, {})
        substitutions[glyph_name] = small_cap_name

        if feature is smcp:
            for substitute_name in get_ccmp_substitutes(ccmp, glyph_name):
                substitutions[substitute_name] = small_cap_name

    for script_tag, _alphabet in SMALL_CAPS_SCRIPTS.values():
        logger.info(
            "Small caps (%s): %d smcp and %d c2sc substitutions",
            script_tag,
            len(smcp.get(script_tag, {})),
            len(c2sc.get(script_tag, {})),
        )
    logger.info("Small caps: %d new glyphs", builder.built_count)

    return {"smcp": smcp, "c2sc": c2sc}


class _SmallCapsBuilder:
    def __init__(self, bdf_font: BDFFont, components: dict, anchors: dict) -> None:
        self.bdf_font = bdf_font
        self.components = components
        self.anchors = anchors

        self.built = {}
        self.built_count = 0
        self.checked = set()

    def check_anchors(self, small_cap_name: str, capital: str) -> None:
        """Warn about the base anchors of a capital that its small cap lacks.

        Small caps have the anchors of the font configuration only, none are
        assumed. Small caps that are built from a capital and the marks of the
        base small cap are left out, as they inherit its anchors.

        Args:
            small_cap_name: The glyph name of the small cap.
            capital: The capital of the letter.
        """
        if small_cap_name in self.checked or small_cap_name in self.built.values():
            return
        self.checked.add(small_cap_name)

        capital_name = self.bdf_font.names.get(capital)
        capital_anchors = self.anchors.get(capital_name, {})
        small_cap_anchors = self.anchors.get(small_cap_name, {})

        missing = [
            anchor_name
            for anchor_name in capital_anchors
            if not anchor_name.startswith("_") and anchor_name not in small_cap_anchors
        ]
        if missing:
            logger.warning(
                "%s has no %s anchor, which %s has",
                small_cap_name,
                ", ".join(f"'{anchor_name}'" for anchor_name in sorted(missing)),
                capital_name,
            )

    def get_complete_script_tags(self) -> set:
        """Return the scripts whose basic alphabet has small caps throughout.

        Scripts the font does not cover are left out silently, the others with
        the letters that lack a small cap.
        """
        complete_script_tags = set()

        for script_tag, alphabet in SMALL_CAPS_SCRIPTS.values():
            # Accented letters, such as U+0439, follow from their base letters
            letters = [
                letter
                for letter in alphabet
                if letter in self.bdf_font.names
                and len(unicodedata.normalize("NFD", letter)) == 1
            ]
            if not letters:
                continue

            missing = [letter for letter in letters if self.get_small_cap(letter) is None]
            if missing:
                logger.info(
                    "Small caps (%s) left out, %d of %d letters have no small cap: %s",
                    script_tag,
                    len(missing),
                    len(letters),
                    " ".join(missing),
                )
            else:
                complete_script_tags.add(script_tag)

        return complete_script_tags

    def get_small_cap(
        self, lowercase: str, capital: Optional[str] = None
    ) -> Optional[str]:
        """Return the small cap glyph name of a lowercase letter, or None.

        Args:
            lowercase: The lowercase letter. It can also be a letter followed by
                marks, for a capital that lowercases to several characters,
                such as U+0130.
            capital: The capital of the letter, by default its uppercase.

        Returns:
            The glyph name, or None.
        """
        if capital is None:
            capital = _get_uppercase(lowercase)

        if len(lowercase) == 1:
            base_name = self._get_name(lowercase)
        else:
            base_name = _lowercase_glyph_name(self.bdf_font.names[capital])

        small_cap_name = base_name + SMALL_CAPS_SUFFIX
        if small_cap_name in self.bdf_font.glyphs:
            return small_cap_name

        if len(lowercase) == 1:
            existing_name = self._get_existing_small_cap(lowercase)
            if existing_name is not None:
                return existing_name

        decomposition = unicodedata.normalize("NFD", lowercase)
        if len(decomposition) == 1:
            return None

        # An accented letter whose base letter is its own small cap
        if _is_own_small_cap(decomposition[0]) and lowercase in self.bdf_font.names:
            return self.bdf_font.names[lowercase]

        return self._build_small_cap(small_cap_name, decomposition, capital)

    def get_copy(self, glyph_name: str) -> str:
        """Return the ".sc" copy of a letter that is its own small cap.

        The copy has the letter as its only component, so that it cannot drift
        from it.

        Args:
            glyph_name: The glyph name of the letter.

        Returns:
            The glyph name of the copy.
        """
        copy_name = glyph_name + SMALL_CAPS_SUFFIX
        if copy_name in self.bdf_font.glyphs:
            return copy_name

        glyph = self.bdf_font.glyphs[glyph_name]
        self.bdf_font.glyphs[copy_name] = {
            "character": None,
            "bitmap": glyph["bitmap"],
            "offset": glyph["offset"],
            "advance": glyph["advance"],
        }
        self.components[copy_name] = [(glyph_name, Vec2(0))]
        if glyph_name in self.anchors:
            self.anchors[copy_name] = dict(self.anchors[glyph_name])

        logger.info("%s copied from %s", copy_name, glyph_name)

        self.built_count += 1

        return copy_name

    def _get_existing_small_cap(self, character: str) -> Optional[str]:
        """Return an existing glyph that is the small cap of a letter, or None."""
        if _is_own_small_cap(character) and character in self.bdf_font.names:
            return self.bdf_font.names[character]

        unicode_small_cap = _get_unicode_small_cap(character)
        if unicode_small_cap in self.bdf_font.names:
            return self.bdf_font.names[unicode_small_cap]

        if character in SMALL_CAPS_ALIASES:
            return self.get_small_cap(SMALL_CAPS_ALIASES[character])

        return None

    def _build_small_cap(
        self, small_cap_name: str, decomposition: str, capital: str
    ) -> Optional[str]:
        """Build the small cap glyph of an accented letter.

        Args:
            small_cap_name: The name of the glyph to build.
            decomposition: The canonical decomposition of the lowercase letter.
            capital: The capital of the letter.

        Returns:
            The glyph name, or None if the glyph cannot be built.
        """
        if small_cap_name in self.built:
            return self.built[small_cap_name]

        self.built[small_cap_name] = None

        capital_name = self.bdf_font.names.get(capital)
        if capital_name in self.components:
            built = self._compose_from_capital(small_cap_name, capital_name)
        else:
            built = None
            if capital_name is not None:
                built = self._draw_from_capital(small_cap_name, capital_name)
            if built is None:
                built = self._compose_from_marks(small_cap_name, decomposition)

        if built is None:
            return None

        # The bitmap is drawn when there are no components, or when they
        # overlap
        bitmap, offset = get_bitmap(built.positions)
        self.bdf_font.glyphs[small_cap_name] = {
            "character": None,
            "bitmap": bitmap,
            "offset": offset,
            "advance": self.bdf_font.glyphs[built.advance_glyph_name]["advance"],
        }
        if built.components:
            self.components[small_cap_name] = built.components
        if built.anchors:
            self.anchors[small_cap_name] = built.anchors

        logger.info("%s %s", small_cap_name, built.description)

        self.built[small_cap_name] = small_cap_name
        self.built_count += 1

        return small_cap_name

    def _compose_from_capital(
        self, small_cap_name: str, capital_name: str
    ) -> Optional[_BuiltGlyph]:
        """Compose a small cap from the marks of its composed capital.

        The innermost base of the capital, such as "A" for U+01FA, is replaced
        by its small cap, and every mark of the capital attaches with its mark
        anchor to the base anchor of the small cap, or of the previous mark of
        the same anchor, as on a lowercase letter. Where the capital draws its
        marks is not used, and no anchor is assumed: a small cap without the
        anchor of a mark is not built.
        """
        pieces = get_pieces(self.components, capital_name)

        capital_base_name, _capital_base_offset = pieces[0]
        base_name = self._get_base_small_cap(
            small_cap_name, capital_name, capital_base_name
        )
        if base_name is None:
            return None

        glyph_components = [(base_name, Vec2(0))]
        glyph_anchors = dict(self.anchors.get(base_name, {}))

        for piece_name, _piece_offset in pieces[1:]:
            piece_character = self.bdf_font.glyphs[piece_name]["character"]
            if piece_character not in MARKS:
                logger.warning(
                    "%s is not built, %s is not a mark", small_cap_name, piece_name
                )
                return None

            offset = self._get_mark_offset(
                small_cap_name,
                base_name,
                glyph_anchors,
                piece_name,
                MARKS[piece_character][0],
                logging.WARNING,
            )
            if offset is None:
                return None

            glyph_components.append((piece_name, offset))

            self._propagate_anchors(glyph_anchors, piece_name, offset)

        return self._get_composed_glyph(
            f"composed from {capital_name}", glyph_components, glyph_anchors
        )

    def _draw_from_capital(
        self, small_cap_name: str, capital_name: str
    ) -> Optional[_BuiltGlyph]:
        """Draw a small cap from the bitmap of its capital.

        The accent pixels of the capital, those that are not part of its base
        letter, move onto the small cap of the base letter. All marks of the
        capital must be positioned by the same base anchor.
        """
        capital_character = self.bdf_font.glyphs[capital_name]["character"]
        capital_decomposition = unicodedata.normalize("NFD", capital_character)

        capital_base_name = self.bdf_font.names.get(capital_decomposition[0])
        if capital_base_name is None or len(capital_decomposition) < 2:
            return None

        anchor_names = {
            MARKS[mark][0] if mark in MARKS else None
            for mark in capital_decomposition[1:]
        }
        if len(anchor_names) != 1 or None in anchor_names:
            return None

        capital_positions = set(self._get_element_positions(capital_name))
        capital_base_positions = set(self._get_element_positions(capital_base_name))
        if not capital_base_positions <= capital_positions:
            return None

        base_name = self._get_base_small_cap(
            small_cap_name, capital_name, capital_base_name
        )
        if base_name is None:
            return None

        delta = self._get_anchor_delta(
            small_cap_name, base_name, capital_base_name, anchor_names.pop()
        )
        if delta is None:
            return None

        positions = set(self._get_element_positions(base_name)) | {
            (x + int(delta.x), y + int(delta.y))
            for x, y in capital_positions - capital_base_positions
        }

        return _BuiltGlyph(f"drawn from {capital_name}", positions, base_name)

    def _compose_from_marks(
        self, small_cap_name: str, decomposition: str
    ) -> Optional[_BuiltGlyph]:
        """Attach the marks of a decomposition to its small cap base.

        Each mark attaches with its mark anchor to the base anchor of the small
        cap, or of the previous mark of the same anchor.
        """
        base_name = self.get_small_cap(decomposition[0])
        if base_name is None:
            return None

        glyph_components = [(base_name, Vec2(0))]
        glyph_anchors = dict(self.anchors.get(base_name, {}))

        for mark_character in decomposition[1:]:
            if (
                mark_character not in MARKS
                or mark_character not in self.bdf_font.names
            ):
                logger.info(
                    "%s could be composed with %s",
                    small_cap_name,
                    format_unicode_character(mark_character),
                )
                return None

            mark_name = self.bdf_font.names[mark_character]

            offset = self._get_mark_offset(
                small_cap_name,
                base_name,
                glyph_anchors,
                mark_name,
                MARKS[mark_character][0],
            )
            if offset is None:
                return None

            glyph_components.append((mark_name, offset))

            self._propagate_anchors(glyph_anchors, mark_name, offset)

        return self._get_composed_glyph("composed", glyph_components, glyph_anchors)

    def _get_composed_glyph(
        self, description: str, glyph_components: list, glyph_anchors: dict
    ) -> _BuiltGlyph:
        positions = {
            (x + int(component_offset.x), y + int(component_offset.y))
            for component_name, component_offset in glyph_components
            for x, y in self._get_element_positions(component_name)
        }
        component_names = ", ".join(name for name, _offset in glyph_components)

        return _BuiltGlyph(
            f"{description} with [{component_names}]",
            positions,
            glyph_components[0][0],
            glyph_components,
            glyph_anchors,
        )

    def _get_base_small_cap(
        self, small_cap_name: str, capital_name: str, capital_base_name: str
    ) -> Optional[str]:
        capital_character = self.bdf_font.glyphs[capital_name]["character"]
        capital_base_character = self.bdf_font.glyphs[capital_base_name]["character"]

        # A capital composed from a letter of another script keeps its script
        if capital_base_character is not None and _get_script(
            capital_base_character
        ) == _get_script(capital_character):
            lowercase = _get_lowercase(capital_base_character)

            if len(lowercase) == 1 and lowercase != capital_base_character:
                base_name = self.get_small_cap(lowercase)

                if base_name is not None:
                    return base_name

        logger.info(
            "%s could be built with a small cap of %s",
            small_cap_name,
            capital_base_name,
        )

        return None

    def _get_anchor_delta(
        self,
        small_cap_name: str,
        base_name: str,
        capital_base_name: str,
        anchor_name: str,
    ) -> Optional[Vec2]:
        """Return how far an accent moves from a capital base to a small cap."""
        base_anchors = self.anchors.get(base_name, {})
        capital_base_anchors = self.anchors.get(capital_base_name, {})

        if anchor_name not in base_anchors:
            self._log_missing_anchor(small_cap_name, anchor_name, base_name)
            return None

        if anchor_name not in capital_base_anchors:
            self._log_missing_anchor(small_cap_name, anchor_name, capital_base_name)
            return None

        return base_anchors[anchor_name] - capital_base_anchors[anchor_name]

    def _get_mark_offset(
        self,
        small_cap_name: str,
        base_name: str,
        glyph_anchors: dict,
        mark_name: str,
        anchor_name: str,
        level: int = logging.INFO,
    ) -> Optional[Vec2]:
        """Return where a mark attaches to the anchors of a small cap."""
        mark_anchors = self.anchors.get(mark_name, {})

        if anchor_name not in glyph_anchors:
            self._log_missing_anchor(small_cap_name, anchor_name, base_name, level)
            return None

        if f"_{anchor_name}" not in mark_anchors:
            self._log_missing_anchor(
                small_cap_name, f"_{anchor_name}", mark_name, level
            )
            return None

        return glyph_anchors[anchor_name] - mark_anchors[f"_{anchor_name}"]

    def _log_missing_anchor(
        self,
        small_cap_name: str,
        anchor_name: str,
        glyph_name: str,
        level: int = logging.INFO,
    ) -> None:
        logger.log(
            level,
            "%s could be built with a '%s' anchor on %s",
            small_cap_name,
            anchor_name,
            glyph_name,
        )

    def _propagate_anchors(
        self, glyph_anchors: dict, mark_name: str, offset: Vec2
    ) -> None:
        # The base anchors of an attached mark replace those of the glyph, so
        # that the next mark stacks on it
        for anchor_name, anchor_offset in self.anchors.get(mark_name, {}).items():
            if not anchor_name.startswith("_"):
                glyph_anchors[anchor_name] = anchor_offset + offset

    def _get_element_positions(self, glyph_name: str) -> list:
        return get_element_positions(self.bdf_font, self.components, glyph_name)

    def _get_name(self, character: str) -> str:
        if character in self.bdf_font.names:
            return self.bdf_font.names[character]

        return get_glyph_name(ord(character))


def _get_script(character: Optional[str]) -> str:
    """Return the script word of a character's Unicode name, such as "LATIN"."""
    if character is None:
        return ""

    return unicodedata.name(character, "").split(" ", 1)[0]


def _get_uppercase(character: str) -> str:
    """Return the uppercase of a letter, or the letter if it has none."""
    return _get_case(character, character.upper(), "SMALL LETTER ", "CAPITAL LETTER ")


def _get_lowercase(character: str) -> str:
    """Return the lowercase of a letter, or the letter if it has none."""
    return _get_case(character, character.lower(), "CAPITAL LETTER ", "SMALL LETTER ")


def _get_case(character: str, mapped: str, word: str, other_word: str) -> str:
    """Return the other case of a letter, by name if Python cannot map it.

    The case mapping of str follows the Unicode version of Python, which may
    be older than unicodedata2: Python 3.12 knows U+0264 but not its capital
    U+A7CB, from Unicode 16. A letter whose case pair is newer than Python's
    Unicode is mapped by name instead, such as LATIN SMALL LETTER RAMS HORN to
    LATIN CAPITAL LETTER RAMS HORN.
    """
    if mapped != character or len(character) != 1:
        return mapped

    name = unicodedata.name(character, "")
    if word not in name:
        return character

    try:
        other = unicodedata.lookup(name.replace(word, other_word, 1))
    except KeyError:
        return character

    # Letters that Python knows without a case pair, such as U+0138, keep it
    if "Cn" not in (
        python_unicodedata.category(character),
        python_unicodedata.category(other),
    ):
        return character

    return other


def _is_own_small_cap(character: str) -> bool:
    """Report whether a lowercase letter is drawn as its own small cap.

    These are the letters in SMALL_CAPS_LOWERCASE and the Unicode small
    capitals, such as U+0280.
    """
    return (
        character in SMALL_CAPS_LOWERCASE
        or "SMALL CAPITAL" in unicodedata.name(character, "")
    )


def _get_unicode_small_cap(character: str) -> Optional[str]:
    """Return the Unicode small capital of a lowercase letter, or None.

    For instance, LATIN SMALL LETTER A maps to LATIN LETTER SMALL CAPITAL A,
    LATIN SMALL LIGATURE OE to LATIN LETTER SMALL CAPITAL OE, CYRILLIC SMALL
    LETTER EL to CYRILLIC LETTER SMALL CAPITAL EL and LATIN SMALL LETTER U BAR
    to LATIN SMALL CAPITAL LETTER U WITH STROKE.
    """
    script = _get_script(character)
    name = unicodedata.name(character, "")

    for prefix in (f"{script} SMALL LETTER ", f"{script} SMALL LIGATURE "):
        if name.startswith(prefix):
            letter = name[len(prefix):]
            break
    else:
        return None

    # Some small capitals have their own word order, and "U BAR" is "U WITH
    # STROKE" among them
    letters = [letter]
    if letter.endswith(" BAR") and " WITH " not in letter:
        letters.append(letter[: -len(" BAR")] + " WITH STROKE")

    for candidate in letters:
        for small_capital_name in (
            f"{script} LETTER SMALL CAPITAL {candidate}",
            f"{script} SMALL CAPITAL LETTER {candidate}",
        ):
            try:
                return unicodedata.lookup(small_capital_name)
            except KeyError:
                pass

    return None


def _lowercase_glyph_name(glyph_name: str) -> str:
    """Lowercase the first letter of an AGL glyph name, such as "Idotaccent".

    "uniXXXX" and "uXXXXXX" names are left as they are.
    """
    return glyph_name[0].lower() + glyph_name[1:]
