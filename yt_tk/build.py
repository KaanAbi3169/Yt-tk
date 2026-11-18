"""Baut ein Video aus content/<id>/script.json.

    python -m yt_tk.build <ID>            # komplett: Stimme -> Grafik -> Schnitt -> QA
    python -m yt_tk.build <ID> --check    # nur Skript pruefen (kostet nichts)
"""
import hashlib
import json
import re
import shutil
import sys

from . import config, qa, render, subtitles, tts, visuals

WORDS_PER_SEC = 2.55  # Schaetzung fuer deutsches Sprechtempo


def load(vid: str) -> dict:
    return json.loads((config.DATA / "content" / vid / "script.json").read_text(encoding="utf-8"))


REQUIRED = ["id", "format", "topic", "hook_type", "hook_overlay", "scenes"]


def required(fmt: str) -> list:
    req = list(REQUIRED)
    for pf in config.platforms(fmt):
        req += [f"title_{pf}", f"text_{pf}"]
    return req


def check_script(s: dict) -> list:
    if s.get("format") not in config.FORMATS:
        return [f"Unbekanntes Format {s.get('format')}"]
    p = [f"Feld fehlt: {k}" for k in required(s["format"]) if k not in s]
    if p:
        return p
    f = config.FORMATS[s["format"]]
    lo, hi = f.get("min_scenes", 3), f.get("max_scenes", 14)
    if not lo <= len(s["scenes"]) <= hi:
        p.append(f"{lo}-{hi} Szenen erforderlich")
    if f.get("chapters"):
        names = [sc["chapter"] for sc in s["scenes"] if sc.get("chapter")]
        if not s["scenes"][0].get("chapter"):
            p.append("Szene 1 braucht ein \"chapter\" (YouTube-Kapitel beginnen bei 0:00)")
        if len(names) < 3:
            p.append("Mindestens 3 Kapitel (\"chapter\" an der ersten Szene jedes Kapitels)")
        if "{KAPITEL}" not in s.get("text_youtube", ""):
            p.append("text_youtube braucht den Platzhalter {KAPITEL}")
        if "#shorts" in (s.get("title_youtube", "") + s.get("text_youtube", "")).lower():
            p.append("Langes Video: kein #shorts in Titel/Text")
    for i, sc in enumerate(s["scenes"]):
        if not sc.get("text", "").strip():
            p.append(f"Szene {i + 1}: kein Text")
        if sc.get("motion", "zoom_in") not in render.MOTIONS:
            p.append(f"Szene {i + 1}: Bewegung muss eine von {render.MOTIONS} sein")
        try:
            svg = visuals.scene_svg(s, sc)
        except FileNotFoundError as e:
            p.append(f"Szene {i + 1}: SVG-Datei fehlt ({e.filename})")
            continue
        p += [f"Szene {i + 1}: {x}" for x in visuals.validate_svg(svg, s["format"])]
    words = len(full_text(s).split())
    est = words / f.get("wps", WORDS_PER_SEC) + config.TAIL
    if not (f["min_s"] - 3 <= est <= f["max_s"] + 2):
        p.append(f"Geschaetzte Laenge {est:.0f}s ({words} Woerter) - Ziel {f['min_s']}-{f['max_s']}s")
    first = re.split(r"(?<=[.!?\u2026])\s", full_text(s).strip(), maxsplit=1)[0]
    if len(first.split()) > 12:  # V-011: Hook in den ersten Sekunden
        p.append(f"Hook zu lang: {len(first.split())} Woerter im ersten Satz (max. 12). Kern der Aussage nach vorn.")
    if len(s.get("title_tiktok", "")) > 90:
        p.append("TikTok-Titel zu lang (max 90)")
    if len(s.get("title_youtube", "")) > 100:
        p.append("YouTube-Titel zu lang (max 100)")
    tags = [w for w in (s.get("text_tiktok", "") + " " + s.get("text_youtube", "")).split() if w.startswith("#")]
    if not tags:
        p.append("Keine Hashtags")
    return p


