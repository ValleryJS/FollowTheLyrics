"""Generate the fixed-width ASCII atlas for the ReShade shader."""

from pathlib import Path

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont


def generate(target):
    atlas = Image.new("RGBA", (1024, 384), (0, 0, 0, 0))
    canvas = ImageDraw.Draw(atlas)
    candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "C:/Windows/Fonts/consolab.ttf",
        "C:/Windows/Fonts/consola.ttf",
    )
    font_path = next((p for p in candidates if Path(p).exists()), None)
    font = (
        ImageFont.truetype(font_path, 47)
        if font_path
        else ImageFont.load_default()
    )
    for code in range(32, 128):
        cell = code - 32
        x, y = (cell % 16) * 64, (cell // 16) * 64
        char = chr(code)
        box = canvas.textbbox((0, 0), char, font=font)
        width, height = box[2] - box[0], box[3] - box[1]
        canvas.text(
            (x + (64 - width) / 2 - box[0], y + (64 - height) / 2 - box[1]),
            char,
            font=font,
            fill=(255, 255, 255, 255),
        )
    atlas.save(target)


if __name__ == "__main__":
    generate(
        Path(__file__).resolve().parents[1]
        / "integrations/fivem-reshade/FTL_FontAtlas.png"
    )
