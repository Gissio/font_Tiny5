# Procedural specimen images for Tiny5.
#
# Every image is an artifact of a fictional 1980s pocket-electronics maker:
# the screens are simulated period displays, drawn entirely in code so the
# font pixels stay crisp and the images can be rendered at any target size.
#
# All text is composed on a low-resolution cell grid (1 image = one display),
# then upscaled with NEAREST so every font pixel maps to whole display cells.
#
# The file runs from the general to the particular: the font, the cell grid,
# the shared image helpers, then one section per device — its constants, its
# renderer and the specimen it builds — in the order the images are numbered.

import math
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


# --- The font ---------------------------------------------------------------

ROOT_PATH = Path(__file__).resolve().parent.parent
OUT_PATH = Path(__file__).resolve().parent

TINY5_PATH = ROOT_PATH / "fonts/variable/Tiny5[BLED,JITT,ROND,wdth,wght].ttf"
TINY5_DUO_PATH = ROOT_PATH / "fonts/variable/Tiny5Duo[BLED,JITT,ROND,wdth,wght].ttf"
TINY5_ITALIC_PATH = ROOT_PATH / "fonts/variable/Tiny5-Italic[BLED,JITT,ROND,wdth,wght].ttf"

# Font version, as the devices display it; keep in sync with the font's
# version (name ID 5)
VERSION = "V2.003"

# Tiny5 draws one font pixel per 8 font units, and is 5 font pixels tall
FONT_PIXEL_SIZE = 8
CAP_PIXELS = 5

# Variation axes: weight, width, roundness, bleed, jitter.
# Full weight, so every font pixel fills its display cells exactly; the
# LCD segmentation comes from the rendered cell pattern, not the font.
LCD_AXES = [400, 100, 0, 0, 0]


def get_font(scale, duo=False, axes=None, italic=False):
    """Load Tiny5 sized so one font pixel covers `scale` display cells,
    optionally as the italic variant or at other axis settings."""
    path = TINY5_ITALIC_PATH if italic else (TINY5_DUO_PATH if duo else TINY5_PATH)
    font = ImageFont.truetype(font=str(path), size=FONT_PIXEL_SIZE * scale)
    font.set_variation_by_axes(axes or LCD_AXES)

    return font


def get_baseline(line_height, cap_height):
    """Return the baseline offset that centers capital letters within a line."""
    return (line_height - cap_height) // 2 + cap_height


# --- The cell grid ----------------------------------------------------------

# Text at 2+ cells per font pixel rasterizes cleanly at cell resolution, but
# at 1 cell per font pixel the tiny ppem garbles the glyphs. Native-size text
# is therefore drawn on a separate layer at FINE times the cell resolution
# (where rendering is proven crisp) and reduced to cells afterwards.
FINE = 4


class Display:
    """A monochrome dot-matrix display, composed in cell coordinates."""

    def __init__(self, size):
        self.size = size
        self.mask = Image.new("L", size, 0)
        self.draw = ImageDraw.Draw(self.mask)
        self.fine = Image.new("L", (size[0] * FINE, size[1] * FINE), 0)
        self.fine_draw = ImageDraw.Draw(self.fine)

    def cells(self):
        """Return the finished cell mask: on/off per display cell.

        The fine layer is point-sampled rather than averaged: sampling hits
        the interior of each font-pixel square, so edge antialiasing cannot
        double or erode pixels the way block averaging does.
        """
        reduced = self.fine.resize(self.size, Image.NEAREST)
        mask = ImageChops.lighter(self.mask, reduced)

        return mask.point(lambda v: 255 if v >= 128 else 0)

    def image_size(self, cell):
        """Return the rendered size, at `cell` image pixels per display cell."""
        return (self.size[0] * cell, self.size[1] * cell)

    def lit(self, cell):
        """Return the lit-cell mask, at `cell` image pixels per display cell."""
        return self.cells().resize(self.image_size(cell), Image.NEAREST)

    def pen(self, scale, duo):
        """Return the layer to write text at `scale` cells per font pixel on:
        the cell mask itself, or the fine layer at native size, along with the
        font and the units that layer draws per cell."""
        if scale >= 2:
            return self.draw, get_font(scale, duo), 1

        return self.fine_draw, get_font(scale * FINE, duo), FINE

    def text(self, xy, scale, string, anchor="ls", duo=False):
        """Draw text with the baseline (or anchor) at cell position xy.

        Center and right anchors are resolved against the inked width, and
        quantized to whole cells: native-size text must keep a constant
        pixel phase, and the font sets its glyph squares flush with the pen,
        one square per cell.
        """
        draw, font, unit = self.pen(scale, duo)
        x = xy[0] * unit
        if anchor[0] in "mr":
            width = self.text_width(scale, string, duo)
            x -= round(width / 2 if anchor[0] == "m" else width) * unit
        draw.text(xy=(x, xy[1] * unit), text=string, fill=255,
                  font=font, anchor="l" + anchor[1])

    def text_width(self, scale, string, duo=False):
        """Return the inked width of the string, in cells.

        Every glyph keeps its rightmost pixel column empty, as the gap to the
        next one, so a string inks one font pixel short of its advance. That
        trailing gap is spacing, not text: counted in, it would push centered
        text off center and hold right-aligned text a pixel shy of its
        margin, so it is taken off every measurement.
        """
        draw, font, unit = self.pen(scale, duo)

        return draw.textlength(string, font=font) / unit - scale

    def char_row(self, left, baseline, pitch, scale, chars, duo=False):
        """Draw characters on a fixed pitch, centered in each column."""
        for column, char in enumerate(chars):
            x = left + column * pitch + pitch // 2
            self.text((x, baseline), scale, char, anchor="ms", duo=duo)