def full_text(s: dict) -> str:
    return " ".join(sc["text"].strip() for sc in s["scenes"])


def scene_timing(s: dict, tts_res: dict) -> dict:
    chars = tts_res["chars"]["characters"]
    starts_t = tts_res["chars"]["character_start_times_seconds"]
    text = full_text(s)
    words = tts_res["words"]
    total = words[-1]["end"] + config.TAIL
    offsets, pos = [], 0
    for sc in s["scenes"]:
        offsets.append(pos)
        pos += len(sc["text"].strip()) + 1
    starts = []
    if "".join(chars) == text:
        for i, off in enumerate(offsets):
            starts.append(0.0 if i == 0 else max(0.0, starts_t[off] - 0.08))
    else:  # Fallback: proportional ueber Zeichenposition
        n = len(text)
        for i, off in enumerate(offsets):
            starts.append(0.0 if i == 0 else total * off / n)
    # Mindestlaenge pro Szene, damit Uebergaenge sauber bleiben
    for i in range(1, len(starts)):
        starts[i] = max(starts[i], starts[i - 1] + config.XFADE + 0.4)
    return {"scene_starts": starts, "total": total}


def _mmss(t: float) -> str:
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"


def chapters(s: dict, timing: dict) -> list:
    """YouTube-Kapitel aus den Szenen mit "chapter" (erste Marke immer 0:00)."""
    out = []
    for sc, st in zip(s["scenes"], timing["scene_starts"]):
        if sc.get("chapter"):
            out.append([_mmss(0 if not out else st), sc["chapter"]])
    return out


def build(vid: str) -> dict:
    s = load(vid)
    probs = check_script(s)
    if probs:
        raise ValueError("Skript ungueltig:\n- " + "\n- ".join(probs))
    fmt = s["format"]
    work = config.WORK / vid
    work.mkdir(parents=True, exist_ok=True)
    cdir = config.DATA / "content" / vid

    # Stimme (gecacht per Text-Hash -> keine doppelten Credits bei Neu-Rendern)
    text = full_text(s)
    h = hashlib.sha256((fmt + text).encode()).hexdigest()[:16]
    voice, tcache = cdir / "voice.mp3", cdir / "voice.json"
    if not (voice.exists() and tcache.exists() and json.loads(tcache.read_text()).get("hash") == h):
        res = tts.synthesize(text, fmt, voice)
        res["hash"] = h
        tcache.write_text(json.dumps(res))
    res = json.loads(tcache.read_text())

    timing = scene_timing(s, res)
    assets = visuals.render_scenes(s, work)
    ass = cdir / "subtitles.ass"
    subtitles.build_ass(res["words"], fmt, timing["total"], ass)
    out = work / f"{vid}.mp4"
    render.assemble(s, assets, timing, voice, ass, out, work)
    report = qa.check(out, fmt, res["words"], ass)
    report["timing"] = timing
    if config.FORMATS[fmt].get("chapters"):
        report["chapters"] = chapters(s, timing)
    (cdir / "build.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    if report["ok"]:
        vdir = config.DATA / "videos"
        vdir.mkdir(parents=True, exist_ok=True)
        shutil.copy(out, vdir / f"{vid}.mp4")
        # Vorschaubild fuer den Bericht
        import subprocess
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "3", "-i", str(out), "-frames:v", "1",
                        "-vf", "scale=360:-1", str(cdir / "preview.jpg")])
    else:
        report["hint"] = "QA nicht bestanden - Video wurde nicht in videos/ kopiert."
    return report


def main(argv):
    if config.paused():
        print("PAUSE aktiv - nichts zu tun.")
        return 0
    vid = argv[1]
    if "--check" in argv:
        probs = check_script(load(vid))
        print("OK" if not probs else "\n".join(probs))
        return 0 if not probs else 1
    rep = build(vid)
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    return 0 if rep["ok"] else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
