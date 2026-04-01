from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

SRC_PATH = "documentation/src"
TINY5_PATH = "fonts/variable/Tiny5[BLED,ROND,wght].ttf"
TINY5_DUO_PATH = "fonts/variable/Tiny5Duo[BLED,ROND,wght].ttf"
OUT_PATH = "documentation/img"

SAMPLE_TEXT = """\
The quick brown fox jumps over the lazy dog.

Benjamín pidió una bebida de kiwi y fresa. Noé, sin vergüenza, la más exquisita champaña del menú.

Γκόλφω, βάδιζε μπροστά ξανθή ψυχή!

Съешь ещё этих мягких французских булок, да выпей же чаю."""

JPG_QUALITY = 95


def load_image(filename):
    """Load an image from the source path."""
    return Image.open(f"{SRC_PATH}/{filename}")


def save_image(img, filename):
    """Save the image as JPEG with optimization."""
    img = img.convert("RGB")
    img.save(f"{OUT_PATH}/{filename}", optimize=True, quality=JPG_QUALITY)


def get_font(size, style: str) -> ImageFont.FreeTypeFont:
    """Load and return the Tiny5 font."""
    if style.startswith("Tiny5"):
        style = style[5:].strip()

    if style.startswith("Duo"):
        style = style[3:].strip()
        font_path = TINY5_DUO_PATH
    else:
        font_path = TINY5_PATH

    font = ImageFont.truetype(font=font_path, size=size)

    if style == "LCD":
        font.set_variation_by_axes([340, 0, 0])
    elif style == "CRT":
        font.set_variation_by_axes([280, 80, 64])
    elif style == "Matrix":
        font.set_variation_by_axes([340, 100, 0])

    return font


