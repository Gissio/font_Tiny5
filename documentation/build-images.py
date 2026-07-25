# This script generates sample images for the Tiny5 font using the Pillow library.

# Install the required dependencies before running this script:
#   sudo apt update
#   sudo apt install libfreetype6-dev libharfbuzz-dev libfribidi-dev libraqm-dev meson pkg-config

import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT_PATH = Path(__file__).resolve().parent.parent
SRC_PATH = ROOT_PATH / "documentation/src"
OUT_PATH = ROOT_PATH / "documentation/img"

TINY5_PATH = ROOT_PATH / "fonts/variable/Tiny5[BLED,JITT,ROND,wdth,wght].ttf"
TINY5_DUO_PATH = ROOT_PATH / "fonts/variable/Tiny5Duo[BLED,JITT,ROND,wdth,wght].ttf"

# Variation axes: weight, width, roundness, bleed, jitter
STYLE_AXES = {
    "LCD": [340, 100, 0, 0, 0],
    "CRT": [280, 100, 80, 64, 0],
    "Matrix": [340, 100, 100, 0, 50],
}

# Tiny5 draws one font pixel per 8 font units, and is 5 font pixels tall
FONT_PIXEL_SIZE = 8
CAP_PIXELS = 5

# Imperfections of the dot matrix printer
PRINT_SEED = 5              # Seed of the imperfections, so that builds stay reproducible
INK_SPREAD = (1.0, 0.7)     # Ink soaking into the paper, in pixels, smeared by the head travel
INK_SKEW = 0.15             # Paper feed misalignment, in degrees
INK_OFFSET = 2              # Print head misalignment between passes, in pixels
INK_PATCH_SIZE = 24         # Size of the patches the ribbon inks unevenly, in font pixels
INK_PATCH_LEVEL = 165       # Ink level of the faintest patch, of 255
WEAK_PINS = 2               # Print head pins that strike faintly

JPG_QUALITY = 95


def load_image(filename):
    """Load a background image from the source path."""
    return Image.open(SRC_PATH / filename).convert("RGB")


def save_image(img, filename):
    """Save the image as an optimized JPEG."""
    img.save(OUT_PATH / filename, optimize=True, quality=JPG_QUALITY)


def get_font(font_size, style):
    """Load the Tiny5 font for a style, e.g. "LCD" or "LCD Duo".

    The style is a key of STYLE_AXES, plus an optional "Duo" to select the
    Tiny5 Duo variant. An unknown style raises, so a typo cannot silently
    fall back to the default variation.
    """
    names = style.split()
    style_name = next(name for name in names if name != "Duo")
    font_path = TINY5_DUO_PATH if "Duo" in names else TINY5_PATH

    font = ImageFont.truetype(font=font_path, size=font_size)
    font.set_variation_by_axes(STYLE_AXES[style_name])

    return font


def get_baseline(line_height, cap_height):
    """Return the baseline offset that centers capital letters within a line."""
    return (line_height - cap_height) // 2 + cap_height


def get_noise_image(size, rng):
    """Build an image of uniform random noise."""
    return Image.frombytes("L", size, rng.randbytes(size[0] * size[1]))


