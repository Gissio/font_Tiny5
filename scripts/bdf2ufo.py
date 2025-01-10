# bdf2ufo
# Converts a .bdf pixel font to a .ufo variable vector font
#
# (C) 2024-2025 Gissio
#
# License: MIT
#

import argparse
from datetime import datetime
import math
import os
import random
import shutil
import sys

import bdflib.reader
import fontTools.designspaceLib
import fontTools.feaLib.builder
import fontTools.feaLib.ast
import fontTools.misc.transform
import fontTools.ufoLib
import fontTools.misc
import numpy as np
import unicodedata
import ufoLib2
import ufoLib2.objects
import ufoLib2.objects.anchor


# Definitions

log_level = 1
bdf2ufo_version = '1.0.1'

width_class_from_name = {
    'UltraCondensed': 1,
    'ExtraCondensed': 2,
    'Condensed': 3,
    'SemiCondensed': 4,
    'Normak': 5,
    'SemiExpanded': 6,
    'Expanded': 7,
    'ExtraExpanded': 8,
    'UltraExpanded': 9,
}

weight_class_from_name = {
    'Thin': 100,
    'ExtraLight': 200,
    'Light': 300,
    'Regular': 400,
    'Medium': 500,
    'SemiBold': 600,
    'Bold': 700,
    'ExtraBold': 800,
    'Black': 900
}

slope_from_slant = {
    'I': 'Italic',
    'RI': 'Italic',
    'O': 'Oblique',
    'RO': 'Oblique',
}

combining_infos = {
    0x300: ('grave accent', 'top', 0x2cb),
    0x301: ('acute accent', 'top.shifted', 0x2ca),
    0x302: ('circumflex accent', 'top', 0x2c6),
    0x303: ('tilde', 'top.shifted', 0x2dc),
    0x304: ('macron', 'top', 0x2c9),
    0x306: ('breve', 'top', 0x2d8),
    0x307: ('dot above', 'top', 0x2d9),
    0x308: ('diaeresis', 'top', 0xa8),
    0x309: ('hook above', 'top', None),
    0x30a: ('ring above', 'top', 0x2da),
    0x30b: ('double acute accent', 'top.shifted', 0x2dd),
    0x30c: ('caron', 'top', 0x2c7),
    0x30d: ('vertical line above', 'top', 0x2c8),
    0x30f: ('double grave accent', 'top', 0x2f5),
    0x311: ('inverted breve', 'top', 0x1aff),
    0x313: ('comma above', 'top', 0x2c),
    0x314: ('reversed comma above', 'top', None),
    0x315: ('comma above right', 'top.right', 0x2c),
    0x31b: ('horn', 'horn', None),
    0x323: ('dot below', 'bottom', 0x2d9),
    0x324: ('diaeresis below', 'bottom', 0xa8),
    0x325: ('ring below', 'bottom', 0x2da),
    0x326: ('comma below', 'bottom', 0x2c),
    0x327: ('cedilla', 'cedilla', 0xb8),
    0x328: ('ogonek', 'ogonek', 0x2db),
    0x32d: ('circumflex accent below', 'bottom', 0x2c6),
    0x32e: ('breve below', 'bottom', 0x2d8),
    0x32f: ('inverted breve below', 'bottom', 0x1aff),
    0x330: ('tilde below', 'bottom.shifted', 0x2dc),
    0x331: ('macron below', 'bottom', 0x2c9),
    0x332: ('low line', 'top', 0x5f),
    0x335: ('short stroke overlay', 'overlay', None),
    0x342: ('greek perispomeni', 'top.shifted', 0x2dc),
    0x343: ('greek koronis', 'top', 0x2c),
    0x344: ('greek dialytika tonos', 'top', 0xa8),
    0x345: ('greek ypogegrammeni', 'bottom', 0x37a),
    0x359: ('asterisk below', 'bottom', None),
    0x35c: ('double breve below', 'bottom', None),
    0x35f: ('double macron below', 'bottom', 0x2ed),
    0x1dc4: ('macron acute', 'top', None),
    0x1dc5: ('grave macron', 'top', None),
    0x1dc6: ('macron grave', 'top', None),
    0x1dc7: ('acute macron', 'top', None),
    0x1dca: ('latin small letter r below', 'bottom', None),
}

