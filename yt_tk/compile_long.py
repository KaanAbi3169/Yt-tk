"""Zusammenschnitt-Langvideo (V-023): zehn Vorrats-Shorts werden zu einem 16:9-Video mit Titelkarte und Kapiteln.

    python -m yt_tk.compile_long            # baut L001 (nur wenn es noch nicht im Inventar ist)
    python -m yt_tk.compile_long --dry      # baut, schreibt aber nichts ins Inventar

Ablauf: Drive-Dateien laden -> je Kurzvideo auf 1280x720 (scharfer Hochkant-Streifen vor unscharfem Hintergrund, Trick-Nummer
als Einblendung) -> Titelkarte -> zusammenfuegen -> Dauer, Dateigroesse und Kapitel pruefen -> videos/L001.mp4 und Inventar.
Die Teile bekommen den Status 'zusammenschnitt', damit sie nicht noch einmal als Short erscheinen (kein Video zweimal)."""
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from . import config, inventory, transcribe

VID = "L001"
TITLE = "10 Haushaltstricks, die wirklich funktionieren: Kennst du alle?"
PARTS = [("D082", "Mikrowelle ohne Schrubben"), ("D081", "Abfluss frei bekommen"), ("D065", "Backofen mit Natron reinigen"),
         ("D061", "Fenster ohne Streifen"), ("D073", "Schimmel in der Dusche vorbeugen"), ("D074", "Küchenschwamm frisch halten"),
         ("D084", "Sportshirt ohne Geruch"), ("D062", "Flecken richtig behandeln"), ("D083", "Staub wirklich loswerden"),
         ("D025", "Wasserkocher entkalken")]
W, H, INTRO_S = 1280, 720, 3
MAX_MB, MIN_S, MAX_S = 95, 420, 720
FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/opentype/inter/Inter-Bold.otf"]
ENC = ["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"]


def log(msg: str) -> None:
    print(f"[{datetime.now(inventory.TZ):%H:%M:%S}] {msg}", flush=True)


def font() -> str:
    f = next((p for p in FONTS if Path(p).exists()), None)
    if not f:
        raise RuntimeError("Keine Schrift gefunden")
    return f


def run(cmd: list) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg: " + r.stderr[-500:])


def encode_clip(src: Path, dst: Path, label: str, crf: int, tmp: Path) -> None:
    txt = tmp / (dst.stem + ".txt")
    txt.write_text(label, encoding="utf-8")
    vf = (f"[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=20:5[bg];"
          f"[b]scale=-2:{H}[fg];[bg][fg]overlay=(W-w)/2:0,"
          f"drawtext=fontfile={font()}:textfile={txt}:x=40:y=40:fontsize=42:fontcolor=white:box=1:boxcolor=black@0.55:boxborderw=14:"
          f"enable='lt(t,4)'[v]")
    run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-filter_complex", vf, "-map", "[v]", "-map", "0:a:0", "-crf", str(crf), *ENC, str(dst)])


def intro_card(dst: Path, crf: int, tmp: Path) -> None:
    txt = tmp / "intro.txt"
    txt.write_text("10 Haushaltstricks\ndie wirklich funktionieren", encoding="utf-8")
    run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=0x101820:s={W}x{H}:d={INTRO_S}", "-f", "lavfi",
         "-i", f"anullsrc=r=44100:cl=stereo", "-t", str(INTRO_S),
         "-vf", f"drawtext=fontfile={font()}:textfile={txt}:x=(w-text_w)/2:y=(h-text_h)/2:fontsize=64:fontcolor=white:line_spacing=18",
         "-crf", str(crf), *ENC, str(dst)])


def stamp(sec: float) -> str:
    s = int(round(sec))
    return f"{s // 60}:{s % 60:02d}"


