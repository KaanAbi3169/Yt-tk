"""V-034: Baut ein 3D-Video ohne Claude: Sprache -> Wortzeiten (Whisper) -> Szene rendern (Chromium) -> Untertitel -> Ton -> Pruefung -> Inventar.

    python3 -m yt_tk.build3d --id T001 [--px 2] [--dry]

Eingaben: content3d/<ID>.json (Szene, Titel, Texte) im Code-Repo und die Sprachdatei <Daten>/audio/<ID>.mp3 (Action `audio`).
Ergebnis: <Daten>/videos/<ID>.mp4 (1080x1920) und ein Eintrag im Inventar (Status aus content3d/<ID>.json, Standard pinned = nur per Pin;
"ready" = die Planung setzt das Video selbst ein, bevorzugt vor dem Vorrat).
--dry: baut und prueft das Video, schreibt aber nichts ins Inventar und pusht nicht.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import config, inventory, kitcheck, textcheck, transcribe

FPS = 30
ROOT = Path(__file__).resolve().parent.parent
R3D = ROOT / "render3d"
PORT = 8791


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def whisper_words(audio_mp3: Path) -> list:
    from faster_whisper import WhisperModel
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _ = model.transcribe(transcribe.extract_audio(audio_mp3), language="de", beam_size=1, word_timestamps=True)
    out = []
    for s in segs:
        for w in s.words or []:
            t = w.word.strip()
            if t:
                out.append({"w": t, "s": round(w.start, 3), "e": round(w.end, 3)})
    return out


def clean(words: list, fix: dict) -> list:
    out = []
    for w in words:
        t = w["w"].strip(" ,.;:„“\"")
        for pat, rep in fix.items():
            t = re.sub(pat, rep, t)
        if t:
            out.append({**w, "w": t})
    return out


def ass(words: list, highlight: str, dur: float, credits: list = ()) -> str:
    def ts(x):
        h, r = divmod(max(0, x), 3600)
        m, s = divmod(r, 60)
        return f"{int(h)}:{int(m):02d}:{s:05.2f}"
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n[V4+ Styles]\n"
            "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,"
            "ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
            "Style: W,DejaVu Sans,104,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,10,3,5,60,60,0,1\n"
            "Style: C,DejaVu Sans,30,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,1,7,36,36,0,1\n\n"
            "[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n")
    hl = re.compile(highlight, re.I) if highlight else None
    lines = []
    for i, w in enumerate(words):
        start = w["s"]
        end = words[i + 1]["s"] if i + 1 < len(words) else min(dur, w["e"] + 0.5)
        end = max(end, start + 0.12)
        txt = w["w"].replace("{", "").replace("}", "")
        col = "{\\c&H0000E5FF&}" if hl and hl.search(txt) else ""
        lines.append(f"Dialogue: 0,{ts(start)},{ts(end)},W,,0,0,0,,{{\\an5\\pos(540,1300)\\fscx80\\fscy80\\t(0,90,\\fscx100\\fscy100)}}{col}{txt}")
    for c in credits:  # kleine Quellenangabe oben links (unterhalb des Badge-Bereichs), nur solange das Bild zu sehen ist
        lines.append(f"Dialogue: 1,{ts(c['s'])},{ts(c['e'])},C,,0,0,0,,{{\\an7\\pos(36,290)\\1a&H30&}}{c['text'].replace('{', '').replace('}', '')}")
    return head + "\n".join(lines) + "\n"


def probe(path: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,duration:format=duration,size",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def build(vid: str, px: float, dry: bool) -> int:
    cfg = json.loads((ROOT / "content3d" / f"{vid}.json").read_text(encoding="utf-8"))
    errs = textcheck.check(cfg)
    if errs:
        log("Textpruefung durchgefallen: " + "; ".join(errs))
        return 1
    audio = config.DATA / "audio" / f"{cfg.get('audio_id', vid)}.mp3"  # audio_id: Sprache eines anderen Videos nutzen (Tests)
    if not audio.exists():
        log(f"Sprachdatei fehlt: {audio}")
        return 1
    log("Wortzeiten (Whisper) ...")
    words = clean(whisper_words(audio), cfg.get("fix", {}))
    if len(words) < 10:
        log("Zu wenige Woerter erkannt")
        return 1
    if cfg["scene"] == "kit":  # Szenenbaukasten: Beschreibung pruefen (Anker gegen die gesprochenen Woerter) und der Buehne geben
        kerr, kwarn = kitcheck.check(cfg, words)
        for w in kwarn:
            log("Baukasten-Warnung: " + w)
        if kerr:
            log("Baukasten-Pruefung durchgefallen: " + "; ".join(kerr))
            return 1
        (R3D / "scene.json").write_text(json.dumps(cfg["kit"], ensure_ascii=False), encoding="utf-8")
    else:
        (R3D / "scene.json").unlink(missing_ok=True)
    (R3D / "words.json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    imgs = R3D / "images"
    shutil.rmtree(imgs, ignore_errors=True)
    imgs.mkdir()
    used = [c["id"] for c in cfg.get("credits", [])]
    for iid in used:
        src = config.DATA / "images" / f"{iid}.jpg"
        if not src.exists():
            log(f"Bild fehlt: {iid}")
            return 1
        shutil.copy(src, imgs / f"{iid}.jpg")
    (imgs / "index.json").write_text(json.dumps(used), encoding="utf-8")
    log(f"{len(words)} Woerter, Ende bei {words[-1]['e']:.1f} s")
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1", "--directory", str(R3D)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            frames = tmp / "frames"
            time.sleep(1.5)
            env = {**__import__("os").environ, "PORT": str(PORT)}
            r = subprocess.run(["node", "render.js", cfg["scene"], str(px), str(frames)], cwd=R3D, env=env)
            if r.returncode != 0:
                log("Rendern fehlgeschlagen")
                return 1
            n = len(list(frames.glob("f*.jpg")))
            dur = n / FPS
            db = {x["id"]: x for x in inventory._load("images.json", {"images": []})["images"]}
            credits = []
            for c in cfg.get("credits", []):
                st = c["from"] if isinstance(c["from"], (int, float)) else next((w["s"] for w in words if re.search(c["from"], w["w"], re.I)), 0)
                credits.append({"s": st, "e": st + c.get("dur", 4.0), "text": db[c["id"]]["credit"]})
            (tmp / "c.ass").write_text(ass(words, cfg.get("highlight", r"\d|prozent|mythos|best\w+tigt|termin"), dur, credits), encoding="utf-8")
            out = tmp / "out.mp4"
            vf = "scale=1080:1920:flags=lanczos,subtitles=c.ass:fontsdir=/usr/share/fonts/truetype/dejavu"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", str(frames / "f%05d.jpg"), "-i", str(audio),
                            "-vf", vf, "-af", f"loudnorm=I={config.TARGET_LUFS}:TP=-1.5:LRA=11,apad=pad_dur=1", "-t", f"{dur:.2f}",
                            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                            "-movflags", "+faststart", str(out)], cwd=tmp, check=True)
            info = probe(out)
            v = next(s for s in info["streams"] if s["codec_type"] == "video")
            has_audio = any(s["codec_type"] == "audio" for s in info["streams"])
            d = float(info["format"]["duration"])
            mb = int(info["format"]["size"]) / 1e6
            qa = []
            if (v["width"], v["height"]) != (1080, 1920):
                qa.append(f"Aufloesung {v['width']}x{v['height']}")
            if not has_audio:
                qa.append("kein Ton")
            if not 15 <= d <= 90:
                qa.append(f"Dauer {d:.1f} s")
            if mb > 95:
                qa.append(f"{mb:.0f} MB")
            first = tmp / "mid.jpg"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{d / 2:.1f}", "-i", str(out), "-frames:v", "1", "-vf", "scale=64:-2,format=gray",
                            str(first)], check=True)
            if first.stat().st_size < 400:
                qa.append("Bild fast leer")
            if qa:
                log("Pruefung durchgefallen: " + "; ".join(qa))
                return 1
            log(f"Pruefung ok: {d:.1f} s, {mb:.1f} MB, 1080x1920, mit Ton")
            if dry:
                shutil.copy(out, tmp.parent / f"{vid}_dry.mp4")
                log("--dry: nichts gespeichert")
                return 0
            dest = config.DATA / "videos" / f"{vid}.mp4"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(out, dest)
            thumb = config.DATA / "thumbs" / f"{vid}.jpg"
            thumb.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{min(2.5, d / 3):.1f}", "-i", str(out), "-frames:v", "1", "-q:v", "3", str(thumb)], check=True)
    finally:
        srv.terminate()
    inv = inventory._load("inventory.json", {"videos": []})
    inv["videos"] = [x for x in inv["videos"] if x["id"] != vid]
    inv["videos"].append({
        "id": vid, "format": cfg["format"], "status": cfg.get("status", "pinned"), "created": inventory.now().isoformat(), "source": "render3d",
        "topic": cfg["topic"], "hook_type": cfg["hook_type"], "series": None, "episode": None, "duration": round(d, 1),
        "video_url": f"{config.RAW_BASE}/videos/{vid}.mp4", "title_tiktok": cfg["title_tiktok"], "title_youtube": cfg["title_youtube"],
        "text_tiktok": cfg["text_tiktok"], "text_youtube": cfg["text_youtube"], "scenes": 1, "buffer": {}, "group": cfg.get("group", "3d-test"),
        "sources": cfg.get("sources", [])})
    inventory._save("inventory.json", inv)
    log(inventory.sync(f"{vid}: 3D-Video {cfg['topic']} ({d:.0f} s)"))
    return 0


def main(argv: list) -> int:
    if "--id" not in argv:
        print(__doc__)
        return 2
    px = float(argv[argv.index("--px") + 1]) if "--px" in argv else 2.0
    return build(argv[argv.index("--id") + 1], px, "--dry" in argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
