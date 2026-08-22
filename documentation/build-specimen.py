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
    return (line_height - cap_height  + 1) // 2 + cap_height


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
        """Draw characters on a fixed pitch, centered in each column.

        Neither end of the measurement need land on a whole cell: an odd
        pitch puts the column center between two cells, and a character of
        even width straddles that center. Both are therefore kept exact, and
        only the pen is rounded, once. Rounding the row's origin and the
        character's offset separately would round each of them down, and the
        two half cells would add up to a whole one: every even-width
        character would sit a cell left of its column.
        """
        for column, char in enumerate(chars):
            slack = pitch - round(self.text_width(scale, char, duo))
            x = math.floor(left + column * pitch + slack / 2 + 0.5)
            self.text((x, baseline), scale, char, duo=duo)


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
    d.text((width - 6, 7), 1, "7:55", anchor="rs")

    # Title with its subtitle, and the softkey label
    d.text((center, 25), 3, "Tiny5", anchor="ms")
    d.text((center, 36), 1, "A 5-pixel font", anchor="ms")
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


def build_charset():
    """A character ROM chart on a HiFi deck's fluorescent display, with the
    glyphs at the native size: one font pixel per display cell."""
    d = Display(VFD_GRID)
    width, height = VFD_GRID
    margin = 3
    pitch = 9

    d.text((margin, 7), 1, "CHARACTER ROM")
    d.text((width - margin, 7), 1, VERSION, anchor="rs")

    # The six charset rows on a uniform 9-cell baseline rhythm, the block
    # centered in the space below the header. The exact left edge of the
    # column block, half cells and all: the row rounds the pen once, with
    # the character's own offset folded in
    left = (width - pitch * len(CHARSET_ROWS[0])) / 2
    for row, chars in enumerate(CHARSET_ROWS):
        d.char_row(left, 19 + row * pitch, pitch, 1, chars)

    save_image(render_emissive(d, VFD_CELL, VFD_BG, VFD_FG, VFD_GLOW),
               "tiny5-sample1.jpg")


# --- Active-matrix TFT: the size ramp ---------------------------------------

# A backlit color panel showing a display test in the one ink the firmware
# has: dark text on the white of the backlight, the chrome a step lighter
TFT_GRID = (240, 135)
TFT_CELL = 8
TFT_SUPER = 3                   # the panel is drawn this many times over size,
                                # and reduced once it is finished. A cell is
                                # 8 pixels across but carries three subpixel
                                # columns; only at a multiple of 3 does the
                                # stripe divide into whole columns, so it is
                                # laid down there and the reduction is what
                                # lands it back on the pixel
TFT_BG = (240, 238, 232)        # the backlight, through a slightly warm diffuser
TFT_INK = (52, 54, 58)
TFT_CHROME = (138, 140, 144)
TFT_LEAK = (28, 28, 28)         # backlight leaking through the closed cells
TFT_BOOST = (120, 120, 120)     # lift, so a lit pixel reads as its own color
TFT_MARGIN = 8                  # side margin, in cells
TFT_LABEL_GAP = 6               # cells between a row's text and its label

# The same face from headline to native size, in points at 6 pt per font
# pixel: every row shows the one test string, as much of it as fits the
# measure at that size, so the sizes compare word for word
RAMP_SCALES = [5, 3, 2, 1]
RAMP_TEXT = "The quick brown fox jumps over the lazy dog. Pack my box with five dozen liquor jugs."