custom_decomposition = {
    0x69: '0131 0307',
    0x6a: '0237 0307',
    0xec: '0131 0300',
    0xed: '0131 0301',
    0xee: '0131 0302',
    0xef: '0131 0308',
    0x10f: '0064 02bc',
    0x122: '0047 0326',
    0x123: '0067 02bb',
    0x129: '0131 0303',
    0x12b: '0131 0304',
    0x12d: '0131 0306',
    0x135: '0237 0302',
    0x136: '004B 0326',
    0x137: '006B 0326',
    0x13b: '004C 0326',
    0x13c: '006C 0326',
    0x13d: '004C 02bc',
    0x13e: '006C 02bc',
    0x145: '004E 0326',
    0x146: '006E 0326',
    0x156: '0052 0326',
    0x157: '0072 0326',
    0x165: '0074 02bc',
    0x17f: '',
    0x1d0: '0131 030c',
    0x1f0: '0237 030c',
    0x209: '0131 030f',
    0x20b: '0131 0311',
    0x385: '0308 0301',
    0x457: '0131 0308',
    0x1ec9: '0131 0309',
    0x1e06: '0042 0331',
    0x1e07: '0062 0331',
    0x1e0e: '0044 0331',
    0x1e0f: '0064 0331',
    0x1e34: '004b 0331',
    0x1e35: '006b 0331',
    0x1e3a: '004c 0331',
    0x1e3b: '006c 0331',
    0x1e48: '004e 0331',
    0x1e49: '006e 0331',
    0x1e5e: '0052 0331',
    0x1e5f: '0072 0331',
    0x1e6e: '0054 0331',
    0x1e6f: '0074 0331',
    0x1e94: '005a 0331',
    0x1e95: '007a 0331',
    0x1f00: '03b1 1fbf',
    0x1f01: '03b1 1ffe',
    0x1f02: '03b1 1fcd',
    0x1f03: '03b1 1fdd',
    0x1f04: '03b1 1fce',
    0x1f05: '03b1 1fde',
    0x1f08: '0391 1fbf',
    0x1f09: '0391 1ffe',
    0x1f0a: '0391 1fcd',
    0x1f0b: '0391 1fdd',
    0x1f0c: '0391 1fce',
    0x1f0d: '0391 1fde',
    0x1f10: '03b5 1fbf',
    0x1f11: '03b5 1ffe',
    0x1f12: '03b5 1fcd',
    0x1f13: '03b5 1fdd',
    0x1f14: '03b5 1fce',
    0x1f15: '03b5 1fde',
    0x1f18: '0395 1fbf',
    0x1f19: '0395 1ffe',
    0x1f1a: '0395 1fcd',
    0x1f1b: '0395 1fdd',
    0x1f1c: '0395 1fce',
    0x1f1d: '0395 1fde',
    0x1f20: '03b7 1fbf',
    0x1f21: '03b7 1ffe',
    0x1f22: '03b7 1fcd',
    0x1f23: '03b7 1fdd',
    0x1f24: '03b7 1fce',
    0x1f25: '03b7 1fde',
    0x1f28: '0397 1fbf',
    0x1f29: '0397 1ffe',
    0x1f2a: '0397 1fcd',
    0x1f2b: '0397 1fdd',
    0x1f2c: '0397 1fce',
    0x1f2d: '0397 1fde',
    0x1f30: '03b9 1fbf',
    0x1f31: '03b9 1ffe',
    0x1f32: '03b9 1fcd',
    0x1f33: '03b9 1fdd',
    0x1f34: '03b9 1fce',
    0x1f35: '03b9 1fde',
    0x1f38: '0399 1fbf',
    0x1f39: '0399 1ffe',
    0x1f3a: '0399 1fcd',
    0x1f3b: '0399 1fdd',
    0x1f3c: '0399 1fce',
    0x1f3d: '0399 1fde',
    0x1f40: '03bf 1fbf',
    0x1f41: '03bf 1ffe',
    0x1f42: '03bf 1fcd',
    0x1f43: '03bf 1fdd',
    0x1f44: '03bf 1fce',
    0x1f45: '03bf 1fde',
    0x1f48: '039f 1fbf',
    0x1f49: '039f 1ffe',
    0x1f4a: '039f 1fcd',
    0x1f4b: '039f 1fdd',
    0x1f4c: '039f 1fce',
    0x1f4d: '039f 1fde',
    0x1f50: '03c5 1fbf',
    0x1f51: '03c5 1ffe',
    0x1f52: '03c5 1fcd',
    0x1f53: '03c5 1fdd',
    0x1f54: '03c5 1fce',
    0x1f55: '03c5 1fde',
    0x1f59: '03a5 1ffe',
    0x1f5b: '03a5 1fdd',
    0x1f5d: '03a5 1fde',
    0x1f60: '03c9 1fbf',
    0x1f61: '03c9 1ffe',
    0x1f62: '03c9 1fcd',
    0x1f63: '03c9 1fdd',
    0x1f64: '03c9 1fce',
    0x1f65: '03c9 1fde',
    0x1f68: '03a9 1fbf',
    0x1f69: '03a9 1ffe',
    0x1f6a: '03a9 1fcd',
    0x1f6b: '03a9 1fdd',
    0x1f6c: '03a9 1fce',
    0x1f6d: '03a9 1fde',
    0x1fbd: '',
    0x1fbe: '037a',
    0x1fbf: '',
    0x1fc1: '0308 0342',
    0x1fe4: '03c1 1fbf',
    0x1fe5: '03c1 1ffe',
    0x1fed: '0308 0300',
    0x1fee: '0308 0301',
    0x1ff9: '039f 0301',
    0x2116: '004e 00ba',
}

custom_anchors = [
    0x3b6, 0x3b8, 0x3b9, 0x3ba, 0x3bc, 0x3be, 0x3bf,
    0x1f02, 0x1f03, 0x1f04, 0x1f05, 0x1f08, 0x1f09, 0x1f0a, 0x1f0b, 0x1f0c, 0x1f0d,
    0x1f12, 0x1f13, 0x1f14, 0x1f15, 0x1f18, 0x1f19, 0x1f1a, 0x1f1b, 0x1f1c, 0x1f1d,
    0x1f22, 0x1f23, 0x1f24, 0x1f25, 0x1f28, 0x1f29, 0x1f2a, 0x1f2b, 0x1f2c, 0x1f2d,
    0x1f32, 0x1f33, 0x1f34, 0x1f35, 0x1f38, 0x1f39, 0x1f3a, 0x1f3b, 0x1f3c, 0x1f3d,
    0x1f42, 0x1f43, 0x1f44, 0x1f45, 0x1f48, 0x1f49, 0x1f4a, 0x1f4b, 0x1f4c, 0x1f4d,
    0x1f52, 0x1f53, 0x1f54, 0x1f55, 0x1f59, 0x1f5b, 0x1f5c,
    0x1f62, 0x1f63, 0x1f64, 0x1f65, 0x1f68, 0x1f69, 0x1f6a, 0x1f6b, 0x1f6c, 0x1f6d,
    0x1f82, 0x1f83, 0x1f84, 0x1f85, 0x1f88, 0x1f89, 0x1f8a, 0x1f8b, 0x1f8c, 0x1f8d,
    0x1f92, 0x1f93, 0x1f94, 0x1f95, 0x1f98, 0x1f99, 0x1f9a, 0x1f9b, 0x1f9c, 0x1f9d,
    0x1fa2, 0x1fa3, 0x1fa4, 0x1fa5, 0x1fa8, 0x1fa9, 0x1faa, 0x1fab, 0x1fac, 0x1fad,
    0x1fba, 0x1fbb,
    0x1fc1, 0x1fc8, 0x1fc9, 0x1fca, 0x1fcb, 0x1fcd, 0x1fce, 0x1fcf,
    0x1fda, 0x1fdb, 0x1fdd, 0x1fde, 0x1fdf,
    0x1fea, 0x1feb, 0x1fec, 0x1fed, 0x1fee,
    0x1ff8, 0x1ff9, 0x1ffa, 0x1ffb
]

# ID: Label, min, max, default
axes_info = {
    'ESIZ': {'name': 'Element Size', 'min': 0.1, 'max': 1, 'default': 1},
    'ROND': {'name': 'Roundness', 'min': 0, 'max': 1, 'default': 0},
    'BLED': {'name': 'Bleed', 'min': 0, 'max': 1, 'default': 0},
    'XESP': {'name': 'Horizontal Element Spacing', 'min': 0.5, 'max': 1, 'default': 1},
    'EJIT': {'name': 'Element Jitter', 'min': 0, 'max': 0.1, 'default': 0},
}


# Helper functions
class Object(object):
    pass


def auto_int(x):
    return int(x, 0)


def log_info(message):
    if log_level <= 0:
        print('info: ' + message)


def log_warning(message):
    if log_level <= 1:
        print('warning: ' + message)


def log_error(message):
    if log_level <= 2:
        print('error: ' + message)

    sys.exit(1)


def combine_strings(a, b):
    return (a + ' ' + b).strip()


def get_unicode_string(codepoint):
    return 'U+' + f'{codepoint:04x}'


def get_decomposition_string(decomposition):
    return ', '.join([get_unicode_string(codepoint) for codepoint in decomposition])


def match_codepoint(codepoint_range, codepoint):
    if codepoint_range == '':
        return True

    for token in codepoint_range.split(','):
        element = token.split('-', 1)
        if len(element) == 1:
            if codepoint == int(element[0], 0):
                return True
        else:
            if codepoint >= int(element[0], 0) and\
                    codepoint <= int(element[1], 0):
                return True

    return False


