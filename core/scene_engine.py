from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _font(size, bold=False):
    candidates = []

    if bold:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "DejaVuSans-Bold.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "DejaVuSans.ttf",
        ]

    for path in candidates:
        try:
            return ImageFont.truetype(
                path,
                size,
            )
        except Exception:
            pass

    return ImageFont.load_default()


def create_scene_visual(
    title,
    text,
    output_file,
    width=1280,
    height=720,
):
    output_file = Path(output_file)

    image = Image.new(
        "RGB",
        (width, height),
        (10, 12, 20),
    )

    draw = ImageDraw.Draw(image)

    # Cinematic background gradient.
    for y in range(height):
        ratio = y / height

        r = int(10 + 25 * ratio)
        g = int(12 + 20 * ratio)
        b = int(20 + 45 * ratio)

        draw.line(
            (0, y, width, y),
            fill=(r, g, b),
        )

    title_font = _font(
        48,
        bold=True,
    )

    body_font = _font(
        31,
        bold=False,
    )

    draw.rectangle(
        (
            65,
            65,
            width - 65,
            height - 65,
        ),
        outline=(190, 190, 200),
        width=2,
    )

    draw.text(
        (105, 105),
        str(title)[:70],
        font=title_font,
        fill=(245, 245, 245),
    )

    words = str(text).split()

    lines = []
    current = ""

    for word in words:

        candidate = (
            f"{current} {word}"
            .strip()
        )

        if len(candidate) > 58:

            if current:
                lines.append(current)

            current = word

        else:
            current = candidate

    if current:
        lines.append(current)

    y = 210

    for line in lines[:10]:

        draw.text(
            (105, y),
            line,
            font=body_font,
            fill=(225, 225, 230),
        )

        y += 47

    image.save(
        output_file,
        quality=95,
    )

    return output_file