def description(starts: list) -> str:
    lines = ["Zehn Haushaltstricks in einem Video: vom Abfluss bis zum Wasserkocher. Mit den Kapiteln springst du direkt zu deinem Problem.",
             "", "KAPITEL", f"{stamp(0)} Start"]
    lines += [f"{stamp(t)} {i}. {name}" for i, ((_, name), t) in enumerate(zip(PARTS, starts), 1)]
    lines += ["", "Welchen Trick kanntest du noch nicht? Schreib es in die Kommentare.", "",
              "Stimme und Grafiken mit KI erstellt. Zusammenschnitt aus unseren Kurzvideos.", "", "#haushalt #tricks #putzen #wissen"]
    return "\n".join(lines)


def build(crf: int, tmp: Path, local: str = "") -> tuple:
    clips, starts, t = [], [], float(INTRO_S)
    intro = tmp / "c00.mp4"
    intro_card(intro, crf, tmp)
    clips.append(intro)
    inv = {v["id"]: v for v in inventory._load("inventory.json", {"videos": []})["videos"]}
    for i, (vid, name) in enumerate(PARTS, 1):
        v = inv.get(vid)
        if not v or v["status"] != "backup":
            raise RuntimeError(f"{vid} ist nicht als Vorrat (backup) vorhanden")
        src = tmp / f"s{vid}.mp4"
        if local and (Path(local) / f"{vid}.mp4").exists():
            src = Path(local) / f"{vid}.mp4"
        else:
            transcribe.download(v["video_url"], src)
        dst = tmp / f"c{i:02d}.mp4"
        encode_clip(src, dst, f"Trick {i}: {name}", crf, tmp)
        starts.append(t)
        t += transcribe.probe_duration(dst)
        clips.append(dst)
        log(f"Teil {i}/{len(PARTS)} {vid} ok, Ende bei {stamp(t)}")
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{c}'\n" for c in clips), encoding="utf-8")
    out = tmp / "out.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(out)])
    return out, starts, transcribe.probe_duration(out)


def main(argv: list) -> int:
    inv = inventory._load("inventory.json", {"videos": []})
    if any(v["id"] == VID for v in inv["videos"]):
        log(f"{VID} ist schon im Inventar.")
        return 0
    local = os.environ.get("COMPILE_LOCAL", "")
    for crf in (27, 31, 35):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            out, starts, dur = build(crf, tmp, local)
            mb = out.stat().st_size / 1e6
            log(f"CRF {crf}: {dur} s, {mb:.1f} MB")
            if mb <= MAX_MB:
                break
    else:
        print("FEHLER: Datei bleibt ueber der Grenze von", MAX_MB, "MB")
        return 1
    errs = []
    if not MIN_S <= dur <= MAX_S:
        errs.append(f"Dauer {dur} s ausserhalb {MIN_S} bis {MAX_S} s")
    if len(TITLE) > 100:
        errs.append("Titel zu lang")
    desc = description(starts)
    if any(b - a < 10 for a, b in zip([0] + starts, starts)):
        errs.append("Kapitel kuerzer als 10 s")
    if errs:
        print("FEHLER:", "; ".join(errs))
        return 1
    if "--dry" in argv:
        print(desc)
        return 0
    dest = config.DATA / "videos" / f"{VID}.mp4"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(out.read_bytes())
    by = {v["id"]: v for v in inv["videos"]}
    for vid, _ in PARTS:
        by[vid]["status"] = "zusammenschnitt"
        by[vid]["notes"] = f"Teil von {VID} (kein zweiter Einsatz als Short)"
    inv["videos"].append({
        "id": VID, "format": "lang", "status": "ready", "created": inventory.now().isoformat(), "source": "zusammenschnitt",
        "topic": "10 Haushaltstricks", "hook_type": "Liste + Frage", "series": None, "episode": None, "duration": dur,
        "video_url": f"{config.RAW_BASE}/videos/{VID}.mp4", "title_tiktok": "", "title_youtube": TITLE, "text_tiktok": "",
        "text_youtube": desc, "scenes": len(PARTS), "parts": [p for p, _ in PARTS], "buffer": {}})
    inventory._save("inventory.json", inv)
    log(inventory.sync(f"{VID}: Zusammenschnitt 10 Haushaltstricks ({dur} s, {mb:.0f} MB)"))
    print(desc)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