# --- Image helpers ----------------------------------------------------------

CANVAS = (1920, 1080)

JPG_QUALITY = 95

# Every random imperfection is drawn from this seed, so the specimens are
# reproducible
NOISE_SEED = 5

# Lighting fields are evaluated on a small grid and smoothly scaled up
FIELD_SIZE = (64, 36)


def noise_image(size, rng):
    """Build an image of uniform random noise."""
    return Image.frombytes("L", size, rng.randbytes(size[0] * size[1]))


def grain_field(size, rng, depth):
    """Build a fine multiplicative grain field, `depth` levels deep: the
    texture of a phosphor coating or of paper fibers."""
    return noise_image(size, rng).point(lambda v: 255 - depth + v * depth // 255)


def light_field(size, level):
    """Build a smooth full-size lighting field from a function giving the
    level at each point of the field, in normalized coordinates."""
    small = Image.new("L", FIELD_SIZE)
    small.putdata([level(x / (FIELD_SIZE[0] - 1), y / (FIELD_SIZE[1] - 1))
                   for y in range(FIELD_SIZE[1]) for x in range(FIELD_SIZE[0])])

    return small.resize(size, Image.BICUBIC)


def sheen(size, strength=10):
    """Build a soft diagonal highlight, light catching the polarizer film."""
    return light_field(size, lambda u, v: round(
        strength * math.exp(-(u + v - 0.55) ** 2 / 0.065)))


def radial_light(size, center_level, edge_level):
    """Build a smooth radial lighting field, brightest in the center."""
    def level(u, v):
        du, dv = u - 0.5, v - 0.5
        d = min(1.0, (du * du * 4 + dv * dv * 4) ** 0.5)

        return round(center_level + (edge_level - center_level) * d ** 1.5)

    return light_field(size, level)


def edge_shadow(size, level=205):
    """Build an inner-shadow field: the bezel shading the recessed screen."""
    small = Image.new("L", FIELD_SIZE, 255)
    ImageDraw.Draw(small).rectangle(
        xy=[(0, 0), (FIELD_SIZE[0] - 1, FIELD_SIZE[1] - 1)], outline=level, width=2)
    small = small.filter(ImageFilter.GaussianBlur(1.2))

    return small.resize(size, Image.BICUBIC)


def cell_pattern(size, cell):
    """Build a full-size mask that is on inside each display cell, the gap
    between cells scaled to the cell size."""
    width, height = size
    gap = max(1, round(cell / 8))
    row_on = bytes(255 if x % cell < cell - gap else 0 for x in range(width))
    row_off = bytes(width)
    rows = b"".join(row_on if y % cell < cell - gap else row_off
                    for y in range(height))

    return Image.frombytes("L", size, rows)


def colorize(mask_img, color):
    """Build an image that fades from black to the color over the mask."""
    return Image.composite(Image.new("RGB", mask_img.size, color),
                           Image.new("RGB", mask_img.size, (0, 0, 0)),
                           mask_img)


def shade(img, field):
    """Darken an image by a grayscale field: falling light, a shadow, a grid."""
    return ImageChops.multiply(img, field.convert("RGB"))


def save_image(img, filename):
    img.save(OUT_PATH / filename, optimize=True, quality=JPG_QUALITY)


# --- Reflective LCD: the hero -----------------------------------------------

# The classic 84x48 phone LCD, in its green backlit scheme
NOKIA_GRID = (84, 48)
NOKIA_CELL = 22
NOKIA_BG = (177, 186, 158)
NOKIA_FG = (30, 39, 29)


def render_reflective(display, cell, bg_color, fg_color, canvas_size=None):
    """Render as a reflective LCD: pixels floating over a pale ground.

    The unlit cells show faintly (the classic LCD ghost grid), and the lit
    pixels cast a soft shadow onto the reflector behind the liquid crystal.
    If a larger canvas size is given, the display is centered on it, with
    the surround darkened like the glass edge of the module.
    """
    full = display.image_size(cell)
    pattern = cell_pattern(full, cell)
    lit = ImageChops.multiply(display.lit(cell), pattern)

    # Ambient light only, as with the backlight off: nearly even, with a
    # gentle falloff towards the corners
    img = Image.new("RGB", full, bg_color)
    img = shade(img, radial_light(full, 252, 230))

    # Ghost grid: every cell of the display is faintly visible
    img = shade(img, pattern.point(lambda v: 246 if v else 255))

    # Drop shadow of the lit pixels on the reflector
    shadow = lit.filter(ImageFilter.GaussianBlur(cell * 0.6))
    shadow = ImageChops.offset(shadow, cell // 2, cell * 2 // 3)
    img = shade(img, shadow.point(lambda v: 255 - v * 60 // 255))

    img.paste(Image.new("RGB", full, fg_color), (0, 0), lit)

    # The screen sits recessed in the bezel, which shades its edges; light
    # catches the polarizer film in a soft diagonal sheen
    img = shade(img, edge_shadow(full))
    img = ImageChops.add(img, sheen(full).convert("RGB"))

    if canvas_size is not None and canvas_size != full:
        # A hairline marks where the glass meets the surround
        ImageDraw.Draw(img).rectangle(xy=[(0, 0), (full[0] - 1, full[1] - 1)],
                                      outline=tuple(c * 2 // 5 for c in bg_color),
                                      width=3)
        surround = tuple(c * 5 // 9 for c in bg_color)
        canvas = Image.new("RGB", canvas_size, surround)
        canvas.paste(img, ((canvas_size[0] - full[0]) // 2,
                           (canvas_size[1] - full[1]) // 2))
        img = canvas

    return img


def build_hero():
    """The hero is the home screen of an 84x48-pixel phone: signal and
    battery indicators, title and subtitle, and the softkey label."""
    d = Display(NOKIA_GRID)
    width, height = NOKIA_GRID
    center = width // 2

    # Nokia-style indicators: signal column down the left edge, battery
    # column down the right edge, each capped by its icon
    d.draw.rectangle(xy=[(1, 3), (3, 4)], fill=255)         # antenna head
    d.draw.rectangle(xy=[(2, 5), (2, 7)], fill=255)         # antenna mast
    d.draw.rectangle(xy=[(width - 3, 1), (width - 3, 1)], fill=255)     # battery tip
    d.draw.rectangle(xy=[(width - 4, 2), (width - 2, 7)], outline=255)  # battery body
    for i in range(4):
        y = 9 + i * 8
        d.draw.rectangle(xy=[(1, y), (3, y + 6)], fill=255)
        d.draw.rectangle(xy=[(width - 4, y), (width - 2, y + 6)], fill=255)

    # Keyguard lock in the top left, clock in the top right
    d.draw.rectangle(xy=[(8, 1), (10, 1)], fill=255)        # shackle top
    d.draw.rectangle(xy=[(7, 2), (7, 3)], fill=255)         # shackle legs
    d.draw.rectangle(xy=[(11, 2), (11, 3)], fill=255)
    d.draw.rectangle(xy=[(6, 4), (12, 7)], fill=255)        # lock body
    d.draw.rectangle(xy=[(9, 5), (9, 6)], fill=0)           # keyhole
    d.text((width - 6, 7), 1, "5:55", anchor="rs")

    # Title with its subtitle, and the softkey label
    d.text((center, 25), 3, "Tiny5", anchor="ms")
    d.text((center, 36), 1, "Every pixel counts", anchor="ms")
    d.text((center, height - 1), 1, "Menu", anchor="ms", duo=True)

    img = render_reflective(d, NOKIA_CELL, NOKIA_BG, NOKIA_FG, CANVAS)
    save_image(img, "tiny5-presentation.jpg")


# --- Vacuum fluorescent display: the character ROM --------------------------

# The glow of a HiFi deck's front panel: ZnO:Zn phosphor emitting bluish
# green at ~505 nm behind tinted glass, its anode segments seen through the
# fine mesh of the control grid
VFD_GRID = (128, 72)
VFD_CELL = 15
VFD_BG = (7, 15, 15)
VFD_FG = (185, 255, 228)
VFD_GLOW = (26, 158, 128)
VFD_MESH_PITCH = 5
VFD_MESH_LEVEL = 202            # transmission of a mesh wire, of 255

CHARSET_ROWS = [
    "ABCDEFGHIJKLM",
    "NOPQRSTUVWXYZ",
    "abcdefghijklm",
    "nopqrstuvwxyz",
    "0123456789%&@",
    "!?#*+-=/().,:",
]


def mesh_pattern(size, pitch, level):
    """Build the transmission mask of the control grid: a fine wire mesh
    that shades every `pitch`th row and column."""
    width, height = size
    row_wire = bytes([level] * width)
    row_open = bytes(level if x % pitch == 0 else 255 for x in range(width))
    rows = b"".join(row_wire if y % pitch == 0 else row_open
                    for y in range(height))

    return Image.frombytes("L", size, rows)


def render_emissive(display, cell, bg_color, fg_color, glow_color):
    """Render as a VFD: phosphor segments glowing through the control grid
    mesh, haloed behind the tinted front glass."""
    full = display.image_size(cell)
    pattern = cell_pattern(full, cell)

    # The control grid mesh shades the glowing segments
    lit = ImageChops.multiply(display.lit(cell), pattern)
    lit = ImageChops.multiply(lit, mesh_pattern(full, VFD_MESH_PITCH, VFD_MESH_LEVEL))

    img = Image.new("RGB", full, bg_color)
    img = shade(img, radial_light(full, 255, 200))

    # Ghost grid: unpowered segments catch a little ambient light
    ghost = pattern.point(lambda v: 14 if v else 0)
    img = ImageChops.add(img, colorize(ghost, tuple(c // 3 for c in glow_color)))

    # A tight halo around the segments, and a wide haze across the glass
    halo = colorize(lit.filter(ImageFilter.GaussianBlur(cell * 0.6)), glow_color)
    img = ImageChops.screen(img, halo)
    haze = lit.filter(ImageFilter.GaussianBlur(cell * 2.2)).point(lambda v: v * 55 // 100)
    img = ImageChops.screen(img, colorize(haze, glow_color))

    img.paste(Image.new("RGB", full, fg_color), (0, 0), lit)

    return img


def build_charset(duo, filename):
    """A character ROM chart on a HiFi deck's fluorescent display, with the
    glyphs at the native size: one font pixel per display cell."""
    d = Display(VFD_GRID)
    width, height = VFD_GRID
    margin = 3
    pitch = 9

    # Eight lines on one uniform 9-cell baseline rhythm: the header, the six
    # charset rows, and the footer
    d.text((margin, 7), 1, "CHARACTER ROM")
    d.text((width - margin, 7), 1, "Tiny5 Duo" if duo else "Tiny5", anchor="rs")

    left = (width - pitch * len(CHARSET_ROWS[0])) // 2
    for row, chars in enumerate(CHARSET_ROWS):
        d.char_row(left, 16 + row * pitch, pitch, 1, chars, duo=duo)

    d.text((margin, height - 2), 1, "1655 glyphs")
    d.text((width - margin, height - 2), 1, "897 languages", anchor="rs")

    save_image(render_emissive(d, VFD_CELL, VFD_BG, VFD_FG, VFD_GLOW), filename)


# --- Cathode ray tube: the terminal session ---------------------------------

# An amber terminal on a 192x108 raster, with one scanline per font pixel,
# as a terminal drawing a 5x7 character cell does, so the raster is zoomed
# in rather than subdivided
CRT_GRID = (192, 108)
CRT_CELL = 10
CRT_LINE_PITCH = 8              # cells per text line
CRT_BG = (16, 9, 2)
CRT_REFLECTION = (176, 158, 134)
CRT_GRAIN = 17                  # depth of the phosphor grain, of 255

# A P3 amber tube: orange at working brightness, the saturated cores
# washing out towards pale yellow. Channel curves from int10h's
# FFmpeg-CRT-transform amber monitor simulation.
CORE_CURVES = {
    "r": [(0, 0), (0.25, 0.45), (0.8, 1), (1, 1)],
    "g": [(0, 0), (0.25, 0.14), (0.8, 0.55), (1, 0.8)],
    "b": [(0, 0), (0.8, 0), (1, 0.29)],
}
GLOW_CURVES = {
    "r": [(0, 0), (0.3, 0.5), (1, 1)],
    "g": [(0, 0), (0.3, 0.13), (1, 0.5)],
    "b": [(0, 0), (1, 0.08)],
}

# Electron beam: a generalized Gaussian across the scanline, whose width
# grows with beam current, so bright lines bloom wider than dim ones
BEAM_EXPONENT = 3.2             # >2 flattens the core and steepens the falloff
BEAM_SIGMA_MIN = 0.34           # as a fraction of the scanline pitch
BEAM_SIGMA_MAX = 0.46
BEAM_FLOOR = 42                 # emission between scanlines, of 255

TERMINAL_LINES = [
    "login: guest",
    "Last login: Fri Jun 5 05:55 on tty5",
    "",
    "$ setfont tiny5",
    "Font loaded: Tiny5, 5 pixels tall.",
    "$ fc-query --brief tiny5",
    "family: Tiny5 + Tiny5 Duo",
    "axes: weight width slant round bleed jitter",
    "pixel-perfect render: increments of 6 pt (8 px)",
    "",
    "$ echo Every pixel counts",
    "Every pixel counts",
    "$",
]


def curve_lut(points):
    """Build a 256-entry lookup table from piecewise-linear curve points."""
    lut = []
    for value in range(256):
        x = value / 255
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            if x <= x1:
                t = 0 if x1 == x0 else (x - x0) / (x1 - x0)
                lut.append(round((y0 + (y1 - y0) * t) * 255))
                break

    return lut


def phosphor(intensity, curves):
    """Map beam intensity to phosphor emission through the color curves."""
    return Image.merge("RGB", tuple(intensity.point(curve_lut(curves[c]))
                                    for c in "rgb"))


def beam_profile(size, pitch, sigma):
    """Build the vertical emission profile of the scanning beam.

    The beam has a generalized Gaussian cross-section: a flat, saturated
    core with a steep falloff into the gap between scanlines, as a well
    focused electron gun produces.
    """
    column = Image.new("L", (1, size[1]))
    levels = []
    for y in range(size[1]):
        offset = ((y % pitch) + 0.5) / pitch - 0.5
        weight = math.exp(-abs(offset / sigma) ** BEAM_EXPONENT)
        levels.append(round(BEAM_FLOOR + (255 - BEAM_FLOOR) * weight))
    column.putdata(levels)

    return column.resize(size, Image.NEAREST)


def barrel(img, k):
    """Warp the image over the bulge of a CRT tube.

    The center is magnified and the raster bows outward; the corners stay
    put, so nothing samples outside the image.
    """
    width, height = img.size
    columns, rows = 32, 18

    def source(px, py):
        xn = px / width * 2 - 1
        yn = py / height * 2 - 1
        f = (1 + k * (xn * xn + yn * yn)) / (1 + 2 * k)

        return ((xn * f + 1) * width / 2, (yn * f + 1) * height / 2)

    mesh = []
    for j in range(rows):
        for i in range(columns):
            x0, y0 = width * i // columns, height * j // rows
            x1, y1 = width * (i + 1) // columns, height * (j + 1) // rows
            quad = sum((source(px, py)
                        for px, py in [(x0, y0), (x0, y1), (x1, y1), (x1, y0)]), ())
            mesh.append(((x0, y0, x1, y1), quad))

    return img.transform(img.size, Image.MESH, mesh, Image.BILINEAR)


def glass_reflection(size):
    """Build the soft reflection of a bright window across the room."""
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    width, height = size
    draw.rounded_rectangle(xy=[(width * 0.58, height * 0.10),
                               (width * 0.80, height * 0.36)],
                           radius=height // 12, fill=255)
    mask = mask.rotate(6, resample=Image.BILINEAR, center=(width * 0.69, height * 0.23))
    mask = mask.filter(ImageFilter.GaussianBlur(width / 30))

    return mask.point(lambda v: v * 42 // 255)


def render_crt(display, cell, bg_color):
    """Render as a bright monochrome CRT.

    The electron beam sweeps one scanline per raster row, its width growing
    with beam current; where it saturates the phosphor the emission washes
    out to white, haloed by the phosphor's own amber. The tube then curves
    and vignettes the picture, and the glass reflects the room.
    """
    full = display.image_size(cell)
    pitch = cell           # one scanline per font pixel

    # The spot is round, so it smears horizontally as it sweeps
    lit = display.lit(cell).filter(ImageFilter.GaussianBlur((cell * 0.22, cell * 0.05)))

    # Beam current modulates the scanline width: bright lines run wide,
    # dim ones stay narrow
    narrow = ImageChops.multiply(lit, beam_profile(full, pitch, BEAM_SIGMA_MIN))
    wide = ImageChops.multiply(lit, beam_profile(full, pitch, BEAM_SIGMA_MAX))
    beam = Image.composite(wide, narrow, lit)

    img = Image.new("RGB", full, bg_color)

    # Phosphor emission adds light: the saturated cores, the halation
    # around them, and the wide haze scattered inside the glass
    img = ImageChops.screen(img, phosphor(beam, CORE_CURVES))
    halo = beam.filter(ImageFilter.GaussianBlur(cell * 1.1)).point(lambda v: v * 72 // 100)
    img = ImageChops.screen(img, phosphor(halo, GLOW_CURVES))
    haze = beam.filter(ImageFilter.GaussianBlur(cell * 3.2)).point(lambda v: v * 30 // 100)
    img = ImageChops.screen(img, phosphor(haze, GLOW_CURVES))

    # The phosphor coating is granular
    img = shade(img, grain_field(full, random.Random(NOISE_SEED), CRT_GRAIN))

    # The tube curves the picture, the glass vignettes it, and a window
    # across the room reflects faintly off the screen
    img = barrel(img, 0.035)
    img = shade(img, radial_light(full, 255, 196))
    img = ImageChops.screen(img, colorize(glass_reflection(full).point(lambda v: v * 2 // 3),
                                          CRT_REFLECTION))

    return img


def build_terminal():
    """A session on an amber terminal, listing the font's specs, with the
    capitals of each line centered within the line pitch."""
    d = Display(CRT_GRID)
    width, height = CRT_GRID
    pitch = CRT_LINE_PITCH

    # Monitors overscan: the active text sits well inside the tube, with a
    # wide dark margin all around it
    block_width = max(d.text_width(1, line) for line in TERMINAL_LINES)
    block_height = pitch * len(TERMINAL_LINES)
    left = round((width - block_width) / 2)
    top = (height - block_height) // 2

    baseline = top + get_baseline(pitch, CAP_PIXELS)
    for row, line in enumerate(TERMINAL_LINES):
        d.text((left, baseline + row * pitch), 1, line)

    # Block cursor waiting on the prompt line
    cursor_top = baseline + (len(TERMINAL_LINES) - 1) * pitch - CAP_PIXELS + 1
    d.draw.rectangle(xy=[(left + 7, cursor_top), (left + 10, cursor_top + CAP_PIXELS - 1)],
                     fill=255)

    save_image(render_crt(d, CRT_CELL, CRT_BG), "tiny5-sample3.jpg")


# --- Active-matrix TFT: the size ramp ---------------------------------------

TFT_GRID = (320, 180)
TFT_CELL = 6
TFT_BG = (238, 239, 240)
TFT_CHROME = (132, 134, 138)
TFT_LEAK = (28, 28, 28)         # backlight leaking through the closed cells
TFT_BOOST = (120, 120, 120)     # lift, so a lit pixel reads as its own color

# The same face from headline to native size, in device pixels, each step
# in its own color on the color LCD
# High key: a bright backlit panel, the text in a restrained palette that
# reads as one set, warm to cool as the size drops, none at full saturation
RAMP_ROWS = [
    (6, "Lorem ipsum", (206, 70, 56)),                               # coral
    (4, "Lorem ipsum dolor", (200, 138, 28)),                        # mustard
    (3, "Lorem ipsum dolor sit", (76, 138, 84)),                     # sage
    (2, "Lorem ipsum dolor sit amet", (48, 104, 176)),               # slate blue
    (1, "Lorem ipsum dolor sit amet, consectetur.", (56, 58, 62)),   # charcoal
]


def subpixel_pattern(size, cell):
    """Build the RGB stripe of an active-matrix color LCD: each cell split
    into a red, a green and a blue subpixel column, with the black matrix
    between them and between the rows."""
    width, height = size
    third = cell / 3
    row_on = []
    for x in range(width):
        cx = x % cell
        if cx >= cell - 1:
            row_on.append((0, 0, 0))
            continue
        band = int(cx / third)
        edge = cx % third
        on = edge >= 0.5 and edge < third - 0.5
        level = 255 if on else 110
        row_on.append([(level, 0, 0), (0, level, 0), (0, 0, level)][min(band, 2)])
    row_off = [(0, 0, 0)] * width
    data = []
    for y in range(height):
        data.extend(row_on if y % cell < cell - 1 else row_off)
    img = Image.new("RGB", size)
    img.putdata(data)

    return img


def render_tft(layers, cell, bg_color, backlight=(90, 96, 100),
               falloff=190, bezel=175):
    """Render as an active-matrix TFT LCD: backlit color pixels made of RGB
    subpixel stripes, glowing on dark glass, under a soft bezel shadow. Each
    layer carries the pixels of one color."""
    full = layers[0][0].image_size(cell)
    stripes = subpixel_pattern(full, cell)
    lits = [(display.lit(cell), color) for display, color in layers]

    # Backlight leaking through the closed cells, brighter at the center
    img = Image.new("RGB", full, bg_color)
    img = shade(img, radial_light(full, 255, falloff))
    img = ImageChops.add(img, ImageChops.multiply(
        stripes, Image.new("RGB", full, TFT_LEAK)))

    # Each layer's pixels open their subpixels to the layer's color, boosted
    # so the pixel reads as the intended color at viewing distance
    for lit, color in lits:
        colored = ImageChops.multiply(stripes, Image.new("RGB", full, color))
        colored = ImageChops.add(colored, ImageChops.multiply(
            Image.new("RGB", full, color), Image.new("RGB", full, TFT_BOOST)))
        img.paste(colored, (0, 0), lit)

    # Slight backlight bloom around the lit pixels
    all_lit = lits[0][0]
    for lit, _ in lits[1:]:
        all_lit = ImageChops.lighter(all_lit, lit)
    glow = all_lit.filter(ImageFilter.GaussianBlur(cell * 0.8)).point(lambda v: v * 30 // 100)
    img = ImageChops.screen(img, colorize(glow, backlight))

    return shade(img, edge_shadow(full, bezel))


def build_ramp():
    """A size ramp on a reflective color LCD module, 320x180 pixels: the
    same face from headline pixels down to the native size, each step in
    its own color, labeled in device pixels."""
    width = TFT_GRID[0]
    margin = 10

    chrome = Display(TFT_GRID)
    chrome.text((margin, 16), 1, "Tiny5 display test")
    chrome.text((width - margin, 16), 1, VERSION, anchor="rs")
    layers = [(chrome, TFT_CHROME)]

    baseline = 28
    for scale, string, color in RAMP_ROWS:
        d = Display(TFT_GRID)
        baseline += scale * CAP_PIXELS
        d.text((margin, baseline), scale, string)
        d.text((width - margin, baseline), 1, f"{scale * 6} pt", anchor="rs")
        baseline += 2 * scale + 8
        layers.append((d, color))

    save_image(render_tft(layers, TFT_CELL, TFT_BG, falloff=228, bezel=222),
               "tiny5-sample4.jpg")


# --- Paper -----------------------------------------------------------------

# Both printers run the same stock
PAPER_COLOR = (250, 249, 246)
PAPER_GRAIN = 9                 # depth of the paper grain, of 255


# --- Inkjet: the variation axes proof ---------------------------------------

INKJET_DOT = 4                  # Printer dot pitch, in image pixels
INKJET_INK = (36, 40, 52)       # Dye-based black: slightly weak and bluish
INKJET_SWATH = 50               # Nozzles per print head pass
INKJET_GAIN = (0.56, 0.70)      # Droplet radius range, in dots (dot gain > 0.5)
INKJET_SATELLITES = 0.03        # Chance of a stray satellite drop per edge dot

# The proof card: a running head over three rows of two blocks, each block
# an axis name with its technical tag beneath
PROOF_MARGIN = 120              # side margin, in image pixels
PROOF_MARGIN_Y = 84             # head and foot margin
PROOF_COLUMN = 900              # distance between the two columns
PROOF_WORD_SCALE = 22           # the axis name, in image pixels per font pixel
PROOF_TAG_SCALE = 8             # its tag, and the running head
PROOF_TAG_GAP = 30              # ink gap from an axis name down to its tag

# Each variation axis demonstrated by its own name, set with that axis
# pushed to its extreme
AXIS_ROWS = [
    ("weight", "wght 700", {"axes": [700, 100, 0, 0, 0]}),
    ("width", "wdth 75", {"axes": [300, 75, 0, 0, 0]}),
    ("slant", "italic", {"axes": [300, 100, 0, 0, 0], "italic": True}),
    ("roundness", "ROND 100", {"axes": [300, 100, 100, 0, 0]}),
    ("bleed", "BLED 70", {"axes": [200, 100, 0, 80, 0]}),
    ("jitter", "JITT 100", {"axes": [300, 100, 0, 0, 100]}),
]


def render_inkjet(mask, rng):
    """Print a full-resolution ink mask as an early inkjet would: rasterized
    to the printer's dot grid, each dot an overgrown droplet placed with a
    little error and the odd satellite, feathered into the paper fibers,
    with faint banding where the head passes meet."""
    size = mask.size
    dot = INKJET_DOT
    grid = (size[0] // dot, size[1] // dot)
    dots = mask.resize(grid, Image.BOX).point(lambda v: 255 if v >= 128 else 0)
    px = dots.load()

    ink = Image.new("L", size, 0)
    draw = ImageDraw.Draw(ink)
    lo, hi = INKJET_GAIN
    pass_offset = 0
    for y in range(grid[1]):
        # Each swath is a separate pass: a small vertical registration
        # error, and the last nozzle rows lay down a little less ink
        if y % INKJET_SWATH == 0:
            pass_offset = rng.uniform(-0.6, 0.6)
        row_level = 255 if y % INKJET_SWATH < INKJET_SWATH - 2 else 215
        for x in range(grid[0]):
            if not px[x, y]:
                continue
            cx = (x + 0.5) * dot + rng.uniform(-0.5, 0.5)
            cy = (y + 0.5) * dot + pass_offset + rng.uniform(-0.4, 0.4)
            r = rng.uniform(lo, hi) * dot
            draw.ellipse(xy=[cx - r, cy - r, cx + r, cy + r], fill=row_level)
            # Satellites spray off the edge dots
            edge = (x == 0 or y == 0 or x == grid[0] - 1 or y == grid[1] - 1 or
                    not (px[x - 1, y] and px[x + 1, y] and px[x, y - 1] and px[x, y + 1]))
            if edge and rng.random() < INKJET_SATELLITES:
                sx = cx + rng.uniform(-2.5, 2.5) * dot
                sy = cy + rng.uniform(-1.0, 1.0) * dot
                sr = rng.uniform(0.15, 0.3) * dot
                draw.ellipse(xy=[sx - sr, sy - sr, sx + sr, sy + sr], fill=170)

    # Ink wicks along the paper fibers: soften the droplets, then re-harden
    # the edge with a little correlated noise so the outline turns fibrous
    ink = ink.filter(ImageFilter.GaussianBlur(dot * 0.25))
    fibers = noise_image(size, rng).filter(ImageFilter.GaussianBlur(1.6))
    fibers = fibers.point(lambda v: 128 + (v - 128) * 1.8)
    ink = ImageChops.add(ink, fibers, scale=1.0, offset=-128)
    ink = ink.point(lambda v: min(255, max(0, (v - 128) * 4 + 128)))
    ink = ink.filter(ImageFilter.GaussianBlur(0.5))

    # Uneven absorption: the ink density drifts a little across the page
    density = noise_image((size[0] // 96 + 1, size[1] // 96 + 1), rng)
    density = density.resize(size, Image.BICUBIC).point(lambda v: 222 + v * 33 // 255)
    ink = ImageChops.multiply(ink, density)

    paper = shade(Image.new("RGB", size, PAPER_COLOR),
                  grain_field(size, rng, PAPER_GRAIN))

    return Image.composite(Image.new("RGB", size, INKJET_INK), paper, ink)


def build_axes():
    """A proof card for the variation axes, run off on an early inkjet: each
    axis shown by its own name, typeset with that axis at its extreme, drawn
    directly at a large size so the font's own axis effects reproduce
    faithfully, then rasterized to the printer's dots.

    The card is spaced on the ink rather than on the metrics: the axes push
    the glyphs to their own heights, so blocks stepped by a fixed baseline
    pitch would leave visibly uneven gaps. Each tag instead clears the
    descenders of its own row, and the space left over spreads evenly.
    """
    rng = random.Random(NOISE_SEED)
    mask = Image.new("L", CANVAS, 0)
    draw = ImageDraw.Draw(mask)

    def put(xy, scale, string, anchor="ls", **variant):
        font = get_font(scale, **variant)
        x = xy[0]
        if anchor[0] == "r":
            # Right-align on the ink, so the running head sits flush to the
            # margin at both ends; the advance runs a pixel past the ink
            x -= draw.textlength(string, font=font) - scale
            anchor = "l" + anchor[1]
        draw.text(xy=(x, xy[1]), text=string, fill=255, font=font, anchor=anchor)

    def ink(scale, strings):
        """Return how far the tallest of the strings inks above the baseline,
        and the deepest of them below it."""
        boxes = [draw.textbbox((0, 0), string, font=get_font(scale, **variant),
                               anchor="ls")
                 for string, variant in strings]

        return max(-box[1] for box in boxes), max(box[3] for box in boxes)

    left, right = PROOF_MARGIN, CANVAS[0] - PROOF_MARGIN
    head = [("Tiny5 variation test", {}), (VERSION, {})]
    rows = [AXIS_ROWS[i:i + 2] for i in range(0, len(AXIS_ROWS), 2)]

    # Measure every line, then share out what the blocks leave: one gap
    # above each row, all equal
    head_above, head_below = ink(PROOF_TAG_SCALE, head)
    blocks = []
    for row in rows:
        above, below = ink(PROOF_WORD_SCALE, [(word, v) for word, _, v in row])
        tag_above, tag_below = ink(PROOF_TAG_SCALE, [(tag, {}) for _, tag, _ in row])
        blocks.append((above, below + PROOF_TAG_GAP + tag_above, tag_below))
    filled = head_above + head_below + sum(sum(block) for block in blocks)
    gap = (CANVAS[1] - 2 * PROOF_MARGIN_Y - filled) // len(rows)

    y = PROOF_MARGIN_Y + head_above
    put((left, y), PROOF_TAG_SCALE, "Tiny5 variation test")
    put((right, y), PROOF_TAG_SCALE, VERSION, anchor="rs")
    y += head_below

    for row, (above, tag_offset, tag_below) in zip(rows, blocks):
        y += gap + above
        for column, (word, tag, variant) in enumerate(row):
            x = left + column * PROOF_COLUMN
            put((x, y), PROOF_WORD_SCALE, word, **variant)
            put((x, y + tag_offset), PROOF_TAG_SCALE, tag)
        y += tag_offset + tag_below

    save_image(render_inkjet(mask, rng), "tiny5-sample5.jpg")


# --- 9-pin dot matrix: the printer self test --------------------------------

# A dot-matrix printout on continuous form paper. A 9-pin printer covers
# 9 pixel rows per line, and prints double-spaced: one text line every two
# passes, so the paper's bars are 18 pixel rows tall (2 print lines), and
# text lands on every other bar.
MATRIX_GRID = (240, 135)
MATRIX_CELL = 8
PIN_ROWS = 9
LINE_PITCH = 2 * PIN_ROWS
BAR_COLOR = (216, 236, 228)
INK_COLOR = (38, 35, 42)
INK_SPREAD = (1.0, 0.7)         # Ink soaking into the paper, smeared by the head travel
INK_SKEW = 0.15                 # Paper feed misalignment, in degrees
INK_OFFSET = 2                  # Print head misalignment between passes, in pixels
INK_PATCH_SIZE = 24             # Size of the patches the ribbon inks unevenly, in cells
INK_PATCH_LEVEL = 165           # Ink level of the faintest patch, of 255
WEAK_PINS = 2                   # Print head pins that strike faintly

CONTENT_TOP = 4                 # top of the printed area, in cells
CONTENT_LEFT = LINE_PITCH       # text starts one line height in

# As on a real 9-pin self test, the printable character set streams line
# after line in a continuous wrap; an international section follows.
CHARSET_STREAM = "".join(chr(code) for code in range(33, 127))
ROLLING_LINES = 6
INTL_LINES = [
    # Vietnamese first: its tall diacritic stacks rise into the blank
    # separator line above
    "Do bạch kim rất quý nên sẽ dùng để lắp vô xương",
    "Jovencillo emponzoñado de whisky: ¡qué figurota exhibe!",
    "Zombif parvînt jusqu'à deux whisky-glace.",
    "Эх, чужак, общий съём цен шляп (юфть) – вдрызг!",
    "Γκόλφω, βάδιζε μπροστά ξανθή ψυχή!",
]


def draw_paper(size, cell, bar_top, rng):
    """Draw continuous form paper: green bars two print lines tall, the
    perforated tractor margin with its sprocket holes, and paper grain."""
    img = Image.new("RGB", size, PAPER_COLOR)
    draw = ImageDraw.Draw(img)

    # Green bars, each exactly 2 print lines (18 pixel rows) tall, so each
    # bar carries two single-spaced lines; the pattern continues down the
    # whole form
    for top in range(bar_top * cell, size[1], 2 * LINE_PITCH * cell):
        draw.rectangle(xy=[(CONTENT_LEFT * cell, top),
                           (size[0], top + LINE_PITCH * cell - 1)],
                       fill=BAR_COLOR)

    # Paper cut, creased and perforated
    x = CONTENT_LEFT * cell
    draw.rectangle(xy=[(x - 2, 0), (x + 1, size[1])], fill=(230, 230, 227))
    for y in range(0, size[1], 4 * cell):
        draw.rectangle(xy=[(x - 2, y), (x + 1, y + 2 * cell)], fill=(202, 202, 199))

    # Sprocket holes, punched through to the dark platen
    hole_radius = 2 * cell
    for y in range((bar_top + PIN_ROWS) * cell, size[1], LINE_PITCH * cell):
        xy = (CONTENT_LEFT * cell // 2, y)
        draw.circle(xy=xy, radius=hole_radius + 2, fill=(208, 208, 205))
        draw.circle(xy=xy, radius=hole_radius, fill=(28, 26, 30))

    return shade(img, grain_field(size, rng, PAPER_GRAIN))


def build_printout():
    """A 9-pin self test, struck dot by dot onto tractor paper: the ROM
    version, the character set streaming in a continuous wrap, and the
    international set, printed single-spaced on every line.

    The imperfections: the ribbon inks in patches, worn pins strike faintly,
    the head lands slightly off between passes, and the paper feeds in a
    little askew.
    """
    rng = random.Random(NOISE_SEED)
    d = Display(MATRIX_GRID)
    size = d.image_size(MATRIX_CELL)

    first_baseline = CONTENT_TOP + get_baseline(PIN_ROWS, CAP_PIXELS) + 1
    glyph_top = first_baseline - CAP_PIXELS

    text_left = CONTENT_LEFT + 2
    max_width = MATRIX_GRID[0] - text_left - 6

    # The character set streams continuously: each line picks up where the
    # last one left off, wrapping around the set
    lines = [f"SELF TEST  ROM {VERSION}  9 PIN", ""]
    position = 0
    for _ in range(ROLLING_LINES):
        line = ""
        while True:
            char = CHARSET_STREAM[position % len(CHARSET_STREAM)]
            if d.text_width(1, line + char) > max_width:
                break
            line += char
            position += 1
        lines.append(line)
    lines += [""] + INTL_LINES

    for i, line in enumerate(lines):
        d.text((text_left, first_baseline + i * PIN_ROWS), 1, line)
    cells = d.cells().load()

    # The ribbon inks unevenly in patches
    blotch_size = (max(MATRIX_GRID[0] // INK_PATCH_SIZE, 1),
                   max(MATRIX_GRID[1] // INK_PATCH_SIZE, 1))
    blotch = noise_image(blotch_size, rng).resize(MATRIX_GRID, Image.BICUBIC)
    blotch = blotch.point(lambda level: INK_PATCH_LEVEL
                          + level * (255 - INK_PATCH_LEVEL) // 255).load()

    # Worn print head pins strike faintly, the same rows on every line
    weak_pins = {pin: rng.randrange(150, 230)
                 for pin in rng.sample(range(CAP_PIXELS + 1), WEAK_PINS)}

    # Strike every dot, each slightly off in place, size and ink
    ink = Image.new("L", size, 0)
    ink_draw = ImageDraw.Draw(ink)
    for cy in range(MATRIX_GRID[1]):
        pin = (cy - glyph_top) % PIN_ROWS
        line_index = (cy - glyph_top) // PIN_ROWS
        pass_offset = INK_OFFSET * (line_index % 2)
        for cx in range(MATRIX_GRID[0]):
            if not cells[cx, cy]:
                continue
            level = blotch[cx, cy]
            if pin in weak_pins:
                level = level * weak_pins[pin] // 255
            x = cx * MATRIX_CELL + MATRIX_CELL / 2 + pass_offset + rng.uniform(-0.9, 0.9)
            y = cy * MATRIX_CELL + MATRIX_CELL / 2 + rng.uniform(-0.7, 0.7)
            radius = MATRIX_CELL * 0.56 * rng.uniform(0.92, 1.05)
            ink_draw.ellipse(xy=[x - radius, y - radius, x + radius, y + radius],
                             fill=level)

    # Ink soaks into the paper, and the paper feeds in slightly askew
    ink = ink.filter(ImageFilter.GaussianBlur(INK_SPREAD))
    ink = ink.rotate(INK_SKEW, resample=Image.BILINEAR)

    img = draw_paper(size, MATRIX_CELL, glyph_top - 2, rng)
    img.paste(Image.new("RGB", size, INK_COLOR), (0, 0), ink)

    save_image(img, "tiny5-sample6.jpg")


if __name__ == "__main__":
    build_hero()
    build_charset(False, "tiny5-sample1.jpg")   # 1: character ROM on a VFD
    build_charset(True, "tiny5-sample2.jpg")    # 2: Tiny5 Duo character ROM
    build_terminal()                            # 3: login session on an amber CRT
    build_ramp()                                # 4: size ramp on a color TFT
    build_axes()                                # 5: variation axes, inkjet proof
    build_printout()                            # 6: 9-pin printer self test
