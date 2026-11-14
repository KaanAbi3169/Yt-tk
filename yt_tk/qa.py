"""Automatische Qualitaetspruefung vor dem Upload."""
import json
import re
import subprocess
from pathlib import Path

from . import config


def _probe(path: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffprobe: " + r.stderr)
    return json.loads(r.stdout)


def _ffmpeg_log(args: list) -> str:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args, "-f", "null", "-"],
                       capture_output=True, text=True)
    return r.stderr


def check(video: Path, fmt: str, words: list, ass: Path) -> dict:
    f = config.FORMATS[fmt]
    issues, info = [], {}
    p = _probe(video)
    v = next((s for s in p["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in p["streams"] if s["codec_type"] == "audio"), None)
    dur = float(p["format"]["duration"])
    size = int(p["format"]["size"])
    info.update(duration=round(dur, 2), size_mb=round(size / 1e6, 2))

    if not v:
        issues.append("Keine Videospur")
    else:
        if (int(v["width"]), int(v["height"])) != (config.VIDEO_W, config.VIDEO_H):
            issues.append(f"Aufloesung {v['width']}x{v['height']} statt 1080x1920")
        if v.get("codec_name") != "h264" or v.get("pix_fmt") != "yuv420p":
            issues.append("Video nicht h264/yuv420p")
    if not a:
        issues.append("Keine Tonspur")
    if not (f["min_s"] <= dur <= f["max_s"]):
        issues.append(f"Laenge {dur:.1f}s ausserhalb {f['min_s']}-{f['max_s']}s")
    if size > 250e6 or size < 300e3:
        issues.append(f"Dateigroesse auffaellig: {size / 1e6:.1f} MB")

    # Datei komplett dekodierbar?
    err = _ffmpeg_log(["-v", "error", "-i", str(video)])
    if err.strip():
        issues.append("Dekodierfehler: " + err.strip()[:300])

    # Schwarze Bilder (Uebergaenge sind kuerzer als 0.6 s)
    log = _ffmpeg_log(["-i", str(video), "-vf", "blackdetect=d=0.6:pic_th=0.98:pix_th=0.04", "-an"])
    blacks = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", log)
    if blacks:
        issues.append(f"Schwarzbild erkannt: {blacks[:3]}")

    # Ton: Lautheit und lange Stille
    log = _ffmpeg_log(["-i", str(video), "-vn", "-af", "ebur128=framelog=quiet,silencedetect=n=-50dB:d=1.5"])
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", log)
    lufs = float(m[-1]) if m else None
    info["lufs"] = lufs
    if lufs is None or not (-18 <= lufs <= -10):
        issues.append(f"Lautheit {lufs} LUFS (Ziel -14)")
    if "silence_start" in log:
        issues.append("Stille > 1.5 s im Ton")

    # Untertitel synchron? ASS-Ereignisse gegen Wort-Zeitstempel
    events = []
    for line in Path(ass).read_text(encoding="utf-8").splitlines():
        if line.startswith("Dialogue:"):
            parts = line.split(",", 9)
            events.append((_t(parts[1]), _t(parts[2])))
    if not events:
        issues.append("Keine Untertitel")
    else:
        first_word, last_word = words[0]["start"], words[-1]["end"]
        if abs(events[0][0] - first_word) > 0.15:
            issues.append("Untertitel-Start nicht synchron")
        if events[-1][1] > dur + 0.05 or last_word - events[-1][1] > 0.3:
            issues.append("Untertitel-Ende nicht synchron")
        if any(e[1] < e[0] for e in events) or any(events[i + 1][0] < events[i][0] for i in range(len(events) - 1)):
            issues.append("Untertitel-Reihenfolge fehlerhaft")
        info["subtitle_events"] = len(events)
        if last_word > dur:
            issues.append("Sprache laenger als Video")
    return {"ok": not issues, "issues": issues, **info}


def _t(s: str) -> float:
    h, m, rest = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(rest)
