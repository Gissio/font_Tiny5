# Procedural specimen images for Tiny5.
#
# Every image is an artifact of a fictional 1980s pocket-electronics maker:
# the screens are simulated period displays, drawn entirely in code so the
# font pixels stay crisp and the images can be rendered at any target size.
#
# All text is composed on a low-resolution cell grid (1 image = one display),
# then upscaled with NEAREST so every font pixel maps to whole display cells.

import math
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT_PATH = Path(__file__).resolve().parent.parent
OUT_PATH = Path(__file__).resolve().parent

TINY5_PATH = ROOT_PATH / "fonts/variable/Tiny5[BLED,JITT,ROND,wdth,wght].ttf"
TINY5_DUO_PATH = ROOT_PATH / "fonts/variable/Tiny5Duo[BLED,JITT,ROND,wdth,wght].ttf"
TINY5_ITALIC_PATH = ROOT_PATH / "fonts/variable/Tiny5-Italic[BLED,JITT,ROND,wdth,wght].ttf"

# Variation axes: weight, width, roundness, bleed, jitter.
# Full weight, so every font pixel fills its display cells exactly; the
# LCD segmentation comes from the rendered cell pattern, not the font.
LCD_AXES = [400, 100, 0, 0, 0]

# Tiny5 draws one font pixel per 8 font units, and is 5 font pixels tall
FONT_PIXEL_SIZE = 8
CAP_PIXELS = 5

JPG_QUALITY = 95

# Text at 2+ cells per font pixel rasterizes cleanly at cell resolution, but
# at 1 cell per font pixel the tiny ppem garbles the glyphs. Native-size text
# is therefore drawn on a separate layer at FINE times the cell resolution
# (where rendering is proven crisp) and reduced to cells afterwards.
FINE = 4


def get_font(scale, duo=False, axes=None, italic=False):
    """Load Tiny5 sized so one font pixel covers `scale` display cells,
    optionally as the italic variant or at other axis settings."""
    path = TINY5_ITALIC_PATH if italic else (TINY5_DUO_PATH if duo else TINY5_PATH)
    font = ImageFont.truetype(font=str(path), size=FONT_PIXEL_SIZE * scale)
    font.set_variation_by_axes(axes or LCD_AXES)

    return font