def get_blotch_image(size, blotch_size, min_level, rng):
    """Build a smoothly varying random field, from min_level to full level."""
    noise_size = (max(size[0] // blotch_size, 1), max(size[1] // blotch_size, 1))
    blotch_img = get_noise_image(noise_size, rng).resize(size, Image.BICUBIC)

    return blotch_img.point(lambda level: min_level + level * (255 - min_level) // 255)


def get_pin_image(size, element_size, glyph_top, rows, rng):
    """Build the strength of the print head pins, one band per element row of a text line.

    A worn pin strikes faintly, and so prints the same faint row of dots on every line.
    """
    levels = [255] * rows
    for pin in rng.sample(range(CAP_PIXELS + 1), WEAK_PINS):
        levels[pin] = rng.randrange(150, 230)

    column_img = Image.new("L", (1, size[1]))
    column_img.putdata([levels[((y - glyph_top) // element_size) % rows] for y in range(size[1])])

    return column_img.resize(size, Image.NEAREST)


def colorize(mask_img, color, background_color=(0, 0, 0)):
    """Build an image that fades from the background color to the color over the mask."""
    return Image.composite(Image.new("RGB", mask_img.size, color),
                           Image.new("RGB", mask_img.size, background_color),
                           mask_img)


def draw_text(img, font_name, font_size, xy, anchor, text, fill_color, glow_color=None, glow_radius=0, glow_shrink=1, glow_blur=0):
    """Draw text on the image, optionally with an outer glow, an inner glow, or both.

    Args:
        img: PIL Image object to draw on
        font_name: Name of the font to use
        font_size: Font size
        xy: Current position for text
        anchor: Text anchor
        text: Text string to draw
        fill_color: Color of the glyph core
        glow_color: Color of the glow, None to use the fill color
        glow_radius: Outer glow radius, 0 to disable the outer glow
        glow_shrink: Inner glow shrink window, rounded up to an odd size, 1 to disable shrinking
        glow_blur: Inner glow blur radius, 0 to disable blurring
    """
    font = get_font(font_size, font_name)

    if glow_color is None:
        glow_color = fill_color

    # Render the glyphs as a mask
    mask_img = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask_img).text(xy=xy, text=text, fill=255, font=font, anchor=anchor)

    # Outer glow: blur the mask only, so the glow color is not diluted towards black,
    # then screen it onto the image, so the glow only adds light
    if glow_radius > 0:
        glow_img = colorize(mask_img.filter(ImageFilter.GaussianBlur(glow_radius)), glow_color)
        img.paste(ImageChops.screen(img, glow_img), (0, 0))

    # Inner glow: shrink and blur the mask into a core, clipped to the glyphs so the blur
    # does not spill outside, then fade the fill color into the glow color at the rim
    if glow_shrink > 1 or glow_blur > 0:
        core_img = mask_img.filter(ImageFilter.MinFilter(glow_shrink + 1 - glow_shrink % 2))
        core_img = core_img.filter(ImageFilter.GaussianBlur(glow_blur))
        core_img = ImageChops.darker(core_img, mask_img)

        text_img = colorize(core_img, fill_color, glow_color)
    else:
        text_img = Image.new("RGB", img.size, fill_color)

    # Composite the glyphs
    text_img.putalpha(mask_img)
    img.paste(text_img, (0, 0), text_img)


def draw_text_lines(img, font_name, font_size, xy, line_height, anchor, lines, fill_color, **glow_args):
    """Draw consecutive lines of text, advancing by the line height.

    The glow arguments are passed on to draw_text().
    """
    x, y = xy
    for line in lines:
        draw_text(img, font_name, font_size, (x, y), anchor, line, fill_color, **glow_args)
        y += line_height


def draw_ink_lines(img, font_name, font_size, xy, line_height, lines, fill_color, rng):
    """Print consecutive lines of text the way a dot matrix printer would.

    The print head strikes an inked ribbon against the paper, so the dots come out
    uneven: the ribbon inks in patches, worn pins strike faintly, the head lands
    slightly off between passes, and the paper feeds in a little askew.
    """
    font = get_font(font_size, font_name)
    element_size = font_size // FONT_PIXEL_SIZE

    # Strike the lines, alternating the direction of the print head
    mask_img = Image.new("L", img.size, 0)
    mask_draw = ImageDraw.Draw(mask_img)

    x, y = xy
    for index, line in enumerate(lines):
        mask_draw.text(xy=(x + INK_OFFSET * (index % 2), y), text=line, fill=255, font=font, anchor="ls")
        y += line_height

    # Let the ink soak into the paper, and feed the paper in askew
    mask_img = mask_img.filter(ImageFilter.GaussianBlur(INK_SPREAD))
    mask_img = mask_img.rotate(INK_SKEW, resample=Image.BILINEAR)

    # Ink from a patchy ribbon, struck by a worn print head
    glyph_top = xy[1] - element_size * CAP_PIXELS
    mask_img = ImageChops.multiply(mask_img, get_blotch_image(img.size, INK_PATCH_SIZE * element_size, INK_PATCH_LEVEL, rng))
    mask_img = ImageChops.multiply(mask_img, get_pin_image(img.size, element_size, glyph_top, line_height // element_size, rng))

    ink_img = Image.new("RGB", img.size, fill_color)
    ink_img.putalpha(mask_img)
    img.paste(ink_img, (0, 0), ink_img)


def draw_presentation(path_in, path_out):
    """Generate and save a presentation image with Tiny5 font title and subtitle."""
    img = load_image(path_in)

    title_size = 72 * FONT_PIXEL_SIZE
    subtitle_size = 12 * FONT_PIXEL_SIZE

    content_left = img.width // 2
    content_top = (img.height - (title_size + subtitle_size)) // 2

    fill_color = (195, 246, 255)
    glow_color = (0, 186, 219)
    glow_radius = 75

    draw_text(img, "LCD", title_size, (content_left, content_top), "mt",
              "Tiny5", fill_color, glow_color, glow_radius)
    draw_text(img, "LCD", subtitle_size, (content_left, content_top + title_size), "mt",
              "A 5-pixel font from the future", fill_color, glow_color, glow_radius)

    save_image(img, path_out)


def draw_specimen(path_in, path_out, font_name, element_size=16):
    """Generate and save a specimen image with LCD style.

    The wider Tiny5 Duo needs a smaller element size to keep its margins.
    """
    img = load_image(path_in)

    lines = [
        "A B C D E F G H I J K L M",
        "N O P Q R S T U V W X Y Z",
        "a b c d e f g h i j k l m",
        "n o p q r s t u v w x y z",
        "0 1 2 3 4 5 6 7 8 9",
    ]

    font_size = element_size * FONT_PIXEL_SIZE
    cap_height = element_size * CAP_PIXELS
    line_height = element_size * 9

    content_left = img.width // 2
    content_top = (img.height - line_height * len(lines)) // 2
    xy = (content_left, content_top + get_baseline(line_height, cap_height))

    fill_color = (195, 246, 255)
    glow_color = (132, 236, 255)
    glow_radius = 50

    draw_text_lines(img, font_name, font_size, xy, line_height, "ms", lines, fill_color,
                    glow_color=glow_color, glow_radius=glow_radius)

    save_image(img, path_out)


def draw_terminal(path_in, path_out):
    """Generate and save a sample image with CRT style."""
    img = load_image(path_in)

    lines = [
        "$ info Tiny5",
        "Variants: Tiny5 + Tiny5 Duo",
        "Type: Variable",
        "Axes: weight, width, slant, roundness, bleed, jitter",
        "Scripts: Latin + Greek + Cyrillic",
        "Languages: 897",
        "Glyphs: 1655",
        "Typographic features: kerning",
        "$",
    ]

    element_size = 11

    font_size = element_size * FONT_PIXEL_SIZE
    cap_height = element_size * CAP_PIXELS
    line_height = element_size * 10

    content_left = element_size * 8
    content_top = element_size * 2
    xy = (content_left, content_top + get_baseline(line_height, cap_height))

    fill_color = (234, 255, 253)
    glow_color = (192, 239, 226)
    glow_shrink = 5
    glow_blur = 0.5

    draw_text_lines(img, "CRT", font_size, xy, line_height, "ls", lines, fill_color,
                    glow_color=glow_color, glow_shrink=glow_shrink, glow_blur=glow_blur)

    save_image(img, path_out)


def draw_paper(img, content_left, content_top, line_height, element_size, rng):
    """Multiply continuous form paper onto the image: green bars, paper cut, holes and grain."""
    paper_img = Image.new("RGB", img.size, (255, 255, 255))
    paper_draw = ImageDraw.Draw(paper_img)

    bar_top = content_top + 3 * element_size
    hole_radius = 2 * element_size

    # Green bars
    for i in range(3):
        y = bar_top + i * 2 * line_height
        rect = [(content_left, y), (img.width, y + line_height)]
        paper_draw.rectangle(xy=rect, fill=(215, 237, 231))

    # Paper cut, creased and perforated
    rect = [(content_left - 1, 0), (content_left + 1, img.height)]
    paper_draw.rectangle(xy=rect, fill=(228, 228, 228))
    for y in range(0, img.height, 2 * element_size):
        rect = [(content_left - 1, y), (content_left + 1, y + element_size)]
        paper_draw.rectangle(xy=rect, fill=(188, 188, 188))

    # Holes, punched through the paper
    for i in range(6):
        y = bar_top + i * line_height
        xy = (content_left // 2, line_height // 2 + y)
        paper_draw.circle(xy=xy, radius=hole_radius + 2, fill=(206, 206, 206))
        paper_draw.circle(xy=xy, radius=hole_radius, fill=(26, 24, 28))

    # Paper grain
    grain_img = get_noise_image(img.size, rng).point(lambda level: 248 + level * 7 // 255)
    paper_img = ImageChops.multiply(paper_img, grain_img.convert("RGB"))

    return ImageChops.multiply(img, paper_img)


def draw_printout(path_in, path_out):
    """Generate and save a sample image with Matrix style."""
    img = load_image(path_in)
    rng = random.Random(PRINT_SEED)

    lines = [
        "The five boxing wizards jump quickly.",
        "Jovencillo emponzoñado de whisky: ¡qué figurota exhibe!",
        "Zombif parvînt jusqu'à deux whisky-glace.",
        "Vejo galã sexy pôr quinze kiwis à força em baú achatado.",
        "Эх, чужак, общий съём цен шляп (юфть) – вдрызг!",
        "Γκόλφω, βάδιζε μπροστά ξανθή ψυχή!",
    ]

    element_size = 9

    font_size = element_size * FONT_PIXEL_SIZE
    cap_height = element_size * CAP_PIXELS
    line_height = element_size * 18

    content_left = line_height
    content_top = 25
    xy = (content_left, content_top + get_baseline(line_height, cap_height))

    fill_color = (38, 35, 42)

    img = draw_paper(img, content_left, content_top, line_height, element_size, rng)

    draw_ink_lines(img, "Matrix", font_size, xy, line_height, lines, fill_color, rng)

    save_image(img, path_out)


if __name__ == "__main__":
    draw_presentation("presentation-background.png", "tiny5-presentation.jpg")
    draw_specimen("sample1-background.png", "tiny5-sample1.jpg", "LCD")
    draw_specimen("sample2-background.png", "tiny5-sample2.jpg", "LCD Duo", 14)
    draw_terminal("sample3-background.png", "tiny5-sample3.jpg")
    draw_printout("sample4-background.png", "tiny5-sample4.jpg")
