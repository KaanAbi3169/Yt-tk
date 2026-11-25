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
from .doku import align, fmt_ts, norm

ROOT = Path(__file__).resolve().parent.parent
THEMES = {"neon", "toxic", "sunset", "ice", "fire", "mono", "weltraum"}
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


# ---------------- Langvideo (Querformat, 10+ Minuten) ----------------
LONG_NEED = {"hook": ["text"], "zitat": ["text"], "zahl": ["value", "label"], "karten": ["items"], "vs": ["a", "b"], "balken": ["items"],
             "foto": ["image"], "frage": ["text", "options"], "kapitel": ["nr", "title"], "zeit": ["events"]}
LONG_MIN_WORDS = 1450


def check_long(cfg: dict, strict: bool = True) -> list:
    errs = []
    for k in ("id", "topic", "title_youtube", "text_youtube", "theme"):
        if not cfg.get(k):
            errs.append(f"{k} fehlt")
    if cfg.get("theme") and cfg["theme"] not in THEMES:
        errs.append("theme unbekannt")
    if "{KAPITEL}" not in cfg.get("text_youtube", ""):
        errs.append("text_youtube ohne {KAPITEL}")
    if len(cfg.get("sources", [])) < 3:
        errs.append("mindestens 3 Quellen")
    blocks, nwords = cfg.get("blocks") or [], 0
    if not 20 <= len(blocks):
        errs.append(f"{len(blocks)} Bloecke (mindestens 20)")
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
            if ty not in LONG_NEED:
                errs.append(f"Block {i} Szene {j}: Typ unbekannt: {ty}")
                continue
            for k in LONG_NEED[ty]:
                if s.get(k) in (None, "", []):
                    errs.append(f"Block {i} Szene {j} ({ty}): {k} fehlt")
    if strict and nwords < LONG_MIN_WORDS:
        errs.append(f"Sprechtext {nwords} Woerter (mindestens {LONG_MIN_WORDS})")
    parts = [b.get("part", 1) for b in blocks]
    if parts != sorted(parts):
        errs.append("part muss aufsteigend sein")
    for p in set(parts):
        n = sum(len(b["text"]) + 1 for b in blocks if b.get("part", 1) == p)
        if n > 4900:
            errs.append(f"Teil {p}: {n} Zeichen (Limit 5 000)")
    return errs


def _sentences(text: str) -> list:
    return [x for x in re.split(r"(?<=[.!?])\s+", text.strip()) if x]