def draw_presentation_text(img, y, text, size):
    """Draw centered text on the image at the specified position."""
    font = get_font(size, "LCD")
    draw = ImageDraw.Draw(img)

    draw.text(
        xy=(img.width // 2, y),
        text=text,
        fill=(195, 246, 255),
        font=font,
        anchor="mt",
    )


def draw_lcd_text(img, font_name, size, xy, text):
    """Draw text with outer glow for LCD sample.

    Args:
        img: PIL Image object to draw on
        font_name: Name of the font to use
        size: Font size
        xy: Current position for text
        text: Text string to draw
    """
    font = get_font(size, font_name + " LCD")

    text_color = (195, 246, 255)

    glow_color = (
        text_color[0] * 4 // 3,
        text_color[1] * 4 // 3,
        text_color[2] * 4 // 3,
        255,
    )
    blur_radius = 40

    # Step 1: render text
    glow_img = Image.new("RGBA", img.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_img)
    glow_draw.text(xy=xy, text=text, fill=glow_color, font=font, anchor="ms")

    # Step 2: blur mask
    glow_img = glow_img.filter(ImageFilter.GaussianBlur(blur_radius))

    # Step 3: composite glow
    result = ImageChops.add(img, glow_img)
    img.paste(result)

    # Step 4: render text
    draw_text = ImageDraw.Draw(img)
    draw_text.text(xy=xy, text=text, fill=text_color, font=font, anchor="ms")


def draw_crt_text(img, text, xy, size):
    """Draw text with inner glow for CRT sample.

    Args:
        img: PIL Image object to draw on
        text: Text string to draw
        xy: Current position for text
        size: Font size
    """
    font = get_font(size, "CRT")

    # Step 1: render text
    draw_text = ImageDraw.Draw(img)
    draw_text.text(
        xy=xy,
        text=text,
        fill=(150, 240, 255),
        font=font,
        anchor="ls",
    )

    # Step 2: render mask
    mask_img = Image.new("L", img.size, 0)
    glow_draw = ImageDraw.Draw(mask_img)
    glow_draw.text(xy=xy, text=text, fill=255, font=font, anchor="ls")

    # Step 3: shrink mask
    mask_img = mask_img.filter(ImageFilter.MinFilter(5))

    # Step 4: blur mask
    mask_img = mask_img.filter(ImageFilter.GaussianBlur(0.5))

    # Step 5: build glow from mask
    glow_img = Image.new("RGBA", img.size, (255, 255, 255, 255))
    glow_img.putalpha(mask_img)

    # Step 6: composite glow
    img.alpha_composite(glow_img)


def draw_matrix_text(img, text, xy, size):
    """Draw text with solid color for Matrix sample.

    Args:
        img: PIL Image object to draw on
        text: Text string to draw
        xy: Current position for text
        size: Font size
    """
    text_color = (0, 0, 0, 255)

    font = get_font(size, "Matrix")

    # Step 1: render text
    draw = ImageDraw.Draw(img)
    draw.text(xy, text, fill=text_color, font=font, anchor="ls")


def draw_presentation():
    """Generate and save a presentation image with Tiny5 font title and subtitle."""
    img = load_image("presentation-background.png")

    title_font_size = 72 * 8
    subtitle_font_size = 12 * 8

    content_height = title_font_size + subtitle_font_size
    title_top = (img.height - content_height) // 2
    subtitle_top = title_top + title_font_size

    draw_presentation_text(
        img,
        title_top,
        "Tiny5",
        title_font_size,
    )
    draw_presentation_text(
        img,
        subtitle_top,
        "A 5-pixel font from the future",
        subtitle_font_size,
    )

    save_image(img, "tiny5-presentation.jpg")


def draw_specimen(path_in, path_out, name: str):
    """Generate and save a sample image with LCD style."""
    img = load_image(path_in)

    element_size = 16

    font_size = element_size * 8
    line_height = element_size * 9
    content_left = img.width // 2
    content_height = line_height * 5

    cap_height = element_size * 5
    font_ascent = (line_height - cap_height) // 2 + cap_height
    content_top = (img.height - content_height) // 2
    xy = [content_left, content_top + font_ascent]

    draw_lcd_text(img, name, font_size, xy, "A B C D E F G H I J K L M")
    xy[1] += line_height
    draw_lcd_text(img, name, font_size, xy, "N O P Q R S T U V W X Y Z")
    xy[1] += line_height
    draw_lcd_text(img, name, font_size, xy, "a b c d e f g h i j k l m")
    xy[1] += line_height
    draw_lcd_text(img, name, font_size, xy, "n o p q r s t u v w x y z")
    xy[1] += line_height
    draw_lcd_text(img, name, font_size, xy, "0 1 2 3 4 5 6 7 8 9")

    save_image(img, path_out)


def draw_terminal():
    """Generate and save a sample image with CRT style."""
    img = load_image("sample3-background.png")

    element_size = 11

    font_size = element_size * 8
    line_height = element_size * 10
    content_left = element_size * 10
    content_top = element_size * 2

    cap_height = element_size * 5
    font_ascent = (line_height - cap_height) // 2 + cap_height
    xy = [content_left, content_top + font_ascent]

    draw_crt_text(img, "$ info Tiny5", xy, font_size)
    xy[1] += line_height
    draw_crt_text(img, "Variants: Tiny5 + Tiny5 Duo", xy, font_size)
    xy[1] += line_height
    draw_crt_text(img, "Type: Variable", xy, font_size)
    xy[1] += line_height
    draw_crt_text(img, "Axes: weight, roundness, bleed", xy, font_size)
    xy[1] += line_height
    draw_crt_text(img, "Scripts: Latin + Greek + Cyrillic", xy, font_size)
    xy[1] += line_height
    draw_crt_text(img, "Languages: 897", xy, font_size)
    xy[1] += line_height
    draw_crt_text(img, "Glyphs: 1655", xy, font_size)
    xy[1] += line_height
    draw_crt_text(img, "Typographic features: kerning", xy, font_size)
    xy[1] += line_height
    draw_crt_text(img, "$", xy, font_size)

    save_image(img, "tiny5-sample3.jpg")


def draw_printout():
    """Generate and save a sample image with Matrix style."""
    img = load_image("sample4-background.png")

    # Text parameters
    element_size = 9

    font_size = element_size * 8
    line_height = element_size * 18
    content_left = line_height
    content_top = 25

    cap_height = element_size * 5
    font_ascent = (line_height - cap_height) // 2 + cap_height

    # Green bars
    top_start = content_top + 3 * element_size
    left_margin = content_left
    hole_radius = 2 * element_size

    mask = Image.new("RGBA", img.size, (255, 255, 255))
    mask_draw = ImageDraw.Draw(mask)
    for i in range(3):
        y = top_start + i * 2 * line_height
        rect = [(left_margin, y), (img.width, y + line_height)]
        mask_draw.rectangle(xy=rect, fill=(215, 237, 231))

    # Paper cut
    rect = [(left_margin - 1, 0), (left_margin + 1, img.height)]
    mask_draw.rectangle(xy=rect, fill=(228, 228, 228))

    # Draw holes
    for i in range(6):
        y = top_start + i * line_height
        xy = (left_margin // 2, line_height // 2 + y)
        mask_draw.circle(xy=xy, radius=hole_radius, fill=(0, 0, 0))

    img = ImageChops.multiply(img, mask)

    # Draw text
    xy = [content_left, content_top + font_ascent]

    draw_matrix_text(img, "The five boxing wizards jump quickly.", xy, font_size)
    xy[1] += line_height
    draw_matrix_text(
        img, "Jovencillo emponzoñado de whisky: ¡qué figurota exhibe!", xy, font_size
    )
    xy[1] += line_height
    draw_matrix_text(img, "Zombif parvînt jusqu'à deux whisky-glace.", xy, font_size)
    xy[1] += line_height
    draw_matrix_text(
        img, "Vejo galã sexy pôr quinze kiwis à força em baú achatado.", xy, font_size
    )
    xy[1] += line_height
    draw_matrix_text(
        img, "Эх, чужак, общий съём цен шляп (юфть) – вдрызг!", xy, font_size
    )
    xy[1] += line_height
    draw_matrix_text(img, "Γκόλφω, βάδιζε μπροστά ξανθή ψυχή!", xy, font_size)

    save_image(img, "tiny5-sample4.jpg")


if __name__ == "__main__":
    draw_presentation()
    draw_specimen("sample1-background.png", "tiny5-sample1.jpg", "Tiny5")
    draw_specimen("sample2-background.png", "tiny5-sample2.jpg", "Tiny5 Duo")
    draw_terminal()
    draw_printout()
