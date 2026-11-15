"""Generate the yt down icon: red rounded square, white play triangle, white download bar.

    uv run --with pillow python assets/make_icons.py

Writes assets/icon-1024.png (macOS .icns is built from it by macos/build-app.sh) and
assets/ytdown.ico (Windows installer and shortcuts).
"""

from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).parent
RED = (229, 31, 38, 255)
WHITE = (255, 255, 255, 255)
SCALE = 4  # draw large, then downsample for smooth edges


def draw(size: int = 1024, margin: int = 100) -> Image.Image:
    s = size * SCALE
    m = margin * SCALE
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((m, m, s - m, s - m), radius=int((s - 2 * m) * 0.225), fill=RED)

    # Play triangle, optically centred a little above the middle.
    cx, cy, h = s * 0.52, s * 0.45, s * 0.32
    d.polygon(
        [(cx - h * 0.45, cy - h / 2), (cx - h * 0.45, cy + h / 2), (cx + h * 0.55, cy)], fill=WHITE
    )

    # Download "tray" bar under the triangle.
    bw, bh, by = s * 0.36, s * 0.045, s * 0.70
    d.rounded_rectangle(
        (s / 2 - bw / 2, by, s / 2 + bw / 2, by + bh), radius=int(bh / 2), fill=WHITE
    )
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    draw().save(HERE / "icon-1024.png")
    # Windows icons look better edge to edge, with a thinner margin.
    draw(256, margin=8).save(
        HERE / "ytdown.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )


if __name__ == "__main__":
    main()