def get_bdf_property(bdf, key, default_value):
    key = key.encode('utf-8')

    if key in bdf.properties:
        value = bdf.properties[key]
        if isinstance(value, int):
            return value

        else:
            return value.decode('utf-8')

    else:
        return default_value


def filter_name(name):
    return ''.join([c for c in name.lower() if c.isalpha()])


def set_font_property(font, config, key, default_value):
    value = getattr(config, key)

    if value is not None:
        setattr(font, key, value)

    else:
        setattr(font, key, default_value)


def get_file_name(family_name, style_name):
    return family_name.replace(' ', '') + '-' +\
        style_name.replace(' ', '')


def get_style_map_names(family_name, style_name):
    style_map_family_names = [family_name]
    bold = False
    italic = False

    for style in style_name.split(' '):
        if style == 'Bold':
            bold = True
        elif style == 'Italic':
            italic = True
        elif style != 'Regular':
            style_map_family_names.append(style)

    if not bold:
        if not italic:
            style_map_style_name = 'regular'
        else:
            style_map_style_name = 'italic'
    else:
        if not italic:
            style_map_style_name = 'bold'
        else:
            style_map_style_name = 'bold italic'

    return ' '.join(style_map_family_names), style_map_style_name


def parse_axes_string(axes_string):
    axes = {}

    if axes_string == None:
        return axes

    for axis_string in axes_string.split(','):
        if axis_string == '':
            continue

        axis_components = axis_string.split('=', 2)
        axis = axis_components[0]

        if axis not in axes_info:
            log_error(
                f'invalid axis {axis} in parameter: {axes_string}')

        if len(axis_components) == 1:
            axes[axis] = 0
        elif len(axis_components) == 2:
            axes[axis] = float(axis_components[1])

    return axes


# Main functions
def load_font(config):
    font_boundingbox0 = [sys.maxsize, sys.maxsize]
    font_boundingbox1 = [-sys.maxsize, -sys.maxsize]

    font = Object()

    with open(config.input, 'rb') as handle:
        bdf = bdflib.reader.read_bdf(handle)

        font.glyphs = {}
        font.codepoints = {}

        cap_height = bdf.ptSize
        x_height = bdf.ptSize

        # Set font glyphs
        for glyph in bdf.glyphs:
            codepoint = glyph.codepoint

            name = glyph.name.decode('utf-8')

            if codepoint == config.notdef_codepoint:
                name = '.notdef'

            else:
                if not match_codepoint(config.codepoint_subset, codepoint):
                    continue

                # Sanitize glyph name
                if not name[0].isalnum():
                    name = '_' + name

                name = ''.join(
                    [c if (c.isalnum() or c == '.') else '_' for c in name])

                while name in font.glyphs:
                    name += '_'

            # Build bitmap
            bitmap = np.zeros((glyph.bbH, glyph.bbW), np.uint8)
            for y in range(glyph.bbH):
                value = glyph.data[y]
                for x in range(glyph.bbW):
                    bitmap[y][x] = (value >> (glyph.bbW - x - 1)) & 1

            # Crop bitmap
            if bitmap.any():
                bitmap_coords = np.argwhere(bitmap)
                y_min, x_min = bitmap_coords.min(axis=0)
                y_max, x_max = bitmap_coords.max(axis=0)
                y_max += 1
                x_max += 1

            else:
                y_min, x_min = 0, 0
                y_max, x_max = 1, 1

            bitmap = bitmap[y_min:y_max,
                            x_min:x_max]

            # Update font bounding box
            boundingbox0 = (glyph.bbY + int(y_min),
                            glyph.bbX + int(x_min))
            boundingbox1 = (boundingbox0[0] + bitmap.shape[0],
                            boundingbox0[1] + bitmap.shape[1])

            font_boundingbox0[0] = min(font_boundingbox0[0], boundingbox0[0])
            font_boundingbox0[1] = min(font_boundingbox0[1], boundingbox0[1])
            font_boundingbox1[0] = max(font_boundingbox1[0], boundingbox1[0])
            font_boundingbox1[1] = max(font_boundingbox1[1], boundingbox1[1])

            advance = glyph.advance

            # Build glyph
            glyph = Object()
            glyph.codepoint = codepoint
            glyph.bitmap = bitmap
            glyph.offset = boundingbox0
            glyph.advance = advance

            if codepoint == 0x41:
                cap_height = bitmap.shape[0]
            elif codepoint == 0x78:
                x_height = bitmap.shape[0]

            font.glyphs[name] = glyph
            font.codepoints[codepoint] = name

        # Add undefined combining glyphs
        for combining_codepoint in combining_infos:
            _, _, modifier_codepoint = combining_infos[combining_codepoint]

            if modifier_codepoint in font.codepoints and\
                    combining_codepoint not in font.codepoints and\
            match_codepoint(config.codepoint_subset, combining_codepoint):
                modifier_name = font.codepoints[modifier_codepoint]
                modifier_glyph = font.glyphs[modifier_name]

                combining_name = f'uni{combining_codepoint:04x}'

                combining_glyph = Object()
                combining_glyph.codepoint = combining_codepoint
                combining_glyph.bitmap = modifier_glyph.bitmap
                combining_glyph.offset = modifier_glyph.offset
                combining_glyph.advance = modifier_glyph.advance

                font.glyphs[combining_name] = combining_glyph
                font.codepoints[combining_codepoint] = combining_name

        # Set font info
        set_font_property(font, config, 'font_version',
                          get_bdf_property(bdf, 'FONT_VERSION', ''))
        set_font_property(font, config, 'family_name',
                          get_bdf_property(bdf, 'FAMILY_NAME', bdf.name.decode('utf-8')))

        style_name = ''

        # Style width
        setwidth_name = filter_name(get_bdf_property(bdf, 'SETWIDTH_NAME', ''))
        style_component = ''
        for name in width_class_from_name:
            if name.lower() == setwidth_name:
                style_component = name
                break
        style_name = combine_strings(style_name, style_component)

        # Style weight
        weight_name = filter_name(get_bdf_property(bdf, 'WEIGHT_NAME', ''))
        style_component = 'Regular'
        for name in weight_class_from_name:
            if name.lower() == weight_name:
                style_component = name
                break
        style_name = combine_strings(style_name, style_component)

        # Style slope
        slant = filter_name(get_bdf_property(bdf, 'SLANT', ''))
        if slant in slope_from_slant:
            style_name = combine_strings(style_name, slope_from_slant[slant])
        set_font_property(font, config, 'style_name', style_name)

        # Font properties
        copyright = '\n'.join([s.decode('utf-8') for s in bdf.comments])
        set_font_property(font, config, 'copyright',
                          get_bdf_property(bdf, 'COPYRIGHT',
                                           copyright))
        set_font_property(font, config, 'designer', '')
        set_font_property(font, config, 'designer_url', '')
        set_font_property(font, config, 'manufacturer',
                          get_bdf_property(bdf, 'FOUNDRY', ''))
        set_font_property(font, config, 'manufacturer_url', '')
        set_font_property(font, config, 'license', '')
        set_font_property(font, config, 'license_url', '')

        set_font_property(font, config, 'ascent',
                          get_bdf_property(bdf, 'FONT_ASCENT', bdf.ptSize))
        set_font_property(font, config, 'descent',
                          -get_bdf_property(bdf, 'FONT_DESCENT', 0))
        set_font_property(font, config, 'cap_height',
                          get_bdf_property(bdf, 'CAP_HEIGHT', cap_height))
        set_font_property(font, config, 'x_height',
                          get_bdf_property(bdf, 'X_HEIGHT', x_height))

        set_font_property(font, config, 'underline_position',
                          get_bdf_property(bdf, 'UNDERLINE_POSITION', 0))
        set_font_property(font, config, 'underline_thickness',
                          get_bdf_property(bdf, 'UNDERLINE_THICKNESS', 0))
        set_font_property(font, config, 'strikeout_position',
                          get_bdf_property(bdf, 'STRIKEOUT_ASCENT', 0))
        set_font_property(font, config, 'strikeout_thickness',
                          get_bdf_property(bdf, 'STRIKEOUT_DESCENT', 0))

        set_font_property(font, config, 'superscript_scale_x', 0.6)
        set_font_property(font, config, 'superscript_scale_y', 0.6)
        set_font_property(font, config, 'superscript_offset_x', 0)
        set_font_property(font, config, 'superscript_offset_y',
                          font.cap_height * font.superscript_scale_y)
        set_font_property(font, config, 'subscript_scale_x', 0.6)
        set_font_property(font, config, 'subscript_scale_y', 0.6)
        set_font_property(font, config, 'subscript_offset_x', 0)
        set_font_property(font, config, 'subscript_offset_y', 0)

        font.boundingbox = (font_boundingbox0, font_boundingbox1)
        font.glyph_scale_x = config.glyph_scale_x
        font.glyph_scale_y = config.glyph_scale_y
        font.glyph_offset_x = config.glyph_offset_x
        font.glyph_offset_y = config.glyph_offset_y
        font.units_per_em = config.units_per_em
        font.strike_num = 2 if config.double_strike else 1

        font.variable_axes = [
            key for key in parse_axes_string(config.variable_axes)]

        font.variable_instances = []
        if len(font.variable_axes) > 0:
            for instance_string in config.variable_instance:
                instance = Object()

                components = instance_string.split(',')
                instance.name = components[0]
                instance.location = parse_axes_string(
                    ','.join(components[1:]))

                font.variable_instances.append(instance)

        else:
            instance = Object()
            instance.name = ''
            instance.location = []

            font.variable_instances.append(instance)

        font.location = {}
        for axis in axes_info:
            font.location[axis] = axes_info[axis]['default']
        location = parse_axes_string(config.static_axes)
        for axis in location:
            font.location[axis] = location[axis]

        font.units_per_element_y = int(font.units_per_em /
                                       (font.ascent - font.descent))

    return font


