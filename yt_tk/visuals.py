"""Szenen-Grafiken: SVGs werden von Claude im Skript geschrieben und hier gerendert.

Zusaetzlich erzeugt dieses Modul die festen Serien-Elemente (Badge, Hook-Titel),
damit jede Serie optisch einheitlich bleibt.
"""
import html
import json
import re
import subprocess
from pathlib import Path

from . import config

SCALE = 2  # Szenen in doppelter Aufloesung -> Spielraum fuer Zoom/Kamerafahrt

BADGE_STYLE = {
    "wissen": {"bg": "#FFD400", "fg": "#111111", "font": "Inter Display", "weight": 900},
    "waswaerewenn": {"bg": "#0E2A5C", "fg": "#FFFFFF", "font": "Inter Display", "weight": 800},
    "horror": {"bg": "#7A0000", "fg": "#F2F2F2", "font": "DejaVu Serif", "weight": 700},
}


def validate_svg(svg: str, fmt: str = "horror") -> list:
    """Prueft Claude-SVGs. Externe Bilder/Fonts sind verboten (nur eigene Grafik)."""
    problems = []
    w, h = config.dims(fmt)
    s = svg.strip()
    if not s.startswith("<svg"):
        problems.append("SVG muss mit <svg beginnen")
    if f'viewBox="0 0 {w} {h}"' not in s:
        problems.append(f'viewBox muss "0 0 {w} {h}" sein')
    if re.search(r'(href|src)\s*=\s*["\']\s*(https?:|//|data:image/(png|jpe?g|webp))', s, re.I):
        problems.append("Keine externen oder eingebetteten Fremdbilder erlaubt")
    if re.search(r"@import|url\(\s*['\"]?https?:", s, re.I):
        problems.append("Keine externen Ressourcen (Fonts/CSS) erlaubt")
    if "<script" in s.lower() or "<foreignobject" in s.lower():
        problems.append("Kein <script>/<foreignObject>")
    return problems


def _svg_text_lines(text: str, max_chars: int) -> list:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > max_chars and cur:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


def badge_svg(fmt: str, part_label: str = "") -> str:
    st = BADGE_STYLE[config.style(fmt)]
    W, H = config.dims(fmt)
    label = config.FORMATS[fmt]["badge"] + (f"  ·  {part_label}" if part_label else "")
    label = html.escape(label)
    char_w = 31 if "Serif" in st["font"] else 25  # Serifenschrift laeuft breiter
    w = 60 + int(len(label) * char_w)
    # Hochformat: oben mittig. Querformat: oben links, damit das Bild frei bleibt.
    x, y = ((W - w) // 2, 150) if H > W else (48, 40)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">
  <g transform="translate({x},{y})">
    <rect width="{w}" height="78" rx="39" fill="{st['bg']}" opacity="0.92"/>
    <text x="{w/2}" y="52" text-anchor="middle" font-family="{st['font']}" font-weight="{st['weight']}"
      font-size="38" letter-spacing="3" fill="{st['fg']}">{label}</text>
  </g>
</svg>'''


def hook_svg(fmt: str, hook: str) -> str:
    st = BADGE_STYLE[config.style(fmt)]
    W, H = config.dims(fmt)
    cx = W // 2
    landscape = W > H
    lines = _svg_text_lines(hook.upper() if fmt == "wissen" else hook, 26 if landscape else 16)[:4]
    size = 104 if len(lines) <= 2 else 88
    y0 = (H * 0.42 if landscape else 470) - (len(lines) - 1) * size * 0.3
    stroke = "#000" if fmt != "waswaerewenn" else "#06142e"
    box_h = len(lines) * size * 1.15 + 70
    box_y = y0 - size * 0.95 - 20
    box_w = min(W - 80, max(len(l) for l in lines) * size * 0.62 + 120)
    tspans = "".join(
        f'<tspan x="{cx}" y="{y0 + i * size * 1.15:.0f}">{html.escape(l)}</tspan>' for i, l in enumerate(lines))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">
  <rect x="{cx - box_w / 2:.0f}" y="{box_y:.0f}" width="{box_w:.0f}" height="{box_h:.0f}" rx="36" fill="{st['bg']}" opacity="0.88"/>
  <text text-anchor="middle" font-family="{st['font']}" font-weight="{st['weight']}" font-size="{size}"
    fill="#FFFFFF" stroke="{stroke}" stroke-width="14" paint-order="stroke" stroke-linejoin="round">{tspans}</text>
</svg>'''


def scene_svg(script: dict, sc: dict) -> str:
    """SVG direkt im Skript ("svg") oder als Datei neben script.json ("svg_file")."""
    if "svg_file" in sc:
        return (config.DATA / "content" / script["id"] / sc["svg_file"]).read_text(encoding="utf-8")
    return sc.get("svg", "")


def render(jobs: list, workdir: Path) -> None:
    jf = workdir / "svg_jobs.json"
    jf.write_text(json.dumps(jobs))
    subprocess.run(["node", str(config.ROOT / "tools" / "svg2png.js"), str(jf)], check=True)


def render_scenes(script: dict, workdir: Path) -> dict:
    fmt = script["format"]
    W, H = config.dims(fmt)
    jobs, scene_pngs = [], []
    for i, sc in enumerate(script["scenes"]):
        svg = scene_svg(script, sc)
        probs = validate_svg(svg, fmt)
        if probs:
            raise ValueError(f"Szene {i + 1}: " + "; ".join(probs))
        svg_p = workdir / f"scene_{i:02d}.svg"
        png_p = workdir / f"scene_{i:02d}.png"
        svg_p.write_text(svg, encoding="utf-8")
        jobs.append({"svg": str(svg_p), "png": str(png_p), "width": W * SCALE,
                     "height": H * SCALE, "transparent": False})
        scene_pngs.append(png_p)
    overlays = {}
    for name, svg in (("badge", badge_svg(fmt, script.get("part_label", ""))),
                      ("hook", hook_svg(fmt, script["hook_overlay"]))):
        sp, pp = workdir / f"{name}.svg", workdir / f"{name}.png"
        sp.write_text(svg, encoding="utf-8")
        jobs.append({"svg": str(sp), "png": str(pp), "width": W, "height": H,
                     "transparent": True})
        overlays[name] = pp
    render(jobs, workdir)
    return {"scenes": scene_pngs, **overlays}
