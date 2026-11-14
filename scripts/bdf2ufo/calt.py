"""
bdf2ufo

Contextual alternates (calt) of a font: ligatures, runs and numeric forms.

This module only depends on the standard library, so that tools other than
the build, such as a specimen generator, can shape text the way the calt
feature does, without a text shaper.

(C) 2024-2026 Gissio
License: MIT
"""

import re

from .data import (
    LIGATURE_FIRST,
    LIGATURE_SPACER_NAME,
    LIGATURE_SUFFIX,
    NUMERIC_SUFFIX,
    SEQUENCE_LINE_ORDER,
    SEQUENCE_ROLES,
    SEQUENCE_SUFFIX,
)

DIGITS = "0123456789"
HEX_LETTERS = "ABCDEFabcdef"

# A slot is one position of a context: (characters, glyph names). It matches
# a character that keeps its own glyph and is one of the characters, or a
# glyph that is one of the glyph names.
SPACER_SLOT = ((), (LIGATURE_SPACER_NAME,))


class CaltRules:
    """The contextual alternates of a font, from the names of its glyphs.

    * A ligature ("hyphen_hyphen_greater.liga") replaces a fixed sequence of
      characters. It forms only where the character before it or after it
      does not continue it: not where its first or last character repeats,
      and not where it is part of a longer run. So "<=" forms in "a <= b",
      "a<=-1" and "-<=", but not in "<==" or "<=>", which are runs, "<<" not
      in "<<-" and "!=" not in "=!=". "|>" still forms in "|>-", and "!=" in
      "!=>", as they are not part of the run. A ligature drawn like its
      characters keeps them from forming a run or another ligature.
    * A run is a line of any length, such as "--", "---->", "<==>" or "####".
      Each of its characters becomes a piece one cell wide: a line character
      the start, middle or end piece of its line ("hyphen_start.seq"), and a
      head before or after the line, which may be several characters, a piece
      as many cells wide ("less_less_hyphen_start.seq" for the "<<" of "<<-",
      "greater_hyphen_end.seq" for the ">" of "->"). A head between two lines,
      such as the middle "|" of "|---|---|", joins both
      ("bar_hyphen_middle.seq"). A head whose name repeats the line character
      needs a line of two cells next to it: "less_equal_equal_end.seq" makes
      "==<" and "<=<" runs, but not "a=<b". Middle heads are tried first,
      then, line by line, "=" before "-", the heads after a line and those
      before one. So the ">" of "=>-" ends "=>", and the ">" of "-->==" starts
      ">==", as in Fira Code.
    * A numeric form ("x.num") replaces a character between two digits, or
      between "0" and a hexadecimal letter, as in "1920x1080" or "0xFF".

    Ligatures come first, longest first, then runs, then numeric forms, so a
    ligature that is a whole operator, such as "<=", wins over a run. Of the
    same length, the ligatures of LIGATURE_FIRST come first, as in Fira Code:
    "--" forms in "--<|", whose "<" the earlier "<|" takes.

    Attributes:
        ligatures: List of (glyph name, characters), longest first.
        starts: Dictionary from line characters to lists of (head characters,
            glyph name), longest first, of the heads before a line.
        ends: Same for the heads after a line.
        middles: Same for the heads between two lines.
        lines: Dictionary from line characters to dictionaries from roles to
            glyph names.
        numerics: Dictionary from characters to their numeric forms.
        cells: Dictionary from the glyph names to the cells they span.
        long_heads: Set of the names of the heads that need a line of two
            cells next to them.
    """

    def __init__(self, glyph_names, characters: dict, warn=None) -> None:
        """Read the contextual alternates from glyph names.

        Args:
            glyph_names: The names of the unencoded glyphs to read.
            characters: Dictionary from the names of the encoded glyphs to
                their characters.
            warn: Function called with a message for each glyph left out.
        """
        warn = warn or (lambda message: None)

        self.ligatures = []
        self.starts = {}
        self.ends = {}
        self.middles = {}
        self.lines = {}
        self.numerics = {}
        self.cells = {}
        self.long_heads = set()
        self._cache = {}

        for name in glyph_names:
            if name.endswith(LIGATURE_SUFFIX):
                parts = name.removesuffix(LIGATURE_SUFFIX).split("_")
                chars = _get_characters(name, parts, characters, warn)
                if chars is None:
                    continue
                if len(chars) < 2:
                    warn(f"Ligature '{name}' has fewer than two characters, skipping")
                    continue
                self.ligatures.append((name, chars))
                self.cells[name] = len(chars)

            elif name.endswith(SEQUENCE_SUFFIX):
                parts = name.removesuffix(SEQUENCE_SUFFIX).split("_")
                role = parts.pop()
                if role not in SEQUENCE_ROLES or len(parts) == 0:
                    warn(
                        f"Run piece '{name}' does not end in a character and "
                        f"one of {', '.join(SEQUENCE_ROLES)}, skipping"
                    )
                    continue
                chars = _get_characters(name, parts, characters, warn)
                if chars is not None:
                    self._add_piece(name, role, chars, warn)

            elif name.endswith(NUMERIC_SUFFIX):
                parts = [name.removesuffix(NUMERIC_SUFFIX)]
                chars = _get_characters(name, parts, characters, warn)
                if chars is not None:
                    self.numerics[chars[0]] = name
                    self.cells[name] = 1

        # A run needs all three pieces of its line
        for line in sorted(set(self.lines) | set(self.starts) | set(self.ends) | set(self.middles)):
            missing = [role for role in SEQUENCE_ROLES if role not in self.lines.get(line, {})]
            if missing:
                names = self._remove_line(line)
                warn(
                    f"Runs of '{line}' have no {', '.join(missing)} piece, "
                    f"skipping {', '.join(sorted(names))}"
                )

        # Longer first, so that "-->" is tried before "->", and "<<-" before "<-",
        # and of the same length, those of LIGATURE_FIRST first
        def order(ligature):
            text = "".join(ligature[1])
            first = LIGATURE_FIRST.index(text) if text in LIGATURE_FIRST else len(LIGATURE_FIRST)
            return (-len(ligature[1]), first)

        self.ligatures.sort(key=order)
        for heads in self.get_head_lists():
            heads.sort(key=lambda head: -len(head[0]))

    def _add_piece(self, name: str, role: str, chars: tuple, warn) -> None:
        """Add a run piece: a line piece, or a head of its role."""
        line, head = chars[-1], chars[:-1]
        if len(head) == 0:
            self.lines.setdefault(line, {})[role] = name
            self.cells[name] = 1
            return

        # A head named with its line character twice needs a line of two
        # cells next to it
        if head[-1] == line:
            head = head[:-1]
            if role == "middle" or len(head) == 0 or head[-1] == line:
                warn(
                    f"Run piece '{name}' repeats its line character, which only "
                    "a head before or after a line may do, and only once, skipping"
                )
                return
            self.long_heads.add(name)

        self._get_heads(role).setdefault(line, []).append((head, name))
        self.cells[name] = len(head)

    def _get_heads(self, role: str) -> dict:
        """Return the heads of a role."""
        return {"start": self.starts, "end": self.ends, "middle": self.middles}[role]

    def remove(self, name: str) -> str:
        """Remove a glyph from the rules. A line character loses its runs with
        any of its line pieces.

        Args:
            name: The glyph name.

        Returns:
            The line character whose runs were removed, or None.
        """
        self._cache = {}
        self.cells.pop(name, None)
        self.ligatures = [ligature for ligature in self.ligatures if ligature[0] != name]
        self.numerics = {char: alt for char, alt in self.numerics.items() if alt != name}
        for heads in (self.starts, self.ends, self.middles):
            for line in heads:
                heads[line] = [head for head in heads[line] if head[1] != name]

        removed_line = next(
            (line for line, pieces in self.lines.items() if name in pieces.values()), None
        )
        if removed_line is not None:
            self._remove_line(removed_line)

        return removed_line

    def _remove_line(self, line: str) -> list:
        """Remove the runs of a line character, and return their glyph names."""
        names = [
            name
            for heads in (self.starts, self.ends, self.middles)
            for _head, name in heads.pop(line, [])
        ]
        names += list(self.lines.pop(line, {}).values())
        for name in names:
            self.cells.pop(name, None)

        return names

    def _cached(self, key, compute):
        """Return a value computed once until the rules change."""
        if key not in self._cache:
            self._cache[key] = compute()
        return self._cache[key]

    def get_head_lists(self) -> list:
        """Return the lists of heads of every line and role."""
        return [heads for role in (self.starts, self.ends, self.middles) for heads in role.values()]

    def has_runs(self) -> bool:
        """Return whether the font has runs."""
        return len(self.lines) > 0

    # Contexts

    def get_continuations(self, line: str, head_chars: bool = False) -> list:
        """Return what continues a line after one of its characters: the line
        character, or a head after the line or between two lines, which is
        already in place, as alternative lists of slots. With head_chars, the
        first character of such a head also continues it ("|=!", as in Fira
        Code).
        """
        heads = self.ends.get(line, []) + self.middles.get(line, [])
        chars = (line,)
        if head_chars:
            chars += tuple(sorted({head[0] for head, _name in heads}))
        singles = tuple(name for head, name in heads if len(head) == 1)
        alternatives = [[(chars, singles)]]
        alternatives += [
            [SPACER_SLOT] * (len(head) - 1) + [((), (name,))] for head, name in heads if len(head) > 1
        ]

        return alternatives

    def get_head_contexts(self, role: str, line: str, name: str) -> list:
        """Return the contexts in which a head forms, as alternative pairs of
        lists of slots (backtrack, lookahead): its line before or after it,
        and for a head that needs a line of two cells, also the cell beyond:
        another line character or a head of the line.
        """

        def compute():
            line_slot = ((line,), ())
            before = [line_slot] if role != "start" else []
            after = [line_slot] if role != "end" else []
            if name not in self.long_heads:
                return [(before, after)]
            if role == "end":
                chars = (line,) + tuple(head[-1] for head, _name in self.starts.get(line, []))
                names = tuple(name for _head, name in self.middles.get(line, []))
                return [([(chars, names)] + before, after)]
            return [(before, after + alt) for alt in self.get_continuations(line, True)]

        return self._cached(("head", role, line, name), compute)

    def get_line_contexts(self, line: str) -> tuple:
        """Return the contexts of a line character: the slot after which it
        continues a run (its start and middle pieces, and the heads before or
        between lines), and the alternatives before which it goes on.
        """
        names = [self.lines[line]["start"], self.lines[line]["middle"]]
        names += [name for _head, name in self.starts.get(line, []) + self.middles.get(line, [])]

        return ((), tuple(names)), self.get_continuations(line)

    # Runs as character sequences, for the contexts of ligatures

    def get_run_patterns(self) -> list:
        """Return the shortest sequences that form runs: two line characters,
        and each head with its line or lines."""

        def compute():
            patterns = []
            for line in self.lines:
                starts = [head for head, _name in self.starts.get(line, [])]
                middles = [head for head, _name in self.middles.get(line, [])]
                patterns.append((line, line))
                patterns += [(line,) + head + (line,) for head in middles]
                for head, name in self.starts.get(line, []):
                    if name in self.long_heads:
                        chars = self.get_continuations(line, True)[0][0][0]
                        patterns += [head + (line, char) for char in chars]
                    else:
                        patterns.append(head + (line,))
                for head, name in self.ends.get(line, []):
                    if name in self.long_heads:
                        patterns.append((line, line) + head)
                        patterns += [start + (line,) + head for start in starts]
                        patterns += [(line,) + middle + (line,) + head for middle in middles]
                    else:
                        patterns.append((line,) + head)
            return patterns

        return self._cached("patterns", compute)

    def is_run(self, chars: tuple) -> bool:
        """Return whether characters form one run: an optional head before a
        line, its line characters, which middle heads may divide, and an
        optional head after it. A head that needs a line of two cells counts
        with a line of one cell before what may continue it ("|=!")."""
        text = "".join(chars)
        for line in self.lines:
            for head, name in self.starts.get(line, []):
                if (
                    name in self.long_heads
                    and len(chars) == len(head) + 2
                    and chars[:-1] == head + (line,)
                    and chars[-1] in self.get_continuations(line, True)[0][0][0]
                ):
                    return True

            match = self._get_run_regex(line).fullmatch(text)
            if len(chars) < 2 or not match:
                continue
            start, end = match.group("start") or "", match.group("end") or ""
            if self._is_long(self.ends, line, end) and len(match.group("body")) < 2:
                continue
            if self._is_long(self.starts, line, start) and len(text) - len(start) < 2:
                continue
            return True

        return False

    def _get_run_regex(self, line: str):
        """Return the regular expression of the runs of a line."""

        def heads(role):
            items = ["".join(map(re.escape, head)) for head, _name in role.get(line, [])]
            return "(?:" + "|".join(items) + ")" if items else "(?!)"

        def compute():
            line_chars = re.escape(line) + "+"
            return re.compile(
                f"(?P<body>(?P<start>{heads(self.starts)})?{line_chars}"
                f"(?:{heads(self.middles)}{line_chars})*)(?P<end>{heads(self.ends)})?"
            )

        return self._cached(("regex", line), compute)

    def _is_long(self, heads: dict, line: str, text: str) -> bool:
        """Return whether a head, given as text, needs a line of two cells."""
        return any(
            "".join(head) == text and name in self.long_heads for head, name in heads.get(line, [])
        )

    def get_ignored_contexts(self, chars: tuple) -> list:
        """Return the contexts that keep a ligature from forming: its first
        character before it, its last character after it, and every context
        in which it is part of a longer run. So "<=" does not form in "<=="
        or "<=>", nor "<<" in "<<-", nor "!=" in "=!=", but "!=" forms in
        "!=>", "|>" in "|>-" and "<=" in "-<=".

        Returns:
            A sorted list of (characters before, characters after).
        """

        def compute():
            contexts = {((chars[0],), ()), ((), (chars[-1],))}
            for run in self.get_run_patterns():
                # The run starts at "offset" from the ligature's first character
                for offset in range(1 - len(run), len(chars)):
                    end = offset + len(run)
                    if not (offset < 0 < end or offset < len(chars) < end):
                        continue
                    inside = range(max(0, offset), min(len(chars), end))
                    if not all(chars[i] == run[i - offset] for i in inside):
                        continue
                    before = run[: max(0, -offset)]
                    after = run[len(chars) - offset :] if end > len(chars) else ()
                    if self.is_run(before + chars + after):
                        contexts.add((before, after))
            return sorted(contexts)

        return self._cached(("ignored", chars), compute)

    # Order of the substitutions

    def get_head_lookups(self) -> list:
        """Return the lookups that substitute heads, in order: the heads
        between two lines, then for each line, "=" before "-"
        (SEQUENCE_LINE_ORDER), the heads after it, then those before it. Each
        role of a line has one lookup for each head of several cells, longest
        first, so that its spacers are its own, then one for the heads of a
        single cell.

        Returns:
            A list of (role, line character or None for the middle heads,
            index, list of (head characters, line character, glyph name)).
        """

        def compute():
            order = SEQUENCE_LINE_ORDER
            lines = sorted(
                set(self.starts) | set(self.ends),
                key=lambda line: (order.index(line) if line in order else len(order), line),
            )
            steps = [("middle", None, self.middles)]
            for line in lines:
                steps.append(("end", line, {line: self.ends.get(line, [])}))
                steps.append(("start", line, {line: self.starts.get(line, [])}))

            lookups = []
            for role, step_line, heads in steps:
                items = [(head, line, name) for line, pairs in heads.items() for head, name in pairs]
                multis = sorted(
                    (item for item in items if len(item[0]) > 1),
                    key=lambda item: (-len(item[0]), item[2]),
                )
                singles = [item for item in items if len(item[0]) == 1]
                passes = [[item] for item in multis] + ([singles] if singles else [])
                lookups += [(role, step_line, index, items) for index, items in enumerate(passes)]
            return lookups

        return self._cached("lookups", compute)

    def shape(self, text: str) -> list:
        """Shape a line of text as the calt feature of a monospace font does.

        Args:
            text: The text.

        Returns:
            A list as long as the text, with None for a character that keeps
            its own glyph, or the name of the glyph that replaces it: the
            spacer, or a glyph whose drawing reaches back over the cells of
            the spacers before it.
        """
        glyphs = [None] * len(text)

        def fits(index, slots):
            for i, (chars, names) in enumerate(slots, index):
                if not 0 <= i < len(text):
                    return False
                if not (glyphs[i] in names or (glyphs[i] is None and text[i] in chars)):
                    return False
            return True

        def raw(chars):
            return [((char,), ()) for char in chars]

        def substitute(index, cells, name):
            for i in range(cells - 1):
                glyphs[index + i] = LIGATURE_SPACER_NAME
            glyphs[index + cells - 1] = name

        # Ligatures
        for name, chars in self.ligatures:
            contexts = self.get_ignored_contexts(chars)
            index = 0
            while index <= len(text) - len(chars):
                if fits(index, raw(chars)) and not any(
                    fits(index - len(before), raw(before + chars + after))
                    for before, after in contexts
                ):
                    substitute(index, len(chars), name)
                    index += len(chars)
                else:
                    index += 1

        # Heads between two lines, then after and before each line
        for role, _line, _index, items in self.get_head_lookups():
            index = 0
            while index < len(text):
                for head, line, name in items:
                    if fits(index, raw(head)) and any(
                        fits(index - len(before), before) and fits(index + len(head), after)
                        for before, after in self.get_head_contexts(role, line, name)
                    ):
                        substitute(index, len(head), name)
                        index += len(head) - 1
                        break
                index += 1

        # Line characters
        for index, char in enumerate(text):
            if char not in self.lines or glyphs[index] is not None:
                continue
            left, rights = self.get_line_contexts(char)
            after_run = fits(index - 1, [left])
            before_run = any(fits(index + 1, right) for right in rights)
            if after_run or before_run:
                role = "middle" if after_run and before_run else "end" if after_run else "start"
                glyphs[index] = self.lines[char][role]

        # Numeric forms
        for index, char in enumerate(text):
            if char in self.numerics and glyphs[index] is None:
                between_digits = fits(index - 1, [(DIGITS, ())]) and fits(index + 1, [(DIGITS, ())])
                hexadecimal = fits(index - 1, [("0", ())]) and fits(index + 1, [(HEX_LETTERS, ())])
                if between_digits or hexadecimal:
                    glyphs[index] = self.numerics[char]

        return glyphs


def _get_characters(name: str, parts: list, characters: dict, warn) -> tuple:
    """Return the characters of the glyph names that a glyph name lists, or
    None if one is not an encoded glyph."""
    chars = []
    for part in parts:
        if part not in characters:
            warn(f"'{name}' names '{part}', which is not an encoded glyph of the font, skipping")
            return None
        chars.append(characters[part])

    return tuple(chars)