def subpixel_pattern(size, cell, unit=1):
    """Build the RGB stripe of an active-matrix color LCD: each cell split
    into a red, a green and a blue subpixel column, with the black matrix
    between them and between the rows.

    The cell is given in the units the pattern is drawn in, and `unit` is
    how many of those make one pixel of the finished panel: the matrix and
    the gap along each subpixel column are set in finished pixels, so that
    supersampling refines the stripe without thinning it.
    """
    width, height = size
    third = cell // 3
    row = bytearray()
    for x in range(width):
        cx = x % cell
        if cx >= cell - unit:
            row += b"\0\0\0"
            continue
        band = min(cx // third, 2)
        edge = cx % third
        level = 255 if unit / 2 <= edge < third - unit / 2 else 110
        row += bytes(level if channel == band else 0 for channel in range(3))
    row_on = bytes(row)
    row_off = bytes(width * 3)
    rows = b"".join(row_on if y % cell < cell - unit else row_off
                    for y in range(height))

    return Image.frombytes("RGB", size, rows)


def render_tft(layers, cell, bg_color, backlight=(90, 96, 100),
               falloff=196, bezel=180):
    """Render as an active-matrix TFT LCD: backlit color pixels made of RGB
    subpixel stripes, glowing on dark glass, recessed in the bezel that
    shades its edges, the polarizer catching a sheen. Each layer carries
    the pixels of one color.

    The panel is drawn several times over size and reduced once it is
    finished: a subpixel column is a third of a cell, which is no whole
    number of pixels, and it is the reduction that resolves it the way the
    eye does at viewing distance.
    """
    sub = cell * TFT_SUPER
    full = layers[0][0].image_size(sub)
    stripes = subpixel_pattern(full, sub, TFT_SUPER)
    lits = [(display.lit(sub), color) for display, color in layers]

    # Backlight leaking through the closed cells, brighter at the center
    img = Image.new("RGB", full, bg_color)
    img = shade(img, radial_light(full, 255, falloff))
    img = ImageChops.add(img, ImageChops.multiply(
        stripes, Image.new("RGB", full, TFT_LEAK)))

    # Each layer's pixels open their subpixels to the layer's color, boosted
    # so the pixel reads as the intended color at viewing distance
    for lit, color in lits:
        boost = tuple(c * b // 255 for c, b in zip(color, TFT_BOOST))
        colored = ImageChops.multiply(stripes, Image.new("RGB", full, color))
        colored = ImageChops.add(colored, Image.new("RGB", full, boost))
        img.paste(colored, (0, 0), lit)

    # Slight backlight bloom around the lit pixels
    all_lit = lits[0][0]
    for lit, _ in lits[1:]:
        all_lit = ImageChops.lighter(all_lit, lit)
    glow = all_lit.filter(ImageFilter.GaussianBlur(sub * 0.8)).point(lambda v: v * 30 // 100)
    img = ImageChops.screen(img, colorize(glow, backlight))

    img = shade(img, edge_shadow(full, bezel))
    img = ImageChops.add(img, sheen(full, 8).convert("RGB"))

    return img.reduce(TFT_SUPER)


def build_ramp():
    """A size ramp on a color LCD module, 240x135 pixels: the same test
    string from headline down to the native size, each row filled to the
    measure and labeled with its size in points.

    The rows are spaced on the ink: each row is as tall as its capitals and
    descenders, and the space left over spreads evenly between the rows.
    """
    width, height = TFT_GRID
    margin = TFT_MARGIN
    left, right = margin, width - margin

    chrome = Display(TFT_GRID)
    chrome.text((left, margin + CAP_PIXELS), 1, "Tiny5 display test")
    chrome.text((right, margin + CAP_PIXELS), 1, VERSION, anchor="rs")
    layers = [(chrome, TFT_CHROME)]

    # The labels take a column at the right; the text fills what is left
    label_width = max(round(chrome.text_width(1, f"{scale * 6} pt"))
                      for scale in RAMP_SCALES)
    measure = right - label_width - TFT_LABEL_GAP - left

    # Each row's ink height: caps above the baseline, descenders below it,
    # at 2 font pixels; the leftover shares out equally between the rows
    rows = [scale * (CAP_PIXELS + 2) for scale in RAMP_SCALES]
    top = 2 * margin + CAP_PIXELS
    gap = (height - margin - top - sum(rows)) / len(rows)

    d = Display(TFT_GRID)
    y = top
    for scale, row in zip(RAMP_SCALES, rows):
        y += gap
        baseline = round(y + scale * CAP_PIXELS)
        line = ""
        for char in RAMP_TEXT:
            if d.text_width(scale, line + char) > measure:
                break
            line += char
        d.text((left, baseline), scale, line.rstrip())
        d.text((right, baseline), 1, f"{scale * 6} pt", anchor="rs")
        y += row
    layers.append((d, TFT_INK))

    save_image(render_tft(layers, TFT_CELL, TFT_BG), "tiny5-sample2.jpg")


# --- Flip-disc board: the departures ----------------------------------------

# An electromechanical departures board. Every pixel is a small disc, matte
# black on one face and day-glo yellow on the other, hung on a horizontal
# shaft over a black panel and turned over by a magnetic pulse; it then
# stays put, unpowered, until the next one. Nothing here emits light: the
# board is read by the light of the hall falling on it from above, and a
# little from the left, where the windows are.
FLIP_GRID = (160, 90)
FLIP_CELL = 12
FLIP_SUPER = 3                  # the board is drawn this many times over size,
                                # and reduced once it is finished
FLIP_LINE_PITCH = 10            # cells per module row: one text line
FLIP_MODULE_WIDTH = 32          # cells per module across
FLIP_PANEL = (14, 14, 15)       # the panel the discs are set into
FLIP_SEAM = (6, 6, 7)           # the joint where one module meets the next
FLIP_SEAM_EDGE = (36, 36, 39)   # and the edge of the module beyond, catching light
FLIP_SEAM_WIDTH = 2             # the joint, in pixels of the finished board
FLIP_SEAM_LIP = 1               # and that lit edge past it
FLIP_MODULE_SHIFT = 0.12        # how far a module may hang off the grid, in cells
FLIP_JITTER = 0.021             # and how far a disc hangs off its own center
FLIP_DARK = (58, 58, 62)        # the black face of a disc, at its brightest
FLIP_YELLOW = (250, 232, 60)    # day-glo, so it reads brighter than paper
FLIP_YELLOW_SCATTER = (8, 8, 10)  # how far one disc's pigment strays from it, per channel
FLIP_YELLOW_FADE = 0.03         # and how much one disc has bleached, of its brightness
FLIP_RADIUS = 0.49              # disc radius, in cells: they practically touch
FLIP_BITE = 0.09                # the notch bitten out of a disc where it is hung,
                                # in cells
FLIP_BITE_ANGLE = 15            # and where that notch sits, in degrees clockwise
                                # from the top: one o'clock
FLIP_RIM = 0.62                 # the rim of a black disc, turned from the light
FLIP_LIT_RIM = 0.90             # a day-glo face barely shades towards its rim
FLIP_RIM_START = 0.76           # where the rim starts, in fractions of radius
FLIP_GLOSS = 60                 # the arc a graphite rim catches from the light, of 255
FLIP_LIT_GLOSS = 12             # a matte pigment catches next to none
FLIP_LIGHT = (-0.42, -0.91)     # where the light comes from: above, and a little left
FLIP_TILT_SHORTEN = 0.16        # how much a tilted disc foreshortens
FLIP_TILT_SHADE = 0.04          # and how much that changes its brightness
FLIP_SHADOW = 150               # depth of a disc's shadow on the panel, of 255
FLIP_SHADOW_DROP = (0.06, 0.16)  # how far that shadow falls, in cells, right and down

# The columns: head, and left edge in cells. The heads are discs like the
# rest of the board, set in Duo to tell them from the flights.
#
# A column is as wide as its head or as its widest flight, whichever is
# wider: 22, 55, 21, and 44 for CANCELLED, which outruns its own head. The
# four of them take 142 of the board's 160 columns, and five cells between
# each pair of heads take 15 more, which leaves three for the two margins.
# The wider of them goes to the left, where every line starts; only
# CANCELLED, the one remark that outruns its own head, reaches the right.
FLIP_MARGIN = 2
DEPARTURE_COLUMNS = [("Time", FLIP_MARGIN), ("Destination", 30), ("Flight", 91),
                     ("Status", 124)]
DEPARTURES = [
    ("20:45", "ZÜRICH", "LX1077", "GATE A1"),
    ("20:45", "TOKYO", "NH224", "DELAYED"),
    ("20:55", "BARCELONA", "DE4327", "DELAYED"),
    ("21:00", "HELSINKI", "VL852", "ON TIME"),
    ("21:15", "KØBENHAVN", "SK676", "DELAYED"),
    ("21:22", "DÜSSELDORF", "LH3530", "ON TIME"),
    ("21:30", "SÃO PAULO", "LA8071", "ON TIME"),
    ("21:40", "REYKJAVÍK", "LH846", "ON TIME"),
]
# The heads take the first line of the board, the flights the lines after
# it, all on the module pitch, capitals centered in the line
FLIP_BASELINE = get_baseline(FLIP_LINE_PITCH, CAP_PIXELS)


def disc_shading(cell, radius, top, bottom, rim, gloss):
    """Build one cell of the shading of a flat disc, to be tiled over the
    board.

    A disc is matte and flat, not a bead: across its face the light falls
    off gently from the edge nearest the light to the one furthest from it,
    and only at the rim, where the disc turns over into its edge, does it
    drop away sharply. That turned edge is the one place a face has any
    gloss, and it catches the light in an arc on the side facing it.
    """
    tile = Image.new("L", (cell, cell), 0)
    px = tile.load()
    center = cell / 2
    span = radius * cell
    lx, ly = FLIP_LIGHT
    for y in range(cell):
        for x in range(cell):
            u = (x + 0.5 - center) / span
            v = (y + 0.5 - center) / span
            toward = -(u * lx + v * ly)     # 1 at the edge nearest the light
            level = top + (bottom - top) * (1 - toward) / 2
            d = (u * u + v * v) ** 0.5
            if d > FLIP_RIM_START:
                edge = min(1.0, (d - FLIP_RIM_START) / (1 - FLIP_RIM_START))
                level *= 1 - (1 - rim) * edge
                facing = max(0.0, toward / d)
                level += gloss * facing ** 3 * 4 * edge * (1 - edge)
            px[x, y] = max(0, min(255, round(level)))

    return tile


def tile_pattern(size, tile):
    """Tile a small image over the full size."""
    img = Image.new("L", size)
    for y in range(0, size[1], tile.size[1]):
        for x in range(0, size[0], tile.size[0]):
            img.paste(tile, (x, y))

    return img


def module_shifts(width, height, rng):
    """Hang the modules: no two sit quite alike in the frame, so each is a
    little off the grid, and the rows of discs jog where they meet."""
    return {(mx, my): (rng.uniform(-FLIP_MODULE_SHIFT, FLIP_MODULE_SHIFT),
                       rng.uniform(-FLIP_MODULE_SHIFT, FLIP_MODULE_SHIFT))
            for my in range(math.ceil(height / FLIP_LINE_PITCH))
            for mx in range(math.ceil(width / FLIP_MODULE_WIDTH))}


def disc_layout(cell, positions, rng, shifts):
    """Settle every disc: where it hangs, and how it has come to rest.

    No two discs come to rest at quite the same angle: one tilted towards
    the light stands a little brighter and, seen face on, a little shorter,
    since it turns about its shaft, which is horizontal. That scatter is
    what a flip-disc board looks like up close. Each disc is given as its
    center, its two radii and its brightness, of 1.
    """
    radius = FLIP_RADIUS * cell
    layout = []
    for cx, cy in positions:
        sx, sy = shifts[(cx // FLIP_MODULE_WIDTH, cy // FLIP_LINE_PITCH)]
        tilt = rng.uniform(-1.0, 1.0)
        x = (cx + sx + rng.uniform(-FLIP_JITTER, FLIP_JITTER) + 0.5) * cell
        y = (cy + sy + rng.uniform(-FLIP_JITTER, FLIP_JITTER) + 0.5) * cell
        ry = radius * (1 - FLIP_TILT_SHORTEN * abs(tilt))
        layout.append((x, y, radius, ry, 1 - FLIP_TILT_SHADE * tilt))

    return layout


def draw_discs(size, layout, bite, shaded=True):
    """Draw the discs of a layout into a mask, each at its own brightness,
    or all full on for a plain cut-out.

    A disc is not quite a circle. It hangs off its shaft by a single tab,
    and is bitten away around it, up at one o'clock; the discs sit so close
    that this notch is where the dark of the panel behind shows through.
    Every disc is laid down before any bite is taken, or a neighbour coming
    afterwards would fill one in again.
    """
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    for x, y, rx, ry, level in layout:
        draw.ellipse(xy=[x - rx, y - ry, x + rx, y + ry],
                     fill=max(0, min(255, round(255 * level))) if shaded else 255)
    angle = math.radians(FLIP_BITE_ANGLE)
    ux, uy = math.sin(angle), -math.cos(angle)
    for x, y, rx, ry, level in layout:
        hx, hy = x + ux * rx, y + uy * ry
        draw.ellipse(xy=[hx - bite, hy - bite, hx + bite, hy + bite], fill=0)

    return mask


def draw_faces(size, layout, rng):
    """Draw the day-glo faces of a layout: every disc its own batch of
    pigment, a shade more orange or greener than the next, and some a
    little bleached by the years under the hall's lights."""
    img = Image.new("RGB", size, (0, 0, 0))
    draw = ImageDraw.Draw(img)
    for x, y, rx, ry, level in layout:
        fade = level * (1 + rng.uniform(-FLIP_YELLOW_FADE, FLIP_YELLOW_FADE))
        color = tuple(max(0, min(255, round((c + rng.uniform(-s, s)) * fade)))
                      for c, s in zip(FLIP_YELLOW, FLIP_YELLOW_SCATTER))
        draw.ellipse(xy=[x - rx, y - ry, x + rx, y + ry], fill=color)

    return img


def hall_light(size):
    """Build the light of the hall: falling on the board from above and a
    little from the left, and dropping off towards the corners."""
    def level(u, v):
        du, dv = u - 0.5, v - 0.5
        corner = min(1.0, (du * du * 4 + dv * dv * 4) ** 0.5)

        return round(255 - 16 * v - 6 * u - 12 * corner ** 2)

    return light_field(size, level)


def render_flipdisc(display, cell, rng):
    """Render as a flip-disc board: every disc of the panel showing a face,
    the yellow ones where the text is and the black ones everywhere else,
    each casting its own small shadow on the panel behind.

    The board is drawn several times over size and reduced once it is
    finished. A disc's bites, and the joints between the modules, are finer
    than a pixel of it: drawn at size they would fall on or off a whole
    pixel, and it is the reduction that gathers them the way a camera does.
    """
    sub = cell * FLIP_SUPER
    full = display.image_size(sub)
    width, height = display.size
    cells = display.cells().load()

    # The panel, and the joints between its modules: each joint is a shadow
    # line, and past it the edge of the next module catches the light
    img = Image.new("RGB", full, FLIP_PANEL)
    draw = ImageDraw.Draw(img)
    joint = FLIP_SEAM_WIDTH * FLIP_SUPER // 2
    lip = FLIP_SEAM_LIP * FLIP_SUPER
    for x in range(0, full[0], FLIP_MODULE_WIDTH * sub):
        draw.rectangle(xy=[(x - joint, 0), (x + joint - 1, full[1])], fill=FLIP_SEAM)
        draw.rectangle(xy=[(x + joint, 0), (x + joint + lip - 1, full[1])],
                       fill=FLIP_SEAM_EDGE)
    for y in range(0, full[1], FLIP_LINE_PITCH * sub):
        draw.rectangle(xy=[(0, y - joint), (full[0], y + joint - 1)], fill=FLIP_SEAM)
        draw.rectangle(xy=[(0, y + joint), (full[0], y + joint + lip - 1)],
                       fill=FLIP_SEAM_EDGE)

    # Every disc of the board is there, whichever way it is turned: they are
    # laid out as one field, and the yellow faces picked out of it afterwards
    positions = [(x, y) for y in range(height) for x in range(width)]
    layout = disc_layout(sub, positions, rng, module_shifts(width, height, rng))
    bite = FLIP_BITE * sub
    discs = draw_discs(full, layout, bite)
    lit_layout = [disc for disc, (x, y) in zip(layout, positions) if cells[x, y]]
    lit = draw_discs(full, lit_layout, bite, shaded=False)

    # Each disc stands off the panel, and drops a shadow onto it, away from
    # the light
    shadow = discs.filter(ImageFilter.GaussianBlur(sub * 0.16))
    shadow = ImageChops.offset(shadow, *(max(1, round(sub * drop))
                                         for drop in FLIP_SHADOW_DROP))
    img = shade(img, shadow.point(lambda v: 255 - v * FLIP_SHADOW // 255))

    # The black faces: graphite, dark enough that the board reads as black
    # until you look for them, and then it is their glossy rims you see
    dark_shade = tile_pattern(full, disc_shading(sub, FLIP_RADIUS, 255, 74,
                                                 FLIP_RIM, FLIP_GLOSS))
    dark = ImageChops.multiply(colorize(discs, FLIP_DARK), dark_shade.convert("RGB"))
    img = ImageChops.lighter(img, dark)

    # The yellow faces: day-glo pigment, which scatters what falls on it
    # almost evenly, so the face reads flat
    lit_shade = tile_pattern(full, disc_shading(sub, FLIP_RADIUS, 255, 240,
                                                 FLIP_LIT_RIM, FLIP_LIT_GLOSS))
    yellow = ImageChops.multiply(draw_faces(full, lit_layout, rng),
                                 lit_shade.convert("RGB"))
    img.paste(yellow, (0, 0), lit)

    return shade(img, hall_light(full)).reduce(FLIP_SUPER)


def build_departures():
    """The departures hall board: the column heads in Duo, and eight
    flights below them, all in yellow discs."""
    rng = random.Random(NOISE_SEED)
    d = Display(FLIP_GRID)

    for name, x in DEPARTURE_COLUMNS:
        d.text((x, FLIP_BASELINE), 1, name, duo=True)
    for line, fields in enumerate(DEPARTURES, start=1):
        baseline = FLIP_BASELINE + line * FLIP_LINE_PITCH
        for (name, x), field in zip(DEPARTURE_COLUMNS, fields):
            d.text((x, baseline), 1, field)

    save_image(render_flipdisc(d, FLIP_CELL, rng), "tiny5-sample3.jpg")


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
# an axis name with its technical tag beneath. The card is trimmed to a wide
# side margin and a narrower one head and foot, and the blocks stand in two
# equal columns across the measure it leaves
PROOF_MARGIN_X = 181            # side margin, in image pixels
PROOF_MARGIN_Y = 84             # head and foot margin, in image pixels
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

    Across the page it is set the same way. Bleed swells the ink past the
    pen and slant and jitter lean and shift it, so lines placed by their
    pens would hang off the column by a fraction of a font pixel: every
    line is set against its own ink instead. That squares the running head
    with the margin at both ends, ranges each tag under its axis name, and
    leaves the two columns to divide the measure equally.
    """
    rng = random.Random(NOISE_SEED)
    mask = Image.new("L", CANVAS, 0)
    draw = ImageDraw.Draw(mask)

    def ink_box(scale, string, **variant):
        """Return the box the string's ink covers, relative to its pen.

        The axes carry the ink outside the glyph boxes: bleed spreads it past
        every side, and slant and jitter lean and shift it. The text metrics
        report the advance and the nominal line instead, so the ink is
        measured by setting the string on its own and taking the box that
        comes back.
        """
        font = get_font(scale, **variant)
        pad = 2 * scale          # room for the ink that falls outside the pen
        width = round(draw.textlength(string, font=font)) + 2 * pad
        height = 2 * (font.size + pad)
        proof = Image.new("L", (width, height), 0)
        ImageDraw.Draw(proof).text(xy=(pad, height // 2), text=string, fill=255,
                                   font=font, anchor="ls")
        box = proof.getbbox()

        return (box[0] - pad, box[1] - height // 2,
                box[2] - pad, box[3] - height // 2)

    def put(xy, scale, string, anchor="ls", **variant):
        """Draw a string set against x by its ink rather than by its pen, so
        that a column edge, and the running head, line up on what shows."""
        box = ink_box(scale, string, **variant)
        x = xy[0] - (box[2] if anchor[0] == "r" else box[0])
        draw.text(xy=(x, xy[1]), text=string, fill=255,
                  font=get_font(scale, **variant), anchor="l" + anchor[1])

    def ink(scale, strings):
        """Return how far the tallest of the strings inks above the baseline,
        and the deepest of them below it."""
        boxes = [ink_box(scale, string, **variant) for string, variant in strings]

        return max(-box[1] for box in boxes), max(box[3] for box in boxes)

    left, right = PROOF_MARGIN_X, CANVAS[0] - PROOF_MARGIN_X
    column = (right - left) // 2        # pitch of the two columns
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
        for index, (word, tag, variant) in enumerate(row):
            x = left + index * column
            put((x, y), PROOF_WORD_SCALE, word, **variant)
            put((x, y + tag_offset), PROOF_TAG_SCALE, tag)
        y += tag_offset + tag_below

    save_image(render_inkjet(mask, rng), "tiny5-sample4.jpg")


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
    "login: gissio",
    "Last login: Fri Jun 5 07:55 on tty5",
    "",
    "$ fc-query --brief Tiny5",
    "    family: \"Tiny5\"",
    "    version: " + VERSION,
    "    glyphs: 1655",
    "    languages: 897",
    "    axes: weight width slant round bleed jitter",
    "    pixel-perfect render: multiples of 6 pt (8 px)",
    "$ setfont Tiny5",
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
    d.draw.rectangle(xy=[(left + 6, cursor_top), (left + 9, cursor_top + CAP_PIXELS - 1)],
                     fill=255)

    save_image(render_crt(d, CRT_CELL, CRT_BG), "tiny5-sample5.jpg")


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
CONTENT_LEFT = LINE_PITCH       # the paper's pre-cut, one line height in
TEXT_INDENT = 9                 # text starts this far right of the pre-cut, in cells

# As on a real 9-pin self test, the printable character set streams line
# after line in a continuous wrap; an international section follows.
CHARSET_STREAM = "".join(chr(code) for code in range(33, 127))
ROLLING_LINES = 4
INTL_LINES = [
    # Vietnamese first: its tall diacritic stacks rise into the blank
    # separator line above
    "Do bạch kim rất quý nên sẽ dùng để lắp vô xương.",
    "Jovencillo emponzoñado de whisky: ¡qué figurota exhibe!",
    "Zombif parvînt jusqu'à deux whisky-glace.",
    "Fürge rőt róka túlszökik zsíros étkű kutyán.",
    "Pchnąć w tę łódź jeża lub ośm skrzyń fig.",
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
    # whole form-
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

    text_left = CONTENT_LEFT + TEXT_INDENT
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
    build_charset()                             # 1: character ROM on a VFD
    build_ramp()                                # 2: size ramp on a color TFT
    build_departures()                          # 3: departures board, flip discs
    build_axes()                                # 4: variation axes, inkjet proof
    build_terminal()                            # 5: login session on an amber CRT
    build_printout()                            # 6: 9-pin printer self test