def add_offset(a, b):
    return (a[0] + b[0], a[1] + b[1])


def subtract_offset(a, b):
    return (a[0] - b[0], a[1] - b[1])


def get_units_per_element_x(font):
    return font.location['XESP'] * font.glyph_scale_x * font.units_per_element_y


def set_ufo_info(ufo_font, font):
    # Ascenders and descenders
    line_ascender = font.ascent * font.units_per_element_y
    line_descender = font.descent * font.units_per_element_y
    line_height = line_ascender - line_descender

    em_descender = line_descender - \
        int((font.units_per_em - line_height) / 2)
    em_ascender = font.units_per_em + em_descender

    # Width and weight class
    width_class = 5
    weight_class = 400
    for style_component in font.style_name.split(' '):
        if style_component in width_class_from_name:
            width_class = width_class_from_name[style_component]
        if style_component in weight_class_from_name:
            weight_class = weight_class_from_name[style_component]

    # Version
    version_components = font.font_version.split(';', 2)
    if version_components[0].startswith('Version '):
        version_components[0] = version_components[8:]
    font_version = 'Version ' + ';'.join(version_components)

    version_number_components = version_components[0].split('.')
    version_majorminor = (1, 0)
    if len(version_number_components) == 2:
        try:
            version_number_components = (
                int(version_number_components[0]),
                int(version_number_components[1]))
        except:
            pass

    # Set info
    ufo_info = ufo_font.info

    ufo_info.familyName = font.family_name
    ufo_info.styleName = font.style_name
    ufo_info.styleMapFamilyName, ufo_info.styleMapStyleName = get_style_map_names(
        font.family_name, font.style_name)
    ufo_info.versionMajor, ufo_info.versionMinor = version_majorminor

    ufo_info.copyright = font.copyright
    ufo_info.unitsPerEm = font.units_per_em
    ufo_info.descender = em_descender
    ufo_info.xHeight = font.x_height * font.units_per_element_y
    ufo_info.capHeight = font.cap_height * font.units_per_element_y
    ufo_info.ascender = em_ascender

    ufo_info.guidelines = []

    ufo_info.openTypeHheaAscender = line_ascender
    ufo_info.openTypeHheaDescender = line_descender
    ufo_info.openTypeHheaLineGap = 0

    ufo_info.openTypeNameDesigner = font.designer
    ufo_info.openTypeNameDesignerURL = font.designer_url
    ufo_info.openTypeNameManufacturer = font.manufacturer
    ufo_info.openTypeNameManufacturerURL = font.manufacturer_url
    ufo_info.openTypeNameLicense = font.license
    ufo_info.openTypeNameLicenseURL = font.license_url
    ufo_info.openTypeNameVersion = font_version

    ufo_info.openTypeOS2WidthClass = width_class
    ufo_info.openTypeOS2WeightClass = weight_class
    ufo_info.openTypeOS2VendorID = 'B2UF'
    ufo_info.openTypeOS2TypoAscender = ufo_info.openTypeHheaAscender
    ufo_info.openTypeOS2TypoDescender = ufo_info.openTypeHheaDescender
    ufo_info.openTypeOS2TypoLineGap = ufo_info.openTypeHheaLineGap
    ufo_info.openTypeOS2WinAscent = max(
        font.boundingbox[1][0] * font.units_per_element_y, 0)
    ufo_info.openTypeOS2WinDescent = max(
        -font.boundingbox[0][0] * font.units_per_element_y, 0)
    ufo_info.openTypeOS2SubscriptXSize = int(
        font.subscript_scale_x * font.units_per_em)
    ufo_info.openTypeOS2SubscriptYSize = int(
        font.subscript_scale_y * font.units_per_em)
    ufo_info.openTypeOS2SubscriptXOffset = int(
        font.subscript_offset_x * font.units_per_element_y)
    ufo_info.openTypeOS2SubscriptYOffset = int(
        font.subscript_offset_y * font.units_per_element_y)
    ufo_info.openTypeOS2SuperscriptXSize = int(
        font.superscript_scale_x * font.units_per_em)
    ufo_info.openTypeOS2SuperscriptYSize = int(
        font.superscript_scale_y * font.units_per_em)
    ufo_info.openTypeOS2SuperscriptXOffset = int(
        font.superscript_offset_x * font.units_per_element_y)
    ufo_info.openTypeOS2SuperscriptYOffset = int(
        font.superscript_offset_y * font.units_per_element_y)
    ufo_info.openTypeOS2StrikeoutSize = int(
        font.strikeout_thickness * font.units_per_element_y)
    ufo_info.openTypeOS2StrikeoutPosition = int(
        font.strikeout_position * font.units_per_element_y)

    ufo_info.postscriptUnderlineThickness = int(
        font.underline_thickness * font.units_per_element_y)
    ufo_info.postscriptUnderlinePosition = int(
        font.underline_position * font.units_per_element_y)