class Display:
    """A monochrome dot-matrix display, composed in cell coordinates."""

    def __init__(self, grid_size):
        self.grid_size = grid_size
        self.mask = Image.new("L", grid_size, 0)
        self.draw = ImageDraw.Draw(self.mask)
        fine_size = (grid_size[0] * FINE, grid_size[1] * FINE)
        self.fine = Image.new("L", fine_size, 0)
        self.fine_draw = ImageDraw.Draw(self.fine)

    @property
    def size(self):
        return self.grid_size

    def cells(self):
        """Return the finished cell mask: on/off per display cell.

        The fine layer is point-sampled rather than averaged: sampling hits
        the interior of each font-pixel square, so edge antialiasing cannot
        double or erode pixels the way block averaging does.
        """
        reduced = self.fine.resize(self.grid_size, Image.NEAREST)
        mask = ImageChops.lighter(self.mask, reduced)

        return mask.point(lambda v: 255 if v >= 128 else 0)

    def text(self, xy, scale, string, anchor="ls", duo=False):
        """Draw text with the baseline (or anchor) at cell position xy.

        Center and right anchors are resolved against the ink extents of the
        string (not its advance width), so text centers optically.
        """
        if scale >= 2:
            font = get_font(scale, duo)
            x = xy[0]
            if anchor[0] in "mr":
                bbox = self.draw.textbbox((0, 0), string, font=font, anchor="ls")
                ink = (bbox[0] + bbox[2]) / 2 if anchor[0] == "m" else bbox[2]
                x = round(x - ink)
            self.draw.text(xy=(x, xy[1]), text=string, fill=255,
                           font=font, anchor="l" + anchor[1])
        else:
            # Native-size text must also keep a constant pixel phase: anchor
            # math would shift it by fractional cells, so the pen lands on
            # whole cells. The glyph squares sit half a font pixel right of
            # the pen at this size, hence the constant half-cell shift.
            font = get_font(scale * FINE, duo)
            x = xy[0] * FINE
            if anchor[0] in "mr":
                bbox = self.fine_draw.textbbox((0, 0), string, font=font, anchor="ls")
                ink = (bbox[0] + bbox[2]) / 2 if anchor[0] == "m" else bbox[2]
                x -= round(ink / FINE) * FINE
            self.fine_draw.text(xy=(x - FINE // 2, xy[1] * FINE), text=string,
                                fill=255, font=font, anchor="l" + anchor[1])

    def text_width(self, scale, string, duo=False):
        """Return the width of the string, in cells."""
        if scale >= 2:
            return self.draw.textlength(string, font=get_font(scale, duo))

        return self.fine_draw.textlength(string, font=get_font(scale * FINE, duo)) / FINE

    def char_row(self, left, baseline, pitch, scale, chars, duo=False):
        """Draw characters on a fixed pitch, centered in each column."""
        for column, char in enumerate(chars):
            x = left + column * pitch + pitch // 2
            self.text((x, baseline), scale, char, anchor="ms", duo=duo)

    def battery(self, x, top):
        """Draw a small upright battery icon: tip on a hollow body."""
        self.draw.rectangle(xy=[(x + 1, top), (x + 1, top)], fill=255)
        self.draw.rectangle(xy=[(x, top + 1), (x + 2, top + 6)], outline=255, width=1)


def cell_gap(cell):
    """Gap between display cells, proportional to the cell size."""
    return max(1, round(cell / 8))


def cell_pattern(size, cell, gap=1):
    """Build a full-size mask that is on inside each display cell."""
    width, height = size
    row_on = bytes(255 if x % cell < cell - gap else 0 for x in range(width))
    row_off = bytes(width)
    rows = b"".join(row_on if y % cell < cell - gap else row_off
                    for y in range(height))

    return Image.frombytes("L", size, rows)


def scanline_pattern(size, cell, gap):
    """Build a mask of horizontal scanlines: the raster of a CRT."""
    width, height = size
    row_on = bytes([255] * width)
    row_off = bytes(width)
    rows = b"".join(row_on if y % cell < cell - gap else row_off
                    for y in range(height))

    return Image.frombytes("L", size, rows)


def noise_image(size, rng):
    """Build an image of uniform random noise."""
    return Image.frombytes("L", size, rng.randbytes(size[0] * size[1]))


def sheen(size, strength=10):
    """Build a soft diagonal highlight, light catching the polarizer film."""
    small = Image.new("L", (64, 36))
    small.putdata([round(strength * math.exp(-(x / 63 + y / 35 - 0.55) ** 2 / 0.065))
                   for y in range(36) for x in range(64)])

    return small.resize(size, Image.BICUBIC)


def edge_shadow(size, level=205):
    """Build an inner-shadow field: the bezel shading the recessed screen."""
    small = Image.new("L", (64, 36), 255)
    ImageDraw.Draw(small).rectangle(xy=[(0, 0), (63, 35)], outline=level, width=2)
    small = small.filter(ImageFilter.GaussianBlur(1.2))

    return small.resize(size, Image.BICUBIC)


def radial_light(size, center_level, edge_level):
    """Build a smooth radial lighting field, brightest in the center."""
    small_size = (64, 36)
    small = Image.new("L", small_size)
    data = []
    for y in range(small_size[1]):
        for x in range(small_size[0]):
            dx = x / (small_size[0] - 1) - 0.5
            dy = y / (small_size[1] - 1) - 0.5
            d = min(1.0, (dx * dx * 4 + dy * dy * 4) ** 0.5)
            data.append(round(center_level + (edge_level - center_level) * d ** 1.5))
    small.putdata(data)

    return small.resize(size, Image.BICUBIC)


def colorize(mask_img, color, background_color=(0, 0, 0)):
    """Build an image that fades from the background color to the color over the mask."""
    return Image.composite(Image.new("RGB", mask_img.size, color),
                           Image.new("RGB", mask_img.size, background_color),
                           mask_img)


def render_reflective(display, cell, bg_color, fg_color, canvas_size=None):
    """Render as a reflective LCD with a single pixel color."""
    return render_reflective_layers([(display, fg_color)], cell, bg_color,
                                    canvas_size)


def render_reflective_layers(layers, cell, bg_color, canvas_size=None):
    """Render as a reflective LCD: pixels floating over a pale ground, one
    color per layer, as on a passive color display.

    The unlit cells show faintly (the classic LCD ghost grid), and the lit
    pixels cast a soft shadow onto the reflector behind the liquid crystal.
    If a larger canvas size is given, the display is centered on it, with
    the surround darkened like the glass edge of the module.
    """
    full = (layers[0][0].size[0] * cell, layers[0][0].size[1] * cell)
    pattern = cell_pattern(full, cell, cell_gap(cell))

    lits = [(ImageChops.multiply(display.cells().resize(full, Image.NEAREST),
                                 pattern), color)
            for display, color in layers]
    combined = lits[0][0]
    for lit, _ in lits[1:]:
        combined = ImageChops.lighter(combined, lit)

    # Ambient light only, as with the backlight off: nearly even, with a
    # gentle falloff towards the corners
    img = Image.new("RGB", full, bg_color)
    img = ImageChops.multiply(img, radial_light(full, 252, 230).convert("RGB"))

    # Ghost grid: every cell of the display is faintly visible
    ghost = pattern.point(lambda v: 246 if v else 255)
    img = ImageChops.multiply(img, ghost.convert("RGB"))

    # Drop shadow of the lit pixels on the reflector
    shadow = combined.filter(ImageFilter.GaussianBlur(cell * 0.6))
    shadow = ImageChops.offset(shadow, cell // 2, cell * 2 // 3)
    img = ImageChops.multiply(img, shadow.point(lambda v: 255 - v * 60 // 255).convert("RGB"))

    for lit, color in lits:
        img.paste(Image.new("RGB", full, color), (0, 0), lit)

    # The screen sits recessed in the bezel, which shades its edges; light
    # catches the polarizer film in a soft diagonal sheen
    img = ImageChops.multiply(img, edge_shadow(full).convert("RGB"))
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


def barrel(img, k=0.06):
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
    width, height = size
    column = Image.new("L", (1, height))
    levels = []
    for y in range(height):
        offset = ((y % pitch) + 0.5) / pitch - 0.5
        weight = math.exp(-abs(offset / sigma) ** BEAM_EXPONENT)
        levels.append(round(BEAM_FLOOR + (255 - BEAM_FLOOR) * weight))
    column.putdata(levels)

    return column.resize(size, Image.NEAREST)


def render_crt(display, cell, bg_color):
    """Render as a bright monochrome CRT.

    The electron beam sweeps one scanline per raster row, its width growing
    with beam current; where it saturates the phosphor the emission washes
    out to white, haloed by the phosphor's own bluish green. The tube then
    curves and vignettes the picture, and the glass reflects the room.
    """
    full = (display.size[0] * cell, display.size[1] * cell)
    pitch = cell           # one scanline per font pixel

    # The spot is round, so it smears horizontally as it sweeps
    lit = display.cells().resize(full, Image.NEAREST)
    lit = lit.filter(ImageFilter.GaussianBlur((cell * 0.22, cell * 0.05)))

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
    grain = noise_image(full, random.Random(PRINT_SEED))
    img = ImageChops.multiply(img, grain.point(lambda v: 238 + v * 17 // 255).convert("RGB"))

    # The tube curves the picture, the glass vignettes it, and a window
    # across the room reflects faintly off the screen
    img = barrel(img, 0.035)
    img = ImageChops.multiply(img, radial_light(full, 255, 196).convert("RGB"))
    img = ImageChops.screen(img, colorize(glass_reflection(full).point(lambda v: v * 2 // 3),
                                          (176, 158, 134)))

    return img


def mesh_pattern(size, pitch, level):
    """Build the transmission mask of the control grid: a fine wire mesh
    that shades every `pitch`th row and column."""
    width, height = size
    row_wire = bytes([level] * width)
    row_open = bytes(level if x % pitch == 0 else 255 for x in range(width))
    rows = b"".join(row_wire if y % pitch == 0 else row_open
                    for y in range(height))

    return Image.frombytes("L", size, rows)


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


def render_tft(layers, cell, bg_color, backlight=(90, 96, 100)):
    """Render as an active-matrix TFT LCD: backlit color pixels made of RGB
    subpixel stripes, glowing on dark glass, under a soft bezel shadow."""
    full = (layers[0][0].size[0] * cell, layers[0][0].size[1] * cell)
    stripes = subpixel_pattern(full, cell)

    # Backlight leaking through the closed cells, brighter at the center
    img = Image.new("RGB", full, bg_color)
    img = ImageChops.multiply(img, radial_light(full, 255, 190).convert("RGB"))
    leak = ImageChops.multiply(stripes, Image.new("RGB", full, (28, 28, 28)))
    img = ImageChops.add(img, leak)

    # Each layer's pixels open their subpixels to the layer's color
    for display, color in layers:
        lit = display.cells().resize(full, Image.NEAREST)
        colored = ImageChops.multiply(stripes, Image.new("RGB", full, color))
        # Boost so the pixel reads as the intended color at viewing distance
        colored = ImageChops.add(colored, ImageChops.multiply(
            Image.new("RGB", full, color), Image.new("RGB", full, (120, 120, 120))))
        img.paste(colored, (0, 0), lit)

    # Slight backlight bloom around the lit pixels
    all_lit = None
    for display, _ in layers:
        lit = display.cells().resize(full, Image.NEAREST)
        all_lit = lit if all_lit is None else ImageChops.lighter(all_lit, lit)
    glow = all_lit.filter(ImageFilter.GaussianBlur(cell * 0.8)).point(lambda v: v * 30 // 100)
    img = ImageChops.screen(img, colorize(glow, backlight))

    img = ImageChops.multiply(img, edge_shadow(full, 175).convert("RGB"))

    return img


def render_emissive(display, cell, bg_color, fg_color, glow_color):
    """Render as a VFD: phosphor segments glowing through the control grid
    mesh, haloed behind the tinted front glass."""
    full = (display.size[0] * cell, display.size[1] * cell)

    lit = display.cells().resize(full, Image.NEAREST)
    pattern = cell_pattern(full, cell, cell_gap(cell))
    lit = ImageChops.multiply(lit, pattern)

    # The control grid mesh shades the glowing segments
    lit = ImageChops.multiply(lit, mesh_pattern(full, VFD_MESH_PITCH, 202))

    img = Image.new("RGB", full, bg_color)
    img = ImageChops.multiply(img, radial_light(full, 255, 200).convert("RGB"))

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


def save_image(img, filename):
    img.save(OUT_PATH / filename, optimize=True, quality=JPG_QUALITY)


CANVAS = (1920, 1080)

# The classic 84x48 phone LCD, in its green backlit scheme
NOKIA_GRID = (84, 48)
NOKIA_CELL = 22
NOKIA_BG = (177, 186, 158)
NOKIA_FG = (30, 39, 29)

# Vacuum fluorescent display, the glow of a HiFi deck's front panel: ZnO:Zn
# phosphor emitting bluish green at ~505 nm behind tinted glass, its anode
# segments seen through the fine mesh of the control grid
VFD_GRID = (128, 72)
VFD_CELL = 15
VFD_BG = (7, 15, 15)
VFD_FG = (185, 255, 228)
VFD_GLOW = (26, 158, 128)
VFD_MESH_PITCH = 5

# A green-phosphor terminal, 192x108 raster. A bright P31-class tube, as on
# Apple and DEC monitors: luminous cyan-green with whitening cores, strong
# halation, and a fine scanline texture of about two lines per pixel.
# One scanline per font pixel, as a terminal drawing a 5x7 character cell
# does, so the raster is zoomed in rather than subdivided
CRT_GRID = (192, 108)
CRT_CELL = 10
CRT_LINE_PITCH = 7
CRT_BG = (16, 9, 2)

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

# A dot-matrix printout on continuous form paper. A 9-pin printer covers
# 9 pixel rows per line, and prints double-spaced: one text line every two
# passes, so the paper's bars are 18 pixel rows tall (2 print lines), and
# text lands on every other bar.
MATRIX_GRID = (240, 135)
MATRIX_CELL = 8
PIN_ROWS = 9
LINE_PITCH = 2 * PIN_ROWS
PAPER_COLOR = (250, 249, 246)
BAR_COLOR = (216, 236, 228)
INK_COLOR = (38, 35, 42)
PRINT_SEED = 5
INK_SPREAD = (1.0, 0.7)         # Ink soaking into the paper, smeared by the head travel
INK_SKEW = 0.15                 # Paper feed misalignment, in degrees
INK_OFFSET = 2                  # Print head misalignment between passes, in pixels
INK_PATCH_SIZE = 24             # Size of the patches the ribbon inks unevenly, in cells
INK_PATCH_LEVEL = 165           # Ink level of the faintest patch, of 255
WEAK_PINS = 2                   # Print head pins that strike faintly


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
    d.battery(width - 4, 1)
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
    d.text((width - 5, 7), 1, "5:55", anchor="rs")

    # Title with its subtitle, and the softkey label
    d.text((center, 25), 3, "Tiny5", anchor="ms")
    d.text((center, 36), 1, "Every pixel counts", anchor="ms")
    d.text((center, height - 1), 1, "Menu", anchor="ms", duo=True)

    img = render_reflective(d, NOKIA_CELL, NOKIA_BG, NOKIA_FG, CANVAS)
    save_image(img, "tiny5-presentation.jpg")


CHARSET_ROWS = [
    "ABCDEFGHIJKLM",
    "NOPQRSTUVWXYZ",
    "abcdefghijklm",
    "nopqrstuvwxyz",
    "0123456789%&@",
    "!?#*+-=/().,:",
]


def build_charset(duo, filename):
    """A character ROM chart on a HiFi deck's fluorescent display, with the
    glyphs at the native size: one font pixel per display cell."""
    d = Display(VFD_GRID)
    width, height = VFD_GRID
    margin = 3

    d.text((margin, 7), 1, "CHARACTER ROM")
    d.text((width - margin, 7), 1, "Tiny5 Duo" if duo else "Tiny5", anchor="rs")

    pitch = 9
    left = (width - pitch * 13) // 2
    # Eight lines on one uniform 9-cell baseline rhythm: the header, the six
    # charset rows, and the footer
    for row, chars in enumerate(CHARSET_ROWS):
        d.char_row(left, 16 + row * 9, pitch, 1, chars, duo=duo)

    d.text((margin, height - 2), 1, "1655 glyphs")
    d.text((width - margin, height - 2), 1, "897 languages", anchor="rs")

    save_image(render_emissive(d, VFD_CELL, VFD_BG, VFD_FG, VFD_GLOW), filename)


TERMINAL_LINES = [
    "login: guest",
    "Last login: Fri Jun 5 05:55 on tty5",
    "",
    "$ setfont tiny5",
    "Font loaded: Tiny5, 5 pixels tall.",
    "$ fc-query --brief tiny5",
    "family: Tiny5 + Tiny5 Duo",
    "axes: weight width slant round bleed jitter",
    "pixel-perfect render: multiples of 8 px",
    "",
    "$ echo Every pixel counts",
    "Every pixel counts",
    "$",
]


def get_baseline(line_height, cap_height):
    """Return the baseline offset that centers capital letters within a line."""
    return (line_height - cap_height) // 2 + cap_height


def build_terminal():
    """A session on a green-phosphor terminal, listing the font's specs.

    The layout follows documentation/build-images.py: left margin of 8
    cells, 10 cells per line, capitals centered within the line.
    """
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

CONTENT_TOP = 4                 # top of the printed area, in cells
CONTENT_LEFT = LINE_PITCH       # text starts one line height in, as in build-images.py


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

    # Paper grain
    grain = noise_image(size, rng).point(lambda level: 246 + level * 9 // 255)

    return ImageChops.multiply(img, grain.convert("RGB"))


def build_printout():
    """A 9-pin self test, struck dot by dot onto tractor paper: the ROM
    version, the character set streaming in a continuous wrap, and the
    international set, printed single-spaced on every line.

    The imperfections: the ribbon inks in patches, worn pins strike faintly,
    the head lands slightly off between passes, and the paper feeds in a 
    little askew.
    """
    rng = random.Random(PRINT_SEED)
    size = (MATRIX_GRID[0] * MATRIX_CELL, MATRIX_GRID[1] * MATRIX_CELL)

    first_baseline = CONTENT_TOP + get_baseline(PIN_ROWS, CAP_PIXELS) + 1
    glyph_top = first_baseline - CAP_PIXELS

    d = Display(MATRIX_GRID)
    text_left = CONTENT_LEFT + 2
    max_width = MATRIX_GRID[0] - text_left - 6

    # The character set streams continuously: each line picks up where the
    # last one left off, wrapping around the set
    lines = ["SELF TEST  ROM V2.003  9 PIN", ""]
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


INKJET_DOT = 4                  # Printer dot pitch, in image pixels
INKJET_INK = (36, 40, 52)       # Dye-based black: slightly weak and bluish
INKJET_SWATH = 50               # Nozzles per print head pass
INKJET_GAIN = (0.56, 0.70)      # Droplet radius range, in dots (dot gain > 0.5)
INKJET_SATELLITES = 0.03        # Chance of a stray satellite drop per edge dot


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
    for y in range(grid[1]):
        # Each swath is a separate pass: a small vertical registration
        # error, and the last nozzle rows lay down a little less ink
        pass_offset = rng.uniform(-0.6, 0.6) if y % INKJET_SWATH == 0 else pass_offset if y else 0
        row_in_pass = y % INKJET_SWATH
        row_level = 255 if row_in_pass < INKJET_SWATH - 2 else 215
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

    paper = Image.new("RGB", size, PAPER_COLOR)
    grain = noise_image(size, rng).point(lambda level: 246 + level * 9 // 255)
    paper = ImageChops.multiply(paper, grain.convert("RGB"))
    img = Image.composite(Image.new("RGB", size, INKJET_INK), paper, ink)

    return img


def build_axes():
    """A proof card for the variation axes, run off on an early inkjet: each
    axis shown by its own name, typeset with that axis at its extreme, drawn
    directly at a large size so the font's own axis effects reproduce
    faithfully, then rasterized to the printer's dots."""
    rng = random.Random(PRINT_SEED)
    mask = Image.new("L", CANVAS, 0)
    draw = ImageDraw.Draw(mask)

    def put(xy, scale, string, anchor="ls", **variant):
        draw.text(xy=xy, text=string, fill=255,
                  font=get_font(scale, **variant), anchor=anchor)

    left, right = 120, CANVAS[0] - 120
    put((left, 108), 8, "Tiny5 variation test")
    put((right, 108), 8, "V2.003", anchor="rs")

    # Two columns, three rows: the word set with the axis at its extreme,
    # its technical tag beneath
    for i, (word, tag, variant) in enumerate(AXIS_ROWS):
        x = left + (i % 2) * 900
        baseline = 330 + (i // 2) * 300
        put((x, baseline), 22, word, **variant)
        put((x, baseline + 72), 8, tag)

    save_image(render_inkjet(mask, rng), "tiny5-sample5.jpg")


# The same face from headline to native size, in device pixels, each step
# in its own color on the color LCD
RAMP_ROWS = [
    (6, "Lorem ipsum", (255, 60, 60)),
    (4, "Lorem ipsum dolor", (60, 235, 90)),
    (3, "Lorem ipsum dolor sit", (70, 140, 255)),
    (2, "Lorem ipsum dolor sit amet", (255, 200, 60)),
    (1, "Lorem ipsum dolor sit amet, consectetur.", (240, 240, 240)),
]

TFT_BG = (10, 12, 14)
TFT_CHROME = (200, 205, 210)


def build_ramp():
    """A size ramp on a reflective color LCD module, 320x180 pixels: the
    same face from headline pixels down to the native size, each step in
    its own color, labeled in device pixels."""
    grid = (320, 180)
    width = grid[0]
    margin = 10

    chrome = Display(grid)
    chrome.text((margin, 16), 1, "Tiny5 display test")
    chrome.text((width - margin, 16), 1, "V2.003", anchor="rs")
    layers = [(chrome, TFT_CHROME)]

    baseline = 28
    for scale, string, color in RAMP_ROWS:
        d = Display(grid)
        baseline += scale * CAP_PIXELS
        d.text((margin, baseline), scale, string)
        d.text((width - margin, baseline), 1, f"{scale * 6} pt", anchor="rs")
        baseline += 2 * scale + 8
        layers.append((d, color))

    save_image(render_tft(layers, 6, TFT_BG), "tiny5-sample4.jpg")


if __name__ == "__main__":
    build_hero()
    build_charset(False, "tiny5-sample1.jpg")   # 1: character ROM on a VFD
    build_charset(True, "tiny5-sample2.jpg")    # 2: Tiny5 Duo character ROM
    build_terminal()                            # 3: login session on an amber CRT
    build_ramp()                                # 4: size ramp on a color TFT
    build_axes()                                # 5: variation axes, inkjet proof
    build_printout()                            # 6: 9-pin printer self test
