"""Kinetic-Kurzvideo (Auftrag des Inhabers 24.11.2026: neuer Animationsstil, spannender, mehr Tempo).

Vertikal 1080x1920, bewegte Typografie, Szenenwechsel alle 2 bis 5 Sekunden mit Blitz und Zoom-Schlag, Wort-fuer-Wort-Untertitel
mit gelbem Aktivwort, hochzaehlende Zahlen, Karten, Balken, Gegenueberstellung, Foto mit Quelle, Abschlussfrage. Alles wird als
Funktion der Zeit in Chromium gezeichnet (kinetic/stage.html), ffmpeg setzt Bild und Ton zusammen. Ohne Claude, 0 EUR.

    python3 -m yt_tk.kinetic check content_kin/N001.json [...]
    python3 -m yt_tk.kinetic build --id N001 [--dry] [--fake]     (--fake: stille Probe ohne Whisper, nur zum Testen)

Inhalt content_kin/<ID>.json: id, topic, hook_type, group, theme (neon, toxic, sunset, ice, fire, mono), tag (optional, z. B. "TEIL 1"),
script (Sprechtext), music (wissen, waswaerewenn, horror), title_tiktok, title_youtube, text_tiktok, text_youtube, sources, hl (Regex fuer
farbige Woerter) und scenes: [{type, at (Regex auf das gesprochene Wort, n = wievieltes Vorkommen, fallback = Anteil 0 bis 1), ...}].
Szenentypen: hook (text, emoji, hl), zahl (value, decimals, unit, label, text), karten (items, title), vs (a, b: name/value/text, win),
balken (items: name/value/text), foto (image = Bild-ID, caption), frage (text, options).
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import config, inventory, textcheck
from .build3d import clean, contact_sheet, log, probe, whisper_words
from .doku import norm

ROOT = Path(__file__).resolve().parent.parent
THEMES = {"neon", "toxic", "sunset", "ice", "fire", "mono"}
NEED = {"hook": ["text"], "zahl": ["value", "label"], "karten": ["items"], "vs": ["a", "b"], "balken": ["items"], "foto": ["image"],
        "frage": ["text", "options"]}
FPS = 30


def check_content(cfg: dict) -> list:
    errs = []
    for k in ("id", "topic", "script", "scenes", "title_tiktok", "title_youtube", "text_tiktok", "text_youtube"):
        if not cfg.get(k):
            errs.append(f"{k} fehlt")
    if cfg.get("theme", "neon") not in THEMES:
        errs.append("theme unbekannt")
    sc = cfg.get("scenes") or []
    if not 5 <= len(sc) <= 16:
        errs.append(f"{len(sc)} Szenen (5 bis 16)")
    for i, s in enumerate(sc):
        ty = s.get("type")
        if ty not in NEED:
            errs.append(f"Szene {i}: Typ unbekannt: {ty}")
            continue
        for k in NEED[ty]:
            if s.get(k) in (None, "", []):
                errs.append(f"Szene {i} ({ty}): {k} fehlt")
        if i > 0 and "at" not in s:
            errs.append(f"Szene {i}: at (Wortanker) fehlt")
        if ty == "karten" and not 2 <= len(s.get("items", [])) <= 5:
            errs.append(f"Szene {i}: karten 2 bis 5 Eintraege")
        if ty == "hook" and len(s.get("text", "")) > 60:
            errs.append(f"Szene {i}: hook-Text zu lang (hoechstens 60 Zeichen)")
    if sc and sc[0].get("type") != "hook":
        errs.append("erste Szene muss hook sein")
    if sc and sc[-1].get("type") != "frage":
        errs.append("letzte Szene muss frage sein")
    return errs + textcheck.check(cfg)


def resolve(scenes: list, words: list, dur: float) -> list:
    """Startzeit je Szene aus dem Wortanker (Regex auf das normalisierte Wort), sonst Anteil der Dauer."""
    W = [norm(w["w"]) for w in words]
    pos, out = 0, []
    for i, s in enumerate(scenes):
        if i == 0:
            out.append(0.0)
            continue
        pat, n, found = re.compile(s["at"], re.I) if isinstance(s["at"], str) else None, int(s.get("n", 1)), None
        if pat:
            hits = 0
            for k in range(pos, len(W)):
                if pat.search(W[k]):
                    hits += 1
                    if hits == n:
                        found = k
                        break
        if found is None:
            st = float(s.get("fallback", i / len(scenes))) * dur
            log(f"Szene {i}: Anker {s['at']!r} nicht gefunden, Fallback {st:.1f} s")
            out.append(max(st, out[-1] + 1.0))
            continue
        pos = found + 1
        out.append(max(words[found]["s"] - 0.05, out[-1] + 0.9))
    return out


def build(vid: str, dry: bool, fake: bool) -> int:
    cfg = json.loads((ROOT / "content_kin" / f"{vid}.json").read_text(encoding="utf-8"))
    errs = check_content(cfg)
    if errs:
        log("Pruefung des Inhalts durchgefallen: " + "; ".join(errs))
        return 1
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        voice = tmp / "voice.wav"
        if fake:
            toks = cfg["script"].split()
            dur_v = len(toks) / 2.8
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", f"{dur_v:.2f}", str(voice)], check=True)
            words = [{"w": re.sub(r"[.,!?:;]", "", t), "s": i / 2.8, "e": i / 2.8 + 0.3} for i, t in enumerate(toks)]
            raw = toks
        else:
            f = config.DATA / "audio" / f"{vid}.mp3"
            if not f.exists():
                log(f"Sprachdatei fehlt: {f}")
                return 1
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(f), "-ar", "48000", "-ac", "1", str(voice)], check=True)
            orig = whisper_words(voice)
            words, raw = [], []
            for w in orig:
                c = clean([w], cfg.get("fix", {}))
                if c:
                    words.append(c[0])
                    raw.append(w["w"])
            dur_v = float(probe(voice)["format"]["duration"])
        if len(words) < 40:
            log("Zu wenige Woerter erkannt")
            return 1
        dur = dur_v + 0.9
        starts = resolve(cfg["scenes"], words, dur_v)
        db = {x["id"]: x for x in inventory._load("images.json", {"images": []})["images"]}
        scenes = []
        for i, s in enumerate(cfg["scenes"]):
            sc = dict(s, s=round(starts[i], 3), e=round(starts[i + 1] if i + 1 < len(starts) else dur, 3))
            sc["len"] = sc["e"] - sc["s"]
            if s["type"] == "foto":
                img, fp = db.get(s["image"]), config.DATA / "images" / f"{s['image']}.jpg"
                if not img or not fp.exists():
                    log(f"Bild {s['image']} fehlt - Abbruch")
                    return 1
                sc["url"], sc["credit"] = fp.as_uri(), img["credit"]
            scenes.append(sc)
        longest = max(s["len"] for s in scenes)
        if longest > 7.5:
            log(f"Warnung: laengste Szene {longest:.1f} s (Ziel unter 6 s, mehr Szenen einbauen)")
        log(f"{len(words)} Woerter, {dur:.1f} s, {len(scenes)} Szenen, Schnitt alle {dur / len(scenes):.1f} s")
        job = {"theme": cfg.get("theme", "neon"), "tag": cfg.get("tag", ""), "hl": cfg.get("hl", ""), "dur": dur, "scenes": scenes, "words": words,
               "raw": raw}
        (tmp / "job.json").write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
        frames = tmp / "frames"
        r = subprocess.run(["node", "kin.js", str(tmp / "job.json"), str(frames)], cwd=ROOT / "kinetic", capture_output=True, text=True)
        log(r.stdout.strip() or r.stderr.strip()[-400:])
        if r.returncode != 0:
            return 1
        out = tmp / "out.mp4"
        music = config.ROOT / "assets" / "music" / f"{cfg.get('music', 'wissen')}.mp3"
        fc = (f"[1:a]aresample=48000,apad,atrim=0:{dur:.2f},asplit=2[v1][vk];"
              f"[2:a]aresample=48000,atrim=0:{dur:.2f},volume=0.10,afade=t=in:st=0:d=0.5,afade=t=out:st={max(dur - 1.5, 0):.2f}:d=1.5[m];"
              f"[m][vk]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=300[md];"
              f"[v1][md]amix=inputs=2:duration=first:normalize=0,loudnorm=I={config.TARGET_LUFS}:TP=-1.5:LRA=11,aresample=48000[aout]")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS), "-i", str(frames / "f%05d.jpg"), "-i", str(voice), "-stream_loop", "-1", "-i", str(music),
                        "-filter_complex", fc, "-map", "0:v", "-map", "[aout]", "-t", f"{dur:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)], check=True)
        info = probe(out)
        v = next(s for s in info["streams"] if s["codec_type"] == "video")
        d = float(info["format"]["duration"])
        mb = int(info["format"]["size"]) / 1e6
        qa = []
        if (v["width"], v["height"]) != (1080, 1920):
            qa.append(f"Aufloesung {v['width']}x{v['height']}")
        if not any(s["codec_type"] == "audio" for s in info["streams"]):
            qa.append("kein Ton")
        if not 15 <= d <= 90:
            qa.append(f"Dauer {d:.1f} s")
        if mb > 95:
            qa.append(f"{mb:.0f} MB")
        if qa:
            log("Pruefung durchgefallen: " + "; ".join(qa))
            return 1
        log(f"Pruefung ok: {d:.1f} s, {mb:.1f} MB, 1080x1920, mit Ton")
        if dry or fake:
            keep = tmp.parent / f"{vid}_dry.mp4"
            shutil.copy(out, keep)
            contact_sheet(out, tmp.parent / f"{vid}_qa.jpg", d)
            log(f"--dry/--fake: nichts gespeichert, Probe unter {keep}")
            return 0
        dest = config.DATA / "videos" / f"{vid}.mp4"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(out, dest)
        th = config.DATA / "thumbs" / f"{vid}.jpg"
        th.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "0.9", "-i", str(out), "-frames:v", "1", "-q:v", "3", str(th)], check=True)
        contact_sheet(out, config.DATA / "qa" / f"{vid}.jpg", d)
    inv = inventory._load("inventory.json", {"videos": []})
    inv["videos"] = [x for x in inv["videos"] if x["id"] != vid]
    inv["videos"].append({
        "id": vid, "format": cfg.get("format", "wissen"), "status": cfg.get("status", "ready"), "created": inventory.now().isoformat(), "source": "kinetic",
        "topic": cfg["topic"], "hook_type": cfg.get("hook_type", "Kinetic"), "series": cfg.get("series"), "episode": cfg.get("episode"), "duration": round(d, 1),
        "video_url": f"{config.RAW_BASE}/videos/{vid}.mp4", "title_tiktok": cfg["title_tiktok"], "title_youtube": cfg["title_youtube"],
        "text_tiktok": cfg["text_tiktok"], "text_youtube": cfg["text_youtube"], "scenes": len(scenes), "buffer": {}, "group": cfg.get("group", "kinetic"),
        "sources": cfg.get("sources", [])})
    inventory._save("inventory.json", inv)
    log(inventory.sync(f"{vid}: Kinetic-Video {cfg['topic']} ({d:.0f} s)"))
    return 0


def main(argv: list) -> int:
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
