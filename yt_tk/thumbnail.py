"""Vorschaubild (1280x720, JPEG unter 2 MB) fuer Zusammenschnitt-Langvideos, ohne Claude und ohne Kosten.

    python3 -m yt_tk.thumbnail --all          # alle L00x nach <Daten>/thumbs/L00x.jpg
    python3 -m yt_tk.thumbnail --id L001

Aufbau: grosse Zahl links, Thema rechts in Weiss, Fragezeile auf gelbem Balken. Nur eigene Grafik, keine fremden Bilder.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import compile_long, config

W, H = 1280, 720
BG_TOP, BG_BOTTOM, YELLOW, WHITE, INK = (16, 24, 32), (28, 44, 66), (255, 210, 63), (255, 255, 255), (16, 24, 32)
PATHS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/opentype/inter/Inter-Bold.otf"]


def _font(size: int) -> ImageFont.FreeTypeFont:
    p = next((x for x in PATHS if Path(x).exists()), None)
    if not p:
        raise RuntimeError("Keine Schrift gefunden")
    return ImageFont.truetype(p, size)


def _fit(draw: ImageDraw.ImageDraw, text: str, max_w: int, start: int, min_size: int = 40):
    size = start
    while size > min_size:
        f = _font(size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return _font(min_size)


def make(cfg: dict, dst: Path, n: int = 10) -> Path:
    img = Image.new("RGB", (W, H), BG_TOP)
    d = ImageDraw.Draw(img)
    for y in range(H):  # senkrechter Verlauf
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3)))
    d.rectangle([0, 0, 24, H], fill=YELLOW)
    big = _font(380)
    d.text((70, 90), str(n), font=big, fill=YELLOW)
    nw = int(d.textlength(str(n), font=big))
    x = 70 + nw + 50
    lines = cfg["intro"].format(n=n).split("\n")
    head = lines[0].split(" ", 1)[-1] if lines[0].split(" ", 1)[0].isdigit() else lines[0]  # ohne Zahl
    sub = lines[1] if len(lines) > 1 else ""
    pill = (sub[:1].upper() + sub[1:]) if sub.endswith("?") else "Kennst du alle?"  # eine Frage nie doppelt zeigen
    sub = "" if sub.endswith("?") else sub
    fh = _font(92)
    words, rows, cur = head.split(), [], ""
    for w in words:  # Titel auf bis zu 3 Zeilen umbrechen, damit er gross bleibt
        t = (cur + " " + w).strip()
        if d.textlength(t, font=fh) <= W - x - 40 or not cur:
            cur = t
        else:
            rows.append(cur)
            cur = w
    rows.append(cur)
    y = 120
    for r in rows[:3]:
        d.text((x, y), r, font=_fit(d, r, W - x - 40, 92, 48), fill=WHITE)
        y += 108
    if sub:
        d.text((x, y + 10), sub, font=_fit(d, sub, W - x - 40, 52, 30), fill=(205, 215, 230))
    fq = _fit(d, pill, W - x - 110, 64, 40)
    qw = int(d.textlength(pill, font=fq))
    d.rounded_rectangle([x, H - 190, x + qw + 70, H - 90], radius=18, fill=YELLOW)
    d.text((x + 35, H - 178), pill, font=fq, fill=INK)
    dst.parent.mkdir(parents=True, exist_ok=True)
    for quality in (92, 85, 75):
        img.save(dst, "JPEG", quality=quality)
        if dst.stat().st_size < 1_900_000:
            break
    return dst


def main(argv: list) -> int:
    ids = list(compile_long.LONGS) if "--all" in argv else [argv[argv.index("--id") + 1]] if "--id" in argv else []
    if not ids:
        print(__doc__)
        return 2
    for i in ids:
        out = make(compile_long.LONGS[i], config.DATA / "thumbs" / f"{i}.jpg", len(compile_long.LONGS[i]["parts"]))
        print(f"{i}: {out} ({out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