def add_element_glyph(ufo_font, font):
    units_per_pixel = font.location['ESIZ'] * font.units_per_element_y
    unit = units_per_pixel / 2
    radius = font.location['ROND'] * unit

    # Cubic curves
    tangent = radius * (4 / 3) * math.tan(math.radians(90 / 4))
    max_x = unit + font.location['BLED'] * \
        (get_units_per_element_x(font) - unit)
    max_y = unit
    min_x = max_x - radius
    min_y = max_y - radius
    tangent_x = min_x + tangent
    tangent_y = min_y + tangent

    element_points = [
        [(min_y, max_x), 'curve'],
        [(-min_y, max_x), 'line'],
        [(-tangent_y, max_x), 'offcurve'],
        [(-max_y, tangent_x), 'offcurve'],
        [(-max_y, min_x), 'curve'],
        [(-max_y, -min_x), 'line'],
        [(-max_y, -tangent_x), 'offcurve'],
        [(-tangent_y, -max_x), 'offcurve'],
        [(-min_y, -max_x), 'curve'],
        [(min_y, -max_x), 'line'],
        [(tangent_y, -max_x), 'offcurve'],
        [(max_y, -tangent_x), 'offcurve'],
        [(max_y, -min_x), 'curve'],
        [(max_y, min_x), 'line'],
        [(max_y, tangent_x), 'offcurve'],
        [(tangent_y, max_x), 'offcurve'],
    ]

    # Quadratic curves
    # midarc = radius * math.cos(math.radians(45))
    # tangent = radius * (4 / 3) * math.tan(math.radians(90 / 4))
    # max_x = unit + font.location['BLED'] * (2 * units_per_pixel - unit)
    # max_y = unit
    # min_x = max_x - radius
    # min_y = max_y - radius
    # tangent_x = min_x + tangent
    # tangent_y = min_y + tangent
    # midarc_x = min_x + midarc
    # midarc_y = min_y + midarc

    # element_points = [
    #     [(min_y, max_x), 'qcurve'],
    #     [(-min_y, max_x), 'line'],
    #     [(-tangent_y, max_x), 'offcurve'],
    #     [(-midarc_y, midarc_x), 'qcurve'],
    #     [(-max_y, tangent_x), 'offcurve'],
    #     [(-max_y, min_x), 'qcurve'],
    #     [(-max_y, -min_x), 'line'],
    #     [(-max_y, -tangent_x), 'offcurve'],
    #     [(-midarc_y, -midarc_x), 'qcurve'],
    #     [(-tangent_y, -max_x), 'offcurve'],
    #     [(-min_y, -max_x), 'qcurve'],
    #     [(min_y, -max_x), 'line'],
    #     [(tangent_y, -max_x), 'offcurve'],
    #     [(midarc_y, -midarc_x), 'qcurve'],
    #     [(max_y, -tangent_x), 'offcurve'],
    #     [(max_y, -min_x), 'qcurve'],
    #     [(max_y, min_x), 'line'],
    #     [(max_y, tangent_x), 'offcurve'],
    #     [(midarc_y, midarc_x), 'qcurve'],
    #     [(tangent_y, max_x), 'offcurve'],
    # ]

    ufo_points = []
    for point_offset, point_type in element_points:
        ufo_points.append(
            ufoLib2.objects.Point(
                point_offset[1],
                point_offset[0],
                point_type)
        )
    ufo_contour = ufoLib2.objects.Contour(ufo_points)

    ufo_glyph = ufo_font.newGlyph('_')
    ufo_glyph.appendContour(ufo_contour)


def paint_glyph(composed_bitmap,
                component_bitmap,
                offset,
                bitmap):
    for y in range(component_bitmap.shape[0]):
        for x in range(component_bitmap.shape[1]):
            if component_bitmap[y][x]:
                bitmap_y = offset[0] + y
                bitmap_x = offset[1] + x

                if not composed_bitmap[bitmap_y][bitmap_x]:
                    return False

                bitmap[bitmap_y][bitmap_x] = 1

    return True


def get_glyph_components(font,
                         composed_glyph,
                         decomposition,
                         bitmap):
    if not isinstance(bitmap, np.ndarray):
        bitmap = np.zeros(composed_glyph.bitmap.shape, np.uint8)

    if len(decomposition) == 0:
        if (composed_glyph.bitmap == bitmap).all():
            return []

        return 'mismatch'

    component_codepoint = decomposition[0]

    for stage in range(2):
        if stage == 0:
            if component_codepoint not in font.codepoints:
                continue

        else:
            if component_codepoint not in combining_infos:
                break

            _, _, modifier_codepoint = combining_infos[component_codepoint]

            if modifier_codepoint == composed_glyph.codepoint:
                return 'uncomposable'

            if modifier_codepoint not in font.codepoints:
                return 'missing'

            component_codepoint = modifier_codepoint

        component_name = font.codepoints[component_codepoint]
        component_glyph = font.glyphs[component_name]

        delta_size = subtract_offset(
            composed_glyph.bitmap.shape, component_glyph.bitmap.shape)

        for offset_y in range(delta_size[0] + 1):
            for offset_x in range(delta_size[1] + 1):
                offset = (offset_y, offset_x)
                bitmap_copy = bitmap.copy()

                if not paint_glyph(composed_glyph.bitmap,
                                   component_glyph.bitmap,
                                   offset,
                                   bitmap_copy):
                    continue

                glyph_components = get_glyph_components(font,
                                                        composed_glyph,
                                                        decomposition[1:],
                                                        bitmap_copy)

                if glyph_components in ['missing', 'uncomposable']:
                    return glyph_components

                elif isinstance(glyph_components, list):
                    glyph_component = Object()
                    glyph_component.name = component_name
                    glyph_component.offset = add_offset(
                        composed_glyph.offset, offset)
                    glyph_components.append(glyph_component)

                    return glyph_components

    if component_codepoint not in font.codepoints:
        return 'missing'

    else:
        return 'mismatch'


