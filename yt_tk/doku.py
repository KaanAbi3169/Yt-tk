"""Doku-Format (Langvideo, 16:9, Auftrag des Inhabers 23.11.2026: "Youtube long videos müssen andere art videos sein"):
Dokumentar-Erklaervideo mit Infografik-Szenen statt Zusammenschnitt von Shorts.

    python3 -m yt_tk.doku script E001          # Sprechtext je Teil (fuer ElevenLabs), mit Zeichenzahl
    python3 -m yt_tk.doku check content_doku/E001.json
    python3 -m yt_tk.doku build --id E001 [--dry] [--fake]   # --fake: Teststimme (Stille) und gleichmaessige Wortzeiten, nichts gespeichert

Inhalt content_doku/<ID>.json: Titel/Beschreibung, theme, blocks[{chapter?, part, text, scenes[{type,...}]}], audio auf media als
audio/<ID>_<Teil>.mp3. Der Sprechtext ist die Verkettung der Block-Texte. Die Zeiten der Bloecke kommen aus Whisper
(Zuordnung ueber erkennbare Woerter des Blocks, sonst nach Textlaenge), die Szenen eines Blocks teilen sich seine Zeit."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from difflib import SequenceMatcher
from pathlib import Path

from . import config, inventory
from .build3d import clean, contact_sheet, log, probe, whisper_words

ROOT = Path(__file__).resolve().parent.parent
THEMES = {"nacht", "tiefsee", "weltraum", "erde", "papier", "glut"}
TYPES = {"titel": ["title"], "kapitel": ["nr", "title"], "zahl": ["value", "label"], "liste": ["items"], "vergleich": ["bars"],
         "zeitleiste": ["events"], "fakt": ["text"], "frage": ["question"]}
MOTIONS = ("zoom_in", "pan_left", "zoom_out", "pan_right", "zoom_in", "pan_up", "zoom_out", "pan_down")
MIN_WORDS = 1450   # bei ca. 2,45 Woertern pro Sekunde (gemessen) ergibt das mindestens 10 Minuten
FPS = 30


def norm(w: str) -> str:
    return re.sub(r"[^\w]", "", w.lower(), flags=re.UNICODE).replace("_", "")


def check_content(cfg: dict, strict: bool = True) -> list:
    errs = []
    if not re.fullmatch(r"[A-Z]\d{3}", cfg.get("id", "")):
        errs.append("id fehlt oder ungueltig")
    if cfg.get("theme") not in THEMES:
        errs.append(f"theme unbekannt: {cfg.get('theme')}")
    for k in ("title_youtube", "text_youtube", "topic"):
        if not (cfg.get(k) or "").strip():
            errs.append(f"{k} fehlt")
    if len(cfg.get("title_youtube", "")) > 100:
        errs.append("title_youtube laenger als 100 Zeichen")
    if "{KAPITEL}" not in cfg.get("text_youtube", ""):
        errs.append("text_youtube braucht {KAPITEL}")
    if "Stimme und Grafiken mit KI erstellt." not in cfg.get("text_youtube", ""):
        errs.append("text_youtube ohne KI-Hinweis")
    if len(cfg.get("sources", [])) < 3:
        errs.append("mindestens 3 Quellen")
    blocks = cfg.get("blocks", [])
    if len(blocks) < 12:
        errs.append(f"{len(blocks)} Bloecke (mindestens 12)")
    nwords = 0
    for i, b in enumerate(blocks):
        t = (b.get("text") or "").strip()
        if not t:
            errs.append(f"Block {i}: text fehlt")
        nwords += len(t.split())
        if b.get("part", 1) not in (1, 2, 3):
            errs.append(f"Block {i}: part 1 bis 3")
        if not b.get("scenes"):
            errs.append(f"Block {i}: keine Szene")
        for j, s in enumerate(b.get("scenes", [])):
            ty = s.get("type")
            if ty not in TYPES:
                errs.append(f"Block {i} Szene {j}: Typ unbekannt: {ty}")
                continue
            for need in TYPES[ty]:
                if not s.get(need):
                    errs.append(f"Block {i} Szene {j} ({ty}): {need} fehlt")
        if i == 0 and not b.get("chapter"):
            pass  # erstes Kapitel heisst automatisch "Einleitung"
    if strict and nwords < MIN_WORDS:
        errs.append(f"Sprechtext {nwords} Woerter (mindestens {MIN_WORDS} fuer 10 Minuten)")
    parts = [b.get("part", 1) for b in blocks]
    if parts != sorted(parts):
        errs.append("part muss aufsteigend sein")
    for p in set(parts):
        n = sum(len(b["text"]) + 1 for b in blocks if b.get("part", 1) == p)
        if n > 4900:
            errs.append(f"Teil {p}: {n} Zeichen (ElevenLabs-Limit 5 000 je Aufnahme)")
    return errs


def script_parts(cfg: dict) -> dict:
    out = {}
    for b in cfg["blocks"]:
        out.setdefault(b.get("part", 1), []).append(b["text"].strip())
    return {p: " ".join(t) for p, t in out.items()}


def align(texts: list, words: list) -> tuple:
    """Startzeit je Block. Block 0 beginnt bei 0. Zuordnung ueber das erste laenger als vier Zeichen lange, nicht numerische Wort des Blocks,
    das (in Reihenfolge) in der Whisper-Erkennung vorkommt, sonst nach Textlaenge. Liefert (Startzeiten, Zahl der Fallbacks)."""
    W = [norm(w["w"]) for w in words]
    t0, t1 = words[0]["s"], words[-1]["e"]
    total_chars = sum(len(t) for t in texts)
    starts, fb, p, cum = [], 0, 0, 0
    for bi, text in enumerate(texts):
        if bi == 0:
            starts.append(0.0)
            cum += len(text)
            continue
        toks = [norm(x) for x in text.split()]
        found = None
        for k, t in enumerate(toks[:14]):
            if len(t) < 5 or t.isdigit() or re.search(r"\d", t):
                continue
            for j in range(p, min(len(W), p + 90)):
                if W[j] == t or (len(t) >= 7 and SequenceMatcher(None, W[j], t).ratio() >= 0.85):
                    found = (j, k)
                    break
            if found:
                break
        if found:
            j, k = found
            st = max(words[j]["s"] - 0.30 * k, starts[-1] + 1.0)
            p = j + 1
        else:
            fb += 1
            st = max(t0 + cum / total_chars * (t1 - t0), starts[-1] + 1.0)
        starts.append(st)
        cum += len(text)
    return starts, fb


def fmt_ts(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _zoompan(motion: str, frames: int) -> str:
    D = max(frames - 1, 1)
    e = f"(3*pow(on/{D},2)-2*pow(on/{D},3))"
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    z = {"zoom_in": (f"1+0.07*{e}", cx, cy), "zoom_out": (f"1.07-0.07*{e}", cx, cy),
         "pan_left": ("1.06", f"(iw-iw/zoom)*(1-{e})", cy), "pan_right": ("1.06", f"(iw-iw/zoom)*{e}", cy),
         "pan_up": ("1.06", cx, f"(ih-ih/zoom)*(1-{e})"), "pan_down": ("1.06", cx, f"(ih-ih/zoom)*{e}")}[motion]
    return f"zoompan=z='{z[0]}':x='{z[1]}':y='{z[2]}':d={frames}:s=1920x1080:fps={FPS}"


def _ff(cmd: list) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg-Fehler:\n" + r.stderr[-2500:])


def make_clip(png: Path, motion: str, sec: float, out: Path) -> None:
    frames = max(int(round(sec * FPS)), 2)
    fade = f"fade=t=in:st=0:d=0.25,fade=t=out:st={max(sec - 0.25, 0):.2f}:d=0.25"
    _ff(["ffmpeg", "-y", "-v", "error", "-i", str(png), "-vf", _zoompan(motion, frames) + "," + fade + ",format=yuv420p",
         "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-r", str(FPS), "-g", "60", str(out)])


def build(vid: str, dry: bool, fake: bool) -> int:
    cfg = json.loads((ROOT / "content_doku" / f"{vid}.json").read_text(encoding="utf-8"))
    errs = check_content(cfg, strict=not fake)
    if errs:
        log("Pruefung des Inhalts durchgefallen: " + "; ".join(errs))
        return 1
    texts = [b["text"].strip() for b in cfg["blocks"]]
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        voice = tmp / "voice.wav"
        if fake:
            total_words = sum(len(t.split()) for t in texts)
            dur = total_words / 2.45
            _ff(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", f"{dur:.2f}", str(voice)])
            words, tcur = [], 0.0
            for t in " ".join(texts).split():
                words.append({"w": t, "s": tcur, "e": tcur + 0.35})
                tcur += 1 / 2.45
        else:
            parts = sorted({b.get("part", 1) for b in cfg["blocks"]})
            files = []
            for p in parts:
                f = config.DATA / "audio" / f"{vid}_{p}.mp3"
                if not f.exists():
                    log(f"Sprachdatei fehlt: {f}")
                    return 1
                files.append(f)
            listing = tmp / "a.txt"
            listing.write_text("".join(f"file '{f}'\n" for f in files), encoding="utf-8")
            _ff(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-ar", "48000", "-ac", "1", str(voice)])
            log("Wortzeiten (Whisper) ...")
            words = clean(whisper_words(voice), cfg.get("fix", {}))
            dur = float(probe(voice)["format"]["duration"])
        if len(words) < 100:
            log("Zu wenige Woerter erkannt")
            return 1
        starts, fb = align(texts, words)
        log(f"{len(words)} Woerter, Dauer {dur:.0f} s, {len(texts)} Bloecke, {fb} ohne Wortanker (Textlaengen-Schaetzung)")
        if fb > len(texts) * 0.3:
            log("Zu viele Bloecke ohne Wortanker, Zuordnung unsicher - Abbruch")
            return 1
        total = dur + 1.5
        # Szenen mit Zeiten
        plan = []
        for bi, b in enumerate(cfg["blocks"]):
            end = starts[bi + 1] if bi + 1 < len(starts) else total
            sc = b["scenes"]
            w = [max(0.2, float(s.get("w", 1))) for s in sc]
            span, acc = end - starts[bi], 0.0
            for j, s in enumerate(sc):
                d = span * w[j] / sum(w)
                spec = dict(s, theme=cfg["theme"])
                if b.get("chapter") and "kicker" not in spec:
                    spec["kicker"] = b["chapter"]
                plan.append({"name": f"s{bi:02d}_{j}", "spec": spec, "s": starts[bi] + acc, "d": d})
                acc += d
        shots = [{"name": p["name"], "spec": p["spec"]} for p in plan]
        if cfg.get("thumb"):
            shots.append({"name": "thumb", "spec": dict(cfg["thumb"], type="vorschau", theme=cfg["theme"])})
        (tmp / "shots.json").write_text(json.dumps(shots, ensure_ascii=False), encoding="utf-8")
        png = tmp / "png"
        env = None
        r = subprocess.run(["node", "shots.js", str(tmp / "shots.json"), str(png)], cwd=ROOT / "doku", capture_output=True, text=True)
        log(r.stdout.strip() or r.stderr.strip()[-300:])
        if r.returncode != 0:
            return 1
        clips = []
        for i, p in enumerate(plan):
            c = tmp / f"c{i:03d}.mp4"
            make_clip(png / f"{p['name']}.png", MOTIONS[i % len(MOTIONS)], p["d"], c)
            clips.append(c)
        log(f"{len(clips)} Szenen geschnitten")
        lst = tmp / "clips.txt"
        lst.write_text("".join(f"file '{c}'\n" for c in clips), encoding="utf-8")
        out = tmp / "out.mp4"
        music = config.ROOT / "assets" / "music" / "wissen.mp3"
        fc = (f"[1:a]aresample=48000,apad,atrim=0:{total:.2f},asplit=2[v1][vk];"
              f"[2:a]aresample=48000,atrim=0:{total:.2f},volume=0.07,afade=t=in:st=0:d=2,afade=t=out:st={max(total - 3, 0):.2f}:d=3[m];"
              f"[m][vk]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=300[md];"
              f"[v1][md]amix=inputs=2:duration=first:normalize=0,loudnorm=I={config.TARGET_LUFS}:TP=-1.5:LRA=11,aresample=48000[aout]")
        _ff(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(voice), "-stream_loop", "-1", "-i", str(music),
             "-filter_complex", fc, "-map", "0:v", "-map", "[aout]", "-t", f"{total:.2f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
             "-movflags", "+faststart", str(out)])
        info = probe(out)
        v = next(s for s in info["streams"] if s["codec_type"] == "video")
        d = float(info["format"]["duration"])
        mb = int(info["format"]["size"]) / 1e6
        qa = []
        if (v["width"], v["height"]) != (1920, 1080):
            qa.append(f"Aufloesung {v['width']}x{v['height']}")
        if not any(s["codec_type"] == "audio" for s in info["streams"]):
            qa.append("kein Ton")
        if d < 600 and not fake:
            qa.append(f"Dauer {d:.0f} s (mindestens 600)")
        if mb > 95:
            qa.append(f"{mb:.0f} MB (GitHub-Limit 100 MB)")
        if qa:
            log("Pruefung durchgefallen: " + "; ".join(qa))
            return 1
        log(f"Pruefung ok: {d:.0f} s, {mb:.1f} MB, 1920x1080, mit Ton")
        if dry or fake:
            keep = tmp.parent / f"{vid}_dry.mp4"
            shutil.copy(out, keep)
            contact_sheet(out, tmp.parent / f"{vid}_qa.jpg", d)
            if (png / "thumb.png").exists():
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(png / "thumb.png"), "-vf", "scale=1280:720", "-q:v", "3", str(tmp.parent / f"{vid}_thumb.jpg")], check=True)
            log(f"--dry/--fake: nichts gespeichert, Probe unter {keep}")
            return 0
        dest = config.DATA / "videos" / f"{vid}.mp4"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(out, dest)
        contact_sheet(out, config.DATA / "qa" / f"{vid}.jpg", d)
        if (png / "thumb.png").exists():
            th = config.DATA / "thumbs" / f"{vid}.jpg"
            th.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(png / "thumb.png"), "-vf", "scale=1280:720", "-q:v", "3", str(th)], check=True)
    # Kapitel (YouTube braucht 0:00 und mindestens 3 Kapitel)
    chapters, last = [], -99
    for bi, b in enumerate(cfg["blocks"]):
        name = b.get("chapter") or ("Einleitung" if bi == 0 else None)
        if name:
            chapters.append((starts[bi], name))
    ch = "\n".join(f"{fmt_ts(s)} {n}" for s, n in chapters)
    text = cfg["text_youtube"].replace("{KAPITEL}", "KAPITEL\n" + ch)
    inv = inventory._load("inventory.json", {"videos": []})
    inv["videos"] = [x for x in inv["videos"] if x["id"] != vid]
    inv["videos"].append({
        "id": vid, "format": "lang", "status": cfg.get("status", "ready"), "created": inventory.now().isoformat(), "source": "doku",
        "topic": cfg["topic"], "hook_type": cfg.get("hook_type", "Doku"), "series": None, "episode": None, "duration": round(d, 1),
        "video_url": f"{config.RAW_BASE}/videos/{vid}.mp4", "title_tiktok": "", "title_youtube": cfg["title_youtube"],
        "text_tiktok": "", "text_youtube": text, "scenes": len(plan), "buffer": {}, "group": cfg.get("group", "lang-doku"),
        "sources": cfg.get("sources", [])})
    inventory._save("inventory.json", inv)
    log(inventory.sync(f"{vid}: Doku {cfg['topic']} ({d / 60:.1f} min)"))
    return 0


def main(argv: list) -> int:
    if len(argv) >= 2 and argv[0] == "script":
        cfg = json.loads((ROOT / "content_doku" / f"{argv[1]}.json").read_text(encoding="utf-8"))
        for p, t in script_parts(cfg).items():
            print(f"=== TEIL {p}: {len(t.split())} Woerter, {len(t)} Zeichen ===\n{t}\n")
        return 0
    if argv and argv[0] == "check":
        bad = 0
        for a in argv[1:]:
            e = check_content(json.loads(Path(a).read_text(encoding="utf-8")))
            print(a + ": " + ("ok" if not e else "; ".join(e)))
            bad += bool(e)
        return 1 if bad else 0
    if argv and argv[0] == "build" and "--id" in argv:
        return build(argv[argv.index("--id") + 1], "--dry" in argv, "--fake" in argv)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