def timeline(cfg: dict, words: list, dur_v: float, raw: list = None) -> tuple:
    """Szenenliste fuer ein Langvideo: je Block zuerst die Bildszenen, danach Karaoke-Saetze (satz) bis zum Blockende."""
    texts = [b["text"].strip() for b in cfg["blocks"]]
    starts, fb = align(texts, words)
    ends = starts[1:] + [dur_v + 0.6]
    scenes, chapter = [], "Einleitung"
    for bi, b in enumerate(cfg["blocks"]):
        t0, t1 = starts[bi], ends[bi]
        span = t1 - t0
        chapter = b.get("chapter") or chapter
        idx = [k for k, w in enumerate(words) if t0 - 0.01 <= w["s"] < t1 - 0.01]
        sent = _sentences(texts[bi])
        # Satzgrenzen als Wortindizes (anteilig ueber die Zeichen, robust gegen Whisper-Abweichungen)
        bounds, acc = [], 0
        tot = sum(len(x.split()) for x in sent) or 1
        for x in sent:
            a = idx[0] + int(round(len(idx) * acc / tot)) if idx else 0
            acc += len(x.split())
            bounds.append(min(a, len(words) - 1))
        # genauer: Satzzeichen aus der Whisper-Ausgabe (Zahlen als Ziffern verfaelschen die Wortzaehlung)
        if raw and idx and len(raw) == len(words):
            wb = [idx[0]] + [k + 1 for k in idx[:-1] if re.search(r"[.!?]$", raw[k]) and not re.match(r"^\d+\.$", raw[k])]
            if len(wb) >= max(1, len(sent) // 2):
                bounds = wb
        # Ende der Bildszenen: erste Satzgrenze nach 40 Prozent der Blockzeit (mindestens 4 s), sonst Blockende
        vis_end = t1
        if span > 9 and idx:
            for k, a in enumerate(bounds):
                if k > 0 and words[a]["s"] >= t0 + max(4.0, 0.4 * span):
                    vis_end = words[a]["s"]
                    break
        vs = b["scenes"]
        wts = [max(0.2, float(s.get("w", 1))) for s in vs]
        acc_t = t0
        for j, s in enumerate(vs):
            d = (vis_end - t0) * wts[j] / sum(wts)
            sc = dict(s, s=round(acc_t, 3), e=round(acc_t + d, 3), kicker=chapter)
            scenes.append(sc)
            acc_t += d
        if vis_end < t1 - 0.5 and idx:
            groups, cur = [], []
            for k, a in enumerate(bounds):
                if words[a]["s"] < vis_end - 0.01:
                    continue
                cur.append(k)
                nxt = bounds[k + 1] if k + 1 < len(bounds) else None
                st = words[bounds[cur[0]]]["s"]
                en = words[nxt]["s"] if nxt is not None and nxt < len(words) else t1
                if en - st >= 4.5 or nxt is None:
                    groups.append((cur[0], k))
                    cur = []
            if cur:
                groups.append((cur[0], cur[-1]))
            for g0, g1 in groups:
                a = bounds[g0]
                nb = bounds[g1 + 1] if g1 + 1 < len(bounds) else idx[-1] + 1
                a1 = max(a, min(nb, len(words)) - 1)
                st = words[a]["s"] - 0.05
                scenes.append({"type": "satz", "s": round(max(st, scenes[-1]["s"] + 0.5), 3), "wi0": a, "wi1": a1, "kicker": chapter, "flash": False})
    scenes.sort(key=lambda x: x["s"])
    for i, sc in enumerate(scenes):
        sc["e"] = scenes[i + 1]["s"] if i + 1 < len(scenes) else dur_v + 1.5
        sc["len"] = sc["e"] - sc["s"]
    return scenes, starts, fb


def build_long(vid: str, dry: bool, fake: bool) -> int:
    cfg = json.loads((ROOT / "content_kin" / f"{vid}.json").read_text(encoding="utf-8"))
    errs = check_long(cfg, strict=not fake)
    if errs:
        log("Pruefung des Inhalts durchgefallen: " + "; ".join(errs))
        return 1
    texts = [b["text"].strip() for b in cfg["blocks"]]
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        voice = tmp / "voice.wav"
        if fake:
            toks = " ".join(texts).split()
            dur_v = len(toks) / 2.6
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", f"{dur_v:.2f}", str(voice)], check=True)
            words = [{"w": re.sub(r"[.,!?:;]", "", t), "s": i / 2.6, "e": i / 2.6 + 0.3} for i, t in enumerate(toks)]
            raw = toks
        else:
            files = []
            for p in sorted({b.get("part", 1) for b in cfg["blocks"]}):
                f = config.DATA / "audio" / f"{vid}_{p}.mp3"
                if not f.exists():
                    log(f"Sprachdatei fehlt: {f}")
                    return 1
                files.append(f)
            listing = tmp / "a.txt"
            listing.write_text("".join(f"file '{f}'\n" for f in files), encoding="utf-8")
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-ar", "48000", "-ac", "1", str(voice)], check=True)
            log("Wortzeiten (Whisper) ...")
            orig = whisper_words(voice)
            words, raw = [], []
            for w in orig:
                c = clean([w], cfg.get("fix", {}))
                if c:
                    words.append(c[0])
                    raw.append(w["w"])
            dur_v = float(probe(voice)["format"]["duration"])
        if len(words) < 300:
            log("Zu wenige Woerter erkannt")
            return 1
        scenes, starts, fb = timeline(cfg, words, dur_v, raw)
        if fb > len(texts) * 0.3:
            log(f"Zu viele Bloecke ohne Wortanker ({fb}), Zuordnung unsicher - Abbruch")
            return 1
        dur = dur_v + 1.5
        db = {x["id"]: x for x in inventory._load("images.json", {"images": []})["images"]}
        for sc in scenes:
            if sc["type"] == "foto":
                img, fp = db.get(sc["image"]), config.DATA / "images" / f"{sc['image']}.jpg"
                if not img or not fp.exists():
                    log(f"Bild {sc['image']} fehlt - Abbruch")
                    return 1
                sc["url"], sc["credit"] = fp.as_uri(), img["credit"]
        longest = max(s["len"] for s in scenes)
        log(f"{len(words)} Woerter, {dur / 60:.1f} min, {len(scenes)} Szenen, Schnitt alle {dur / len(scenes):.1f} s, laengste Szene {longest:.1f} s, {fb} ohne Wortanker")
        job = {"land": True, "zoom": 2 / 3, "fps": 24, "theme": cfg["theme"], "hl": cfg.get("hl", ""), "dur": dur, "scenes": scenes, "words": words, "raw": raw}
        (tmp / "job.json").write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
        frames = tmp / "frames"
        r = subprocess.run(["node", "kin.js", str(tmp / "job.json"), str(frames)], cwd=ROOT / "kinetic", capture_output=True, text=True)
        log(r.stdout.strip()[-300:] or r.stderr.strip()[-400:])
        if r.returncode != 0:
            return 1
        out = tmp / "out.mp4"
        music = config.ROOT / "assets" / "music" / f"{cfg.get('music', 'wissen')}.mp3"
        fc = (f"[1:a]aresample=48000,apad,atrim=0:{dur:.2f},asplit=2[v1][vk];"
              f"[2:a]aresample=48000,atrim=0:{dur:.2f},volume=0.07,afade=t=in:st=0:d=2,afade=t=out:st={max(dur - 3, 0):.2f}:d=3[m];"
              f"[m][vk]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=300[md];"
              f"[v1][md]amix=inputs=2:duration=first:normalize=0,loudnorm=I={config.TARGET_LUFS}:TP=-1.5:LRA=11,aresample=48000[aout]")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", "24", "-i", str(frames / "f%05d.jpg"), "-i", str(voice), "-stream_loop", "-1", "-i", str(music),
                        "-filter_complex", fc, "-map", "0:v", "-map", "[aout]", "-t", f"{dur:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "27",
                        "-maxrate", "850k", "-bufsize", "1700k", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(out)], check=True)
        info = probe(out)
        v = next(s for s in info["streams"] if s["codec_type"] == "video")
        d = float(info["format"]["duration"])
        mb = int(info["format"]["size"]) / 1e6
        qa = []
        if (v["width"], v["height"]) != (1280, 720):
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
        log(f"Pruefung ok: {d:.0f} s, {mb:.1f} MB, 1280x720, mit Ton")
        thumb = None
        if cfg.get("thumb"):
            tj = {"land": True, "zoom": 2 / 3, "fps": 24, "theme": cfg["theme"], "hl": "", "dur": 0.7, "words": [{"w": "x", "s": 9, "e": 9}], "raw": ["x"],
                  "scenes": [dict(cfg["thumb"], type="thumb", s=0, e=1)]}
            (tmp / "tj.json").write_text(json.dumps(tj, ensure_ascii=False), encoding="utf-8")
            subprocess.run(["node", "kin.js", str(tmp / "tj.json"), str(tmp / "tf")], cwd=ROOT / "kinetic", capture_output=True, text=True)
            fs = sorted((tmp / "tf").glob("f*.jpg"))
            thumb = fs[-1] if fs else None
        if dry or fake:
            keep = tmp.parent / f"{vid}_dry.mp4"
            shutil.copy(out, keep)
            contact_sheet(out, tmp.parent / f"{vid}_qa.jpg", d)
            if thumb:
                shutil.copy(thumb, tmp.parent / f"{vid}_thumb.jpg")
            log(f"--dry/--fake: nichts gespeichert, Probe unter {keep}")
            return 0
        dest = config.DATA / "videos" / f"{vid}.mp4"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(out, dest)
        contact_sheet(out, config.DATA / "qa" / f"{vid}.jpg", d)
        th = config.DATA / "thumbs" / f"{vid}.jpg"
        th.parent.mkdir(parents=True, exist_ok=True)
        if thumb:
            shutil.copy(thumb, th)
        else:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "1.0", "-i", str(out), "-frames:v", "1", "-q:v", "3", str(th)], check=True)
    chapters = []
    for bi, b in enumerate(cfg["blocks"]):
        name = b.get("chapter") or ("Einleitung" if bi == 0 else None)
        if name:
            chapters.append((starts[bi], name))
    ch = "\n".join(f"{fmt_ts(s)} {n}" for s, n in chapters)
    text = cfg["text_youtube"].replace("{KAPITEL}", "KAPITEL\n" + ch)
    inv = inventory._load("inventory.json", {"videos": []})
    inv["videos"] = [x for x in inv["videos"] if x["id"] != vid]
    inv["videos"].append({
        "id": vid, "format": "lang", "status": cfg.get("status", "ready"), "created": inventory.now().isoformat(), "source": "kinetic",
        "topic": cfg["topic"], "hook_type": cfg.get("hook_type", "Kinetic-Doku"), "series": None, "episode": None, "duration": round(d, 1),
        "video_url": f"{config.RAW_BASE}/videos/{vid}.mp4", "title_tiktok": "", "title_youtube": cfg["title_youtube"],
        "text_tiktok": "", "text_youtube": text, "scenes": len(scenes), "buffer": {}, "group": cfg.get("group", "lang-kin"),
        "sources": cfg.get("sources", [])})
    inventory._save("inventory.json", inv)
    log(inventory.sync(f"{vid}: Kinetic-Langvideo {cfg['topic']} ({d / 60:.1f} min)"))
    return 0