def decompose_glyph(font, composed_name):
    composed_glyph = font.glyphs[composed_name]
    composed_codepoint = composed_glyph.codepoint

    # Calculate decomposition
    if composed_codepoint in custom_decomposition:
        decomposition_string = custom_decomposition[composed_codepoint]
    elif composed_codepoint >= 0:
        decomposition_string = unicodedata.decomposition(
            chr(composed_codepoint))
    else:
        decomposition_string = ''

    if decomposition_string.startswith('<compat> '):
        decomposition_string = decomposition_string[9:]
    if decomposition_string == '' or decomposition_string.startswith('<'):
        return []
    decomposition = [int(x, 16) for x in decomposition_string.split()]

    decomposition = [x for x in decomposition if x != 0x20]

    # Get components
    components = get_glyph_components(font,
                                      composed_glyph,
                                      decomposition,
                                      None)

    if components == 'missing':
        log_info(f'{get_unicode_string(composed_codepoint)}'
                 ' could be composed from ['
                 f'{get_decomposition_string(decomposition)}]')

        return []

    elif components == 'mismatch':
        log_warning(f'{get_unicode_string(composed_codepoint)}'
                    ' cannot be composed from ['
                    f'{get_decomposition_string(decomposition)}]'
                    ', storing precomposed glyph')

        return []

    elif components == 'uncomposable':
        return []

    else:
        log_info(f'{get_unicode_string(composed_codepoint)}'
                 ' composed with [' +
                 f'{get_decomposition_string(decomposition)}]')

        return components


def get_random_offset(font):
    while True:
        value = random.gauss(0, font.location['EJIT'])

        if math.fabs(value) < 1:
            break

    return value * font.units_per_element_y


def add_ufo_bitmap(ufo_glyph,
                   font,
                   glyph):
    units_per_element_x = get_units_per_element_x(font)

    strike_num = font.strike_num

    for y in range(glyph.bitmap.shape[0]):
        for x in range(glyph.bitmap.shape[1]):
            for z in range(strike_num):
                if glyph.bitmap[y][x]:
                    ufo_y = (glyph.offset[0] + y + 0.5 - 0.5 * z) * \
                        font.units_per_element_y + \
                        get_random_offset(font)
                    ufo_x = (font.glyph_offset_x +
                             glyph.offset[1] + x + 0.5) * \
                        units_per_element_x + get_random_offset(font)

                    ufo_component = ufoLib2.objects.Component('_')
                    ufo_component.transformation = [
                        1, 0, 0, 1,
                        math.floor(ufo_x),
                        math.floor(ufo_y)]

                    ufo_glyph.components.append(ufo_component)


def add_ufo_components(glyph,
                       font,
                       components):
    units_per_element_x = get_units_per_element_x(font)

    for component in components:
        ufo_component = ufoLib2.objects.Component(component.name)

        delta = subtract_offset(component.offset,
                                font.glyphs[component.name].offset)

        if delta != (0, 0):
            ufo_component.transformation = [
                1, 0, 0, 1,
                math.floor(delta[1] * units_per_element_x),
                math.floor(delta[0] * font.units_per_element_y)]

        glyph.components.append(ufo_component)


def add_anchors(anchors,
                font,
                composed_codepoint,
                components):
    if composed_codepoint in custom_anchors:
        return

    if len(components) != 2:
        return

    # Get base and combining glyphs
    base_name = None
    combining_name = None

    for component in components:
        component_name = component.name
        component_glyph = font.glyphs[component_name]
        component_codepoint = component_glyph.codepoint

        if component_codepoint in combining_infos:
            combining_name = component_name
            combining_size = component_glyph.bitmap.shape
            combining_glyph_offset = component_glyph.offset
            combining_offset = component.offset

            combining_info = combining_infos[component_codepoint]
            anchor_name = combining_info[1]

        else:
            base_name = component_name
            base_glyph_offset = component_glyph.offset
            base_offset = component.offset

    if base_name == None or combining_name == None:
        return

    # Process combining component
    if combining_name not in anchors:
        anchors[combining_name] = {}

    combining_anchors = anchors[combining_name]
    if anchor_name not in combining_anchors:
        if anchor_name not in ['bottom', 'cedilla', 'ogonek']:
            combining_anchor_offset = (0,
                                       int(combining_size[1] / 2))
        else:
            combining_anchor_offset = (combining_size[0],
                                       int(combining_size[1] / 2))

        combining_anchors[anchor_name] = add_offset(combining_glyph_offset,
                                                    combining_anchor_offset)

    else:
        combining_anchor_offset = subtract_offset(combining_anchors[anchor_name],
                                                  combining_glyph_offset)

    anchor_offset = add_offset(combining_offset,
                               combining_anchor_offset)

    # Process base component
    base_name = base_name

    if base_name not in anchors:
        anchors[base_name] = {}

    anchor_offset = add_offset(
        subtract_offset(anchor_offset,
                        base_offset),
        base_glyph_offset)

    base_anchors = anchors[base_name]
    if anchor_name not in base_anchors:
        base_anchors[anchor_name] = anchor_offset
    else:
        if base_anchors[anchor_name] != anchor_offset:
            log_warning(
                f'{get_unicode_string(composed_codepoint)} anchor "{
                    anchor_name}"'
                ' does not align with anchors from components [' +
                ', '.join([component.name for component in components]) + ']'
            )


