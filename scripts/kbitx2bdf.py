#!/usr/bin/env python3
# Converts a Bits'N'Picas .kbitx font to a .bdf font, the way the BDF exporter
# of Bits'N'Picas does: encoded glyphs in code point order, named glyphs last
# with ENCODING -1 (not counted in CHARS).
import argparse

from kbitfont import KbitFont


def quote(value):
    return '"' + value.replace('"', '""') + '"'


def get_bitmap_rows(glyph):
    rows = []
    for bitmap_row in glyph.bitmap:
        row = bytearray((len(bitmap_row) + 7) // 8)
        for x, color in enumerate(bitmap_row):
            if color >= 0x80:
                row[x // 8] |= 0x80 >> (x % 8)
        rows.append(row.hex().upper() or "00")
    return rows


def convert(font):
    props = font.props
    names = font.names

    # Font bounding box, from the encoded glyphs
    left = right = top = bottom = 0
    for glyph in font.characters.values():
        left = min(left, glyph.x)
        right = max(right, glyph.x + glyph.width)
        top = max(top, glyph.y)
        bottom = max(bottom, glyph.height - glyph.y)

    pixel_size = props.line_ascent + props.line_descent
    style = names.style or "Regular"
    slant = "I" if "italic" in style.lower() or "oblique" in style.lower() else "R"

    lines = [
        "STARTFONT 2.1",
        f"FONT -{names.manufacturer}-{names.family}-{style}-{slant}-{style}"
        f"--{pixel_size}-{pixel_size}-75-75-c-80-iso10646-1",
        f"SIZE {pixel_size} 75 75",
        f"FONTBOUNDINGBOX {right - left} {top + bottom} {left} {-bottom}",
    ]

    properties = []
    for key, value in (
        ("FAMILY_NAME", names.family),
        ("WEIGHT_NAME", names.style),
        ("FONT_VERSION", names.version),
        ("COPYRIGHT", names.copyright),
        ("FOUNDRY", names.manufacturer),
    ):
        if value is not None:
            properties.append(f"{key} {quote(value)}")
    properties += [
        f"FONT_ASCENT {props.line_ascent}",
        f"FONT_DESCENT {props.line_descent}",
        f"POINT_SIZE {props.em_ascent + props.em_descent}",
        f"X_HEIGHT {props.x_height}",
        f"CAP_HEIGHT {props.cap_height}",
    ]

    lines.append(f"STARTPROPERTIES {len(properties)}")
    lines += properties
    lines.append("ENDPROPERTIES")
    lines.append(f"CHARS {len(font.characters)}")

    glyphs = [
        (f"U+{code_point:04X}", code_point, glyph)
        for code_point, glyph in sorted(font.characters.items())
    ]
    glyphs += [(name, -1, glyph) for name, glyph in font.named_glyphs.items()]

    for name, encoding, glyph in glyphs:
        lines += [
            f"STARTCHAR {name}",
            f"ENCODING {encoding}",
            f"SWIDTH {1000 * glyph.advance // (right - left)} 0",
            f"DWIDTH {glyph.advance} 0",
            f"BBX {glyph.width} {glyph.height} {glyph.x} {glyph.y - glyph.height}",
            "BITMAP",
        ]
        lines += get_bitmap_rows(glyph)
        lines.append("ENDCHAR")

    lines.append("ENDFONT")

    return lines


parser = argparse.ArgumentParser(description="Converts a .kbitx font to a .bdf font.")
parser.add_argument("input", help="the .kbitx file")
parser.add_argument("output", help="the .bdf file")
args = parser.parse_args()

font = KbitFont.load_kbitx(args.input)

with open(args.output, "w", encoding="utf-8", newline="\r\n") as bdf_file:
    bdf_file.write("\n".join(convert(font)) + "\n")