def convert(src: str, dest: str) -> int:
    """Doku-Inhalt (content_doku) in Kinetic-Szenen umsetzen: gleicher Sprechtext und gleiche Sprachdateien, neues Aussehen."""
    d = json.loads(Path(src).read_text(encoding="utf-8"))

    def num(v):
        m = re.match(r"^\s*(\d[\d\s.,]*)", str(v))
        if not m:
            return None
        t = m.group(1).strip().replace(" ", "")
        if "," in t:
            t = t.replace(".", "").replace(",", ".")
        elif re.fullmatch(r"\d{1,3}(\.\d{3})+", t):
            t = t.replace(".", "")
        try:
            return float(t)
        except ValueError:
            return None

    def cut(t, n=62):
        t = t.strip()
        return t if len(t) <= n else t[:n].rsplit(" ", 1)[0]

    out_blocks = []
    for b in d["blocks"]:
        sc = []
        for s in b["scenes"]:
            ty, w = s["type"], s.get("w", 1)
            if ty == "titel":
                sc.append({"type": "hook", "text": cut(s["title"].upper()), "emoji": d.get("emoji", "🚀"), "w": w})
            elif ty == "kapitel":
                sc.append({"type": "kapitel", "nr": s["nr"], "title": s["title"], "w": w})
            elif ty == "zahl":
                n = num(s["value"])
                z = {"type": "zahl", "value": n if n is not None else 0, "text": str(s["value"]), "unit": (s.get("unit") or "").upper(), "label": s["label"], "w": w}
                if n is None or not re.fullmatch(r"[\d\s.,]+", str(s["value"])):
                    z["static"] = True
                sc.append(z)
            elif ty == "liste":
                sc.append({"type": "karten", "title": (s.get("title") or "").upper(), "items": s["items"][:6], "w": w})
            elif ty == "vergleich":
                sc.append({"type": "balken", "title": (s.get("title") or "").upper(),
                           "items": [{"name": x["label"], "value": x["value"], "text": x.get("text") or f"{x['value']} {s.get('unit', '')}".strip()} for x in s["bars"]], "w": w})
            elif ty == "zeitleiste":
                sc.append({"type": "zeit", "title": (s.get("title") or "").upper(), "events": s["events"], "focus": s.get("focus"), "w": w})
            elif ty == "fakt":
                sc.append({"type": "zitat", "text": s["text"], "hl": "\\d", "w": w})
            elif ty == "frage":
                sc.append({"type": "frage", "text": s["question"].upper(), "options": [o for o in s["options"]][:3], "w": w})
        nb = {k: v for k, v in b.items() if k != "scenes"}
        nb["scenes"] = sc
        out_blocks.append(nb)
    cfg = {k: d[k] for k in ("id", "topic", "hook_type", "group", "title_youtube", "text_youtube", "sources", "thumb", "status") if k in d}
    cfg.update({"theme": d.get("theme", "neon"), "music": "wissen", "hl": "\\d|lichttag|voyager", "group": "lang-kin", "blocks": out_blocks})
    Path(dest).write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{dest}: {len(out_blocks)} Bloecke umgesetzt")
    return 0


def main(argv: list) -> int:
    if argv and argv[0] == "convert" and len(argv) == 3:
        return convert(argv[1], argv[2])
    if argv and argv[0] == "check":
        bad = 0
        for a in argv[1:]:
            c = json.loads(Path(a).read_text(encoding="utf-8"))
            e = check_long(c) if "blocks" in c else check_content(c)
            print(a + ": " + ("ok" if not e else "; ".join(e)))
            bad += bool(e)
        return 1 if bad else 0
    if argv and argv[0] == "build" and "--id" in argv:
        vid = argv[argv.index("--id") + 1]
        c = json.loads((ROOT / "content_kin" / f"{vid}.json").read_text(encoding="utf-8"))
        return (build_long if "blocks" in c else build)(vid, "--dry" in argv, "--fake" in argv)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