def set_ufo_anchors(ufo_font, font, anchors):
    units_per_element_x = get_units_per_element_x(font)

    # UFO anchors, base and mark lists
    mark_map = {}
    base_map = {}

    for component_name in anchors:
        component_codepoint = font.glyphs[component_name].codepoint

        component_anchors = anchors[component_name]
        ufo_glyph = ufo_font[component_name]

        for anchor_name in component_anchors:
            anchor_offset = component_anchors[anchor_name]

            anchor = ufoLib2.objects.Anchor(
                math.floor(
                    (anchor_offset[1] + font.glyph_offset_x) * units_per_element_x),
                math.floor(
                    anchor_offset[0] * font.units_per_element_y),
                anchor_name)

            ufo_glyph.appendAnchor(anchor)

            if component_codepoint in combining_infos:
                anchor_name_offset = (anchor_name, anchor_offset)

                if anchor_name_offset not in mark_map:
                    mark_map[anchor_name_offset] = []

                mark_map[anchor_name_offset].append(component_name)

        if component_codepoint not in combining_infos:
            anchor_names_offsets = tuple(
                [(anchor_name, anchor_offset)
                 for anchor_name, anchor_offset
                 in component_anchors.items()])

            if anchor_names_offsets not in base_map:
                base_map[anchor_names_offsets] = []

            base_map[anchor_names_offsets].append(component_name)

    # OpenType features
    features = fontTools.feaLib.builder.FeatureFile()

    # Language systems
    features.statements.append(
        fontTools.feaLib.ast.LanguageSystemStatement('DFLT', 'dflt'))
    if 0x41 in font.codepoints:
        features.statements.append(
            fontTools.feaLib.ast.LanguageSystemStatement('latn', 'dflt'))
    if 0x391 in font.codepoints:
        features.statements.append(
            fontTools.feaLib.ast.LanguageSystemStatement('grek', 'dflt'))
    if 0x410 in font.codepoints:
        features.statements.append(
            fontTools.feaLib.ast.LanguageSystemStatement('cyrl', 'dflt'))

    # Mark definitions
    allmarks = fontTools.feaLib.ast.GlyphClass()
    topmarks = fontTools.feaLib.ast.GlyphClass()

    for codepoint in combining_infos:
        if codepoint in font.codepoints:
            allmarks.append(font.codepoints[codepoint])

            if combining_infos[codepoint][1] in ['top', 'top.shifted']:
                topmarks.append(font.codepoints[codepoint])

    allmarks_definition = fontTools.feaLib.ast.GlyphClassDefinition(
        'allmarks', allmarks)
    features.statements.append(allmarks_definition)

    topmarks_definition = fontTools.feaLib.ast.GlyphClassDefinition(
        'topmarks', topmarks)
    features.statements.append(topmarks_definition)

    # Mark feature
    if len(mark_map) > 0 and len(base_map) > 0:
        mark_lookup = fontTools.feaLib.ast.LookupBlock('marklookup')

        for anchor_name_offset in mark_map:
            anchor_name, anchor_offset = anchor_name_offset
            component_names = mark_map[anchor_name_offset]

            glyphs = fontTools.feaLib.ast.GlyphClass()
            for component_name in component_names:
                glyphs.append(fontTools.feaLib.ast.GlyphName(component_name))

            mark_class = fontTools.feaLib.ast.MarkClassDefinition(
                fontTools.feaLib.ast.MarkClass(anchor_name),
                fontTools.feaLib.ast.Anchor(
                    int(anchor_offset[1] * units_per_element_x),
                    int(anchor_offset[0] * font.units_per_element_y)),
                glyphs
            )
            mark_lookup.statements.append(mark_class)

        for anchor_name_offsets, component_names in base_map.items():
            glyphs = fontTools.feaLib.ast.GlyphClass()
            for component_name in component_names:
                glyphs.append(fontTools.feaLib.ast.GlyphName(component_name))

            marks = []
            for anchor_name_offset in anchor_name_offsets:
                anchor_name, anchor_offset = anchor_name_offset
                marks.append((
                    fontTools.feaLib.ast.Anchor(
                        int(anchor_offset[1] * units_per_element_x),
                        int(anchor_offset[0] * font.units_per_element_y)),
                    fontTools.feaLib.ast.MarkClass(anchor_name)
                ))

            base_class = fontTools.feaLib.ast.MarkBasePosStatement(
                glyphs,
                marks)
            mark_lookup.statements.append(base_class)

        features.statements.append(mark_lookup)

        mark_block = fontTools.feaLib.ast.FeatureBlock('mark')
        mark_block.statements.append(
            fontTools.feaLib.ast.LookupReferenceStatement(mark_lookup))

        features.statements.append(mark_block)

    # GDEF table
    allmarks_name = fontTools.feaLib.ast.GlyphClassName(allmarks_definition)

    gdef_table = fontTools.feaLib.ast.TableBlock('GDEF')
    gdef_table.statements.append(
        fontTools.feaLib.ast.GlyphClassDefStatement(
            None, allmarks_name, None,  None))

    features.statements.append(gdef_table)

    # Assign to UFO font
    ufo_font.features.text = features.asFea()


def add_ufo_glyphs(ufo_font, font):
    units_per_element_x = get_units_per_element_x(font)

    add_element_glyph(ufo_font, font)

    anchors = {}

    for composed_name in font.glyphs:
        composed_glyph = font.glyphs[composed_name]

        ufo_glyph = ufo_font.newGlyph(composed_name)
        if composed_glyph.codepoint != 0:
            ufo_glyph.unicode = composed_glyph.codepoint
        ufo_glyph.width = int(composed_glyph.advance * units_per_element_x)

        components = decompose_glyph(font, composed_name)

        if len(components) == 0:
            add_ufo_bitmap(ufo_glyph, font, composed_glyph)

        else:
            add_ufo_components(ufo_glyph, font, components)

            add_anchors(anchors, font,
                        composed_glyph.codepoint, components)

    set_ufo_anchors(ufo_font, font, anchors)


def get_default_location(font):
    default_location = {}

    for axis in font.variable_axes:
        default_location[axis] = axes_info[axis]['default']

    # if len(font.variable_instances) == 0:
    #     for axis in font.variable_axes:
    #         default_location[axis] = axes_info[axis]['default']

    # else:
    #     first_instance = font.variable_instances[0]

    #     for axis in first_instance:
    #         default_location[axis] = first_instance[axis]

    return default_location


def get_masters(font):
    masters = []
    locations = []

    axes_num = len(font.variable_axes)

    if axes_num >= 1:
        for master_index in range(2 ** axes_num):
            master = Object()
            master.name = ''
            master.location = {}

            for axis_index in range(axes_num):
                axis = font.variable_axes[axis_index]

                if not master_index & (1 << axis_index):
                    master.name = combine_strings(master.name, axis + 'min')
                    master.location[axis] = axes_info[axis]['min']
                else:
                    master.name = combine_strings(master.name, axis + 'max')
                    master.location[axis] = axes_info[axis]['max']

            master.name = combine_strings(master.name, font.style_name)

            masters.append(master)
            locations.append(master.location)

    else:
        master = Object()
        master.name = font.style_name
        master.location = {}

        masters.append(master)
        locations.append(master.location)

    # default_location = get_default_location(font)
    # if default_location not in locations:
    #     master.name = 'Default'
    #     master.location = default_location

    return masters


def write_designspace(path, font):
    font_file_name = get_file_name(font.family_name, font.style_name)

    designspace_filename = font_file_name + '.designspace'

    doc = fontTools.designspaceLib.DesignSpaceDocument()

    default_location = get_default_location(font)
    for axis in font.variable_axes:
        doc.addAxisDescriptor(
            tag=axis,
            name=axes_info[axis]['name'],
            minimum=int(100 * axes_info[axis]['min']),
            maximum=int(100 * axes_info[axis]['max']),
            default=int(100 * default_location[axis])
        )

    for master in get_masters(font):
        master_file_name = get_file_name(font.family_name, master.name)

        location = {}
        for axis in master.location:
            axis_name = axes_info[axis]['name']

            location[axis_name] = int(100 * master.location[axis])

        doc.addSourceDescriptor(
            filename=master_file_name + '.ufo',
            name=master_file_name,
            familyName=font.family_name,
            location=location)

    for instance in font.variable_instances:
        instance_style_name = combine_strings(instance.name, font.style_name)
        instance_file_name = get_file_name(
            font.family_name, instance_style_name)

        location = {}
        for axis in instance.location:
            axis_name = axes_info[axis]['name']

            location[axis_name] = int(100 * instance.location[axis])

        style_map_family_name, style_map_style_name = get_style_map_names(
            font.family_name, instance_style_name)

        doc.addInstanceDescriptor(
            filename=instance_file_name + '.ufo',
            name=instance_file_name,
            familyName=font.family_name,
            styleName=instance_style_name,
            styleMapFamilyName=style_map_family_name,
            styleMapStyleName=style_map_style_name,
            location=location
        )

    doc.write(path + '/' + designspace_filename)

    # config.yaml
    config = open(path + '/' + font_file_name + '-config.yaml', 'wt')
    config.write('sources:\n')
    config.write('  - ' + designspace_filename + '\n')
    if len(font.variable_axes) > 0:
        config.write('axisOrder:\n')
        for axis in font.variable_axes:
            config.write(f'  - {axis}\n')
        config.close()


