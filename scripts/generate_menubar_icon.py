#!/usr/bin/env python3
"""Build menubar template icons from the galloping-horse source silhouette.

Requires: pip install pillow

Source (prefer first existing):
  assets/menubar-horse-source.png
Output:
  src/mcl_kboard/assets/MenubarIconTemplate{,@2x,@3x}.png
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "mcl_kboard" / "assets"
SOURCE_CANDIDATES = [
    ROOT / "assets" / "menubar-horse-source.png",
]


def load_source() -> Image.Image:
    for path in SOURCE_CANDIDATES:
        if path.is_file():
            return Image.open(path).convert("RGBA")
    raise SystemExit(
        "Missing source image. Place the horse PNG at assets/menubar-horse-source.png"
    )


def to_silhouette(img: Image.Image) -> Image.Image:
    w, h = img.size
    # Drop Qianwen watermark strip at bottom
    img = img.crop((0, 0, w, int(h * 0.90)))
    px = img.load()
    cw, ch = img.size
    for y in range(ch):
        for x in range(cw):
            r, g, b, a = px[x, y]
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            if lum > 200:
                px[x, y] = (0, 0, 0, 0)
            elif lum > 140:
                if y > ch * 0.82 and x > cw * 0.55:
                    px[x, y] = (0, 0, 0, 0)
                else:
                    px[x, y] = (0, 0, 0, int(max(0, min(255, (200 - lum) * 3))))
            else:
                alpha = 255 if lum < 80 else int(255 - (lum - 80) * 1.5)
                px[x, y] = (0, 0, 0, max(0, min(255, alpha)))

    bbox = img.getbbox()
    if not bbox:
        raise SystemExit("No opaque pixels found in source")
    pad = int(max(cw, ch) * 0.02)
    l, t, r, b = bbox
    horse = img.crop((max(0, l - pad), max(0, t - pad), min(cw, r + pad), min(ch, b + pad)))
    hw, hh = horse.size
    side = max(hw, hh)
    margin = int(side * 0.04)
    canvas = side + margin * 2
    square = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    square.paste(horse, ((canvas - hw) // 2, (canvas - hh) // 2), horse)
    return square


def emit(master: Image.Image, size: int, name: str, harden: bool) -> None:
    im = master.resize((size, size), Image.Resampling.LANCZOS)
    p = im.load()
    for y in range(size):
        for x in range(size):
            a = p[x, y][3]
            if harden:
                p[x, y] = (0, 0, 0, 255 if a > 90 else 0)
            else:
                p[x, y] = (0, 0, 0, 0 if a < 25 else a)
    im.save(OUT / name, "PNG")
    print("wrote", OUT / name)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sil = to_silhouette(load_source())
    master = sil.resize((512, 512), Image.Resampling.LANCZOS)
    mp = master.load()
    for y in range(512):
        for x in range(512):
            a = mp[x, y][3]
            mp[x, y] = (0, 0, 0, 0 if a < 20 else a)
    master.save(OUT / "MenubarIconMaster.png", "PNG")

    emit(master, 18, "MenubarIconTemplate.png", True)
    emit(master, 36, "MenubarIconTemplate@2x.png", False)
    emit(master, 54, "MenubarIconTemplate@3x.png", False)

    prev = master.resize((128, 128), Image.Resampling.LANCZOS)
    pp = prev.load()
    for y in range(128):
        for x in range(128):
            a = pp[x, y][3]
            if a:
                pp[x, y] = (28, 118, 108, a)
    prev.save(OUT / "icon-preview.png", "PNG")
    print("wrote", OUT / "icon-preview.png")


if __name__ == "__main__":
    main()