def main():
    global log_level

    parser = argparse.ArgumentParser(
        prog='bdf2ufo',
        description='Converts .bdf pixel fonts to .ufo static and variable vector fonts.')
    parser.add_argument('-V', '--version',
                        action='version',
                        version=f'bdf2ufo {bdf2ufo_version}')
    parser.add_argument('-v', '--verbose',
                        action='store_true',
                        help='verbose mode')

    parser.add_argument('--family-name',
                        help='overrides the font family name string')
    parser.add_argument('--style-name',
                        help='overrides the font style name string (e.g. "Condensed Bold Italic")')
    parser.add_argument('--font-version',
                        help='overrides the font version string')

    parser.add_argument('--copyright',
                        help='overrides the font copyright string')
    parser.add_argument('--designer',
                        help='overrides the font designer string')
    parser.add_argument('--designer-url',
                        help='overrides the font designer URL string')
    parser.add_argument('--manufacturer',
                        help='overrides the font manufacturer string')
    parser.add_argument('--manufacturer-url',
                        help='overrides the font manufacturer URL string')
    parser.add_argument('--license',
                        help='overrides the font license string')
    parser.add_argument('--license-url',
                        help='overrides the font license URL string')

    parser.add_argument('--ascent',
                        type=int,
                        help='overrides the font ascent in pixels (baseline to top of line)')
    parser.add_argument('--descent',
                        type=int,
                        help='overrides the font descent in pixels (baseline to bottom of line)')
    parser.add_argument('--cap-height',
                        type=int,
                        help='overrides the font cap height in pixels (typically of uppercase A)')
    parser.add_argument('--x-height',
                        type=int,
                        help='overrides the font x height in pixels (typically of lowercase x)')

    parser.add_argument('--underline-position',
                        type=float,
                        help='sets the font underline position in pixels (top, relative to the baseline)')
    parser.add_argument('--underline-thickness',
                        type=float,
                        help='sets the font underline thickness in pixels')
    parser.add_argument('--strikeout-position',
                        type=float,
                        help='sets the font strikeout position in pixels (top, relative to the baseline)')
    parser.add_argument('--strikeout-thickness',
                        type=float,
                        help='sets the font strikeout thickness in pixels')

    parser.add_argument('--superscript-scale-x',
                        type=float,
                        help='sets the font superscript x scale')
    parser.add_argument('--superscript-scale-y',
                        type=float,
                        help='sets the font superscript y scale')
    parser.add_argument('--superscript-offset-x',
                        type=float,
                        help='sets the font superscript x offset in pixels')
    parser.add_argument('--superscript-offset-y',
                        type=float,
                        help='sets the font superscript y offset in pixels')
    parser.add_argument('--subscript-scale-x',
                        type=float,
                        help='sets the font subscript x scale')
    parser.add_argument('--subscript-scale-y',
                        type=float,
                        help='sets the font subscript y scale')
    parser.add_argument('--subscript-offset-x',
                        type=float,
                        help='sets the font subscript x offset in pixels')
    parser.add_argument('--subscript-offset-y',
                        type=float,
                        help='sets the font subscript y offset in pixels')

    parser.add_argument('--codepoint-subset',
                        default='',
                        help='specifies a comma-separated subset of Unicode characters to convert (e.g. 0x0-0x2000,0x20ee)')
    parser.add_argument('--notdef-codepoint',
                        type=auto_int,
                        help='specifies the codepoint for the .notdef character')
    parser.add_argument('--glyph-scale-x',
                        type=float,
                        default=1,
                        help='sets the glyph x scale')
    parser.add_argument('--glyph-scale-y',
                        type=float,
                        default=1,
                        help='sets the glyph y scale')
    parser.add_argument('--glyph-offset-x',
                        type=float,
                        default=0,
                        help='sets the glyph x offset in pixels')
    parser.add_argument('--glyph-offset-y',
                        type=float,
                        default=0,
                        help='sets the glyph y offset in pixels')
    parser.add_argument('--random-seed',
                        type=int,
                        default=0,
                        help='sets the random seed for the EJIT axis (see below)')
    parser.add_argument('--units-per-em',
                        type=int,
                        default=2048,
                        help='sets the units per em value')
    parser.add_argument('--double-strike',
                        action='store_true',
                        help='adds a double strike at the vertical half pixel')
    parser.add_argument('--axes-limits',
                        help='overrides the axes limits: [[axis=]] (e.g. "XESP=0.25-1.2")')

    parser.add_argument('--variable-axes',
                        help='builds a variable font with specified axes (ESIZ: element size, ROND: roundness, BLED: bleed, XESP: horizontal element spacing, EJIT: element jitter): [axis][,...]')
    parser.add_argument('--variable-instance',
                        action='append',
                        help='builds a variable font instance with specified style name and location: [style-name][,[axis]=[value]][,...]')
    parser.add_argument('--static-axes',
                        help='sets the static axes: [[axis]=[value]][,...]')

    parser.add_argument('input',
                        help='the .bdf file to be converted')
    parser.add_argument('output',
                        help='the masters folder with the built .ufo files')

    config = parser.parse_args()

    if config.verbose:
        log_level = 0
    if config.axes_limits is not None:
        for axis_limits in config.axes_limits.split(','):
            axis, limits = axis_limits.split('=', 2)
            min, max = limits.split('-', 2)
            axes_info[axis]['min'] = float(min)
            axes_info[axis]['max'] = float(max)
            axes_info[axis]['default'] = float(max)
    if config.variable_instance is None:
        config.variable_instance = []
    elif config.variable_axes is None:
        log_error(
            'can\'t create variable font instances without variable font axes')

    print('Loading BDF font...')
    font = load_font(config)

    print('Preparing masters folder...')
    os.makedirs(config.output, exist_ok=True)

    for master in get_masters(font):
        random.seed(config.random_seed)

        ufo_file_name = get_file_name(font.family_name, master.name) + '.ufo'

        for axis in master.location:
            font.location[axis] = master.location[axis]

        print(f'Building {ufo_file_name}...')

        ufo_font = ufoLib2.Font()
        set_ufo_info(ufo_font, font)

        add_ufo_glyphs(ufo_font, font)

        output_path = config.output + '/' + ufo_file_name

        if os.path.exists(output_path):
            shutil.rmtree(output_path)
        ufo_font.write(fontTools.ufoLib.UFOWriter(output_path))

    file_name = get_file_name(font.family_name, font.style_name)

    print(f'Building {file_name}.designspace and {file_name}-config.yaml...')
    write_designspace(config.output, font)

    print('Done.')


if __name__ == '__main__':
    main()
