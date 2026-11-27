"""Vorrat, Planung, Statistik und Datenablage (Branch "media").

    python -m yt_tk.inventory setup                 # media-Worktree anlegen/aktualisieren
    python -m yt_tk.inventory status                # Vorrat, Budget, naechste IDs (JSON)
    python -m yt_tk.inventory register <ID>         # fertiges Video in den Vorrat
    python -m yt_tk.inventory plan <YYYY-MM-DD>     # Buffer-Posts fuer den Tag (JSON)
    python -m yt_tk.inventory mark <ID> --tiktok <postId> --youtube <postId> --due <ISO>
    python -m yt_tk.inventory fail <ID> "<Grund>"
    python -m yt_tk.inventory import-drive <liste.json>   # Drive-Videos als Reserve (Status backup)
    python -m yt_tk.inventory texts <ID> <texte.json>     # Titel/Texte fuer ein Reserve-Video setzen
    python -m yt_tk.inventory perf <ID> <tiktok|youtube> <24h|7d> views=.. likes=.. comments=.. shares=.. [followers=..]
    python -m yt_tk.inventory due-metrics           # welche Posts brauchen jetzt 24h/7d-Zahlen
    python -m yt_tk.inventory learn                 # Auswertung -> data/insights.json (+ montags Zeitplan)
    python -m yt_tk.inventory sync "<Nachricht>"    # Daten committen und pushen (mit Wiederholung)
    python -m yt_tk.inventory compact               # alte Videos entfernen, media-History zusammenfassen
"""
import json
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config

TZ = ZoneInfo(config.TIMEZONE)


# ---------- Hilfen ----------
def _p(name: str) -> Path:
    return config.DATA / "data" / name


def _load(name: str, default):
    p = _p(name)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def _save(name: str, obj) -> None:
    p = _p(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _git(*args, cwd=None, check=True):
    r = subprocess.run(["git", *args], cwd=cwd or config.DATA, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout.strip()


def now() -> datetime:
    return datetime.now(TZ)


def schedule() -> dict:
    """Erster Sendeplatz je Format an einem Wochentag (fester Sendeplan, config.SENDEPLAN)."""
    monday = date(2026, 1, 5)
    return {fmt: min(config.slot_times(fmt, monday).values() or [f["slot"]]) for fmt, f in config.FORMATS.items()}


# ---------- Befehle ----------
def setup() -> str:
    d = config.DATA
    if (d / ".git").exists():
        _git("fetch", "origin", config.MEDIA_BRANCH, check=False)
        _git("reset", "--hard", f"origin/{config.MEDIA_BRANCH}", check=False)
        return f"aktualisiert: {d}"
    _git("fetch", "origin", f"{config.MEDIA_BRANCH}:{config.MEDIA_BRANCH}", cwd=config.ROOT, check=False)
    _git("worktree", "add", str(d), config.MEDIA_BRANCH, cwd=config.ROOT)
    return f"angelegt: {d}"


def budget_mode(b: dict) -> str:
    """normal: alles produzieren | spar: Wissen kommt aus der Drive-Reserve |
    pause: ElevenLabs-Kontingent aufgebraucht -> keine Produktion bis zum Reset (laeuft danach automatisch weiter)."""
    if "remaining" not in b:
        return "normal"
    if b["remaining"] < 1500:
        return "pause"
    if b["per_day_available"] < 2600:
        return "spar"
    return "normal"


def status() -> dict:
    inv = _load("inventory.json", {"videos": []})["videos"]
    out = {"now": now().isoformat(), "paused": config.paused(), "formats": {}, "schedule": schedule()}
    try:
        from . import tts
        out["elevenlabs"] = tts.budget_status()
    except Exception as e:  # Budget-Abfrage darf den Status nicht verhindern
        out["elevenlabs"] = {"error": str(e)}
    mode = budget_mode(out["elevenlabs"])
    out["budget_mode"] = mode
    for fmt, f in config.FORMATS.items():
        vids = [v for v in inv if v["format"] == fmt]
        ready = [v["id"] for v in vids if v["status"] == "ready"]
        backup = [v["id"] for v in vids if v["status"] == "backup"]
        nums = [int(v["id"][1:]) for v in vids if v["id"].startswith(f["prefix"])] + _content_ids(f["prefix"])
        if fmt == "horror":  # immer nur die naechste Folge (A/B-Abstimmung muss vorher laufen)
            need = 1 if not ready else 0
        elif "weekdays" in f:  # z. B. lange Videos: Vorrat fuer die naechsten Sendetage
            need = max(0, len(f["weekdays"]) - len(ready))
        else:  # Formate im Wechsel brauchen anteilig weniger Vorrat
            share = len(config.rotation_group(fmt))
            need = max(0, -(-(config.INVENTORY_DAYS + 1) // share) - len(ready))
        if mode == "pause" or (mode == "spar" and fmt == "wissen" and backup):
            need = 0
        if fmt == "wissen" and len(backup) >= config.WISSEN_SKIP_RESERVE:
            need = 0  # genug Drive-Reserve: Wissen nicht neu produzieren (spart Claude-Limit und ElevenLabs)
        out["formats"][fmt] = {
            "ready": ready,
            "backup_drive": len(backup),
            "days_covered": (len(ready) + len(backup)) * len(config.rotation_group(fmt)),
            "runs_today": config.runs_on(fmt, now().date()),
            "needs_production": need,
            "next_id": f"{f['prefix']}{(max(nums) if nums else 0) + 1:03d}",
            "recent_topics": [v.get("topic") for v in vids if v["status"] != "backup"][-30:],
        }
    out["series"] = _load("series.json", {})
    return out


def import_drive(path: str) -> int:
    """Fertige Videos aus dem Drive-Ordner 'Auto-Posting' als Reserve (Status backup) aufnehmen.
    Datei: JSON-Liste [{"drive_id": "...", "title": "V033_Brot_lagern.mp4", "fmt": "wissen"}]."""
    data = _load("inventory.json", {"videos": []})
    known = {v.get("drive_id") for v in data["videos"]}
    n = 0
    for f in json.loads(Path(path).read_text(encoding="utf-8")):
        if f["drive_id"] in known:
            continue
        stem = Path(f["title"]).stem
        num, _, rest = stem.partition("_")
        data["videos"].append({
            "id": f"D{num[1:]}", "format": f.get("fmt", "wissen"), "status": "backup", "source": "drive",
            "drive_id": f["drive_id"], "drive_title": f["title"], "topic": rest.replace("_", " "),
            "hook_type": "drive-reserve", "created": now().isoformat(),
            "video_url": f"https://drive.google.com/uc?export=download&id={f['drive_id']}", "buffer": {},
        })
        n += 1
    _save("inventory.json", data)
    return n


def set_texts(vid: str, path: str) -> None:
    t = json.loads(Path(path).read_text(encoding="utf-8"))
    data = _load("inventory.json", {"videos": []})
    for v in data["videos"]:
        if v["id"] == vid:
            for k in ("title_tiktok", "title_youtube", "text_tiktok", "text_youtube", "topic"):
                if k in t:
                    v[k] = t[k]
    _save("inventory.json", data)


def _content_ids(prefix: str) -> list:
    c = config.DATA / "content"
    return [int(p.name[1:]) for p in c.glob(f"{prefix}[0-9][0-9][0-9]")] if c.exists() else []


def _with_chapters(text: str, build: dict) -> str:
    if "{KAPITEL}" not in text:
        return text
    lines = "\n".join(f"{t} {name}" for t, name in build.get("chapters", []))
    return text.replace("{KAPITEL}", "Kapitel:\n" + lines if lines else "")


def register(vid: str) -> dict:
    cdir = config.DATA / "content" / vid
    s = json.loads((cdir / "script.json").read_text(encoding="utf-8"))
    b = json.loads((cdir / "build.json").read_text(encoding="utf-8"))
    if not b.get("ok"):
        raise SystemExit(f"{vid}: QA nicht bestanden: {b.get('issues')}")
    if not (config.DATA / "videos" / f"{vid}.mp4").exists():
        raise SystemExit(f"{vid}: videos/{vid}.mp4 fehlt")
    data = _load("inventory.json", {"videos": []})
    if any(v["id"] == vid for v in data["videos"]):
        raise SystemExit(f"{vid} ist schon im Vorrat")
    entry = {
        "id": vid, "format": s["format"], "status": "ready", "created": now().isoformat(),
        "topic": s["topic"], "hook_type": s["hook_type"], "series": s.get("series"),
        "episode": s.get("episode"), "duration": b["duration"],
        "video_url": f"{config.RAW_BASE}/videos/{vid}.mp4",
        "title_tiktok": s.get("title_tiktok", ""), "title_youtube": s.get("title_youtube", ""),
        "text_tiktok": s.get("text_tiktok", ""), "text_youtube": _with_chapters(s.get("text_youtube", ""), b),
        "scenes": len(s["scenes"]), "buffer": {},
    }
    data["videos"].append(entry)
    _save("inventory.json", data)
    return entry


def pins_for(day: str) -> list:
    """Festgesetzte Posts (data/pins.json): {"pins": [{"id": "T001", "day": "2026-11-19", "time": "10:00", "platform": "tiktok"}]}.
    Ein Pin belegt den ganzen Sendeplatz (alle Plattformen), die Planung setzt dort kein anderes Video ein."""
    return [p for p in _load("pins.json", {"pins": []}).get("pins", []) if p.get("day") == day]


def _entry(v: dict, fmt: str, due: datetime, platforms: list) -> dict:
    f = config.FORMATS[fmt]
    entry = {"id": v["id"], "format": fmt, "dueAt": due.isoformat(), "video_url": v["video_url"],
             "platforms": platforms, "long_video": f.get("orientation") == "landscape"}
    if "tiktok" in platforms:
        entry["tiktok"] = {"channelId": config.BUFFER["tiktok_channel_id"], "text": v["text_tiktok"],
                           "metadata": {"tiktok": {"title": v["title_tiktok"], "isAiGenerated": True}}}
    if "youtube" in platforms:
        entry["youtube"] = {"channelId": config.BUFFER["youtube_channel_id"], "text": v["text_youtube"],
                            "metadata": {"youtube": {"title": v["title_youtube"], "categoryId": f["youtube_category"],
                                                     "madeForKids": False, "privacy": "public",
                                                     "isAiGenerated": True, "notifySubscribers": True}}}
    return entry


def pinned_posts(day: str) -> list:
    data = _load("inventory.json", {"videos": []})
    byid = {v["id"]: v for v in data["videos"]}
    out = []
    for p in pins_for(day):
        v = byid.get(p["id"])
        if not v or not v.get("video_url") or v["status"] in ("failed", "deleted", "archived"):
            continue
        hh, mm = map(int, p["time"].split(":"))
        d = date.fromisoformat(day)
        due = datetime(d.year, d.month, d.day, hh, mm, tzinfo=TZ)
        if due <= now() + timedelta(minutes=20):
            continue
        e = _entry(v, v["format"], due, [p["platform"]])
        e["pin"] = True
        out.append(e)
    return out


def _prio_key(which: str = "order"):
    """V-033: Reihenfolge der Vorrats-Videos aus data/priority.json. "order" gilt fuer den 10:00-Slot (Test-Gruppe, Winterthemen),
    "prime" fuer den 16:00-Slot (beste Zeit, staerkste Gruppen). Nicht Gelistete folgen nach ID."""
    pr = _load("priority.json", {"order": [], "prime": []})
    order = {vid: i for i, vid in enumerate(pr.get(which, []))}
    other = {vid: i for i, vid in enumerate(pr.get("order" if which == "prime" else "prime", []))}
    return lambda x: (order.get(x["id"], 10_000), other.get(x["id"], 10_000), x["id"])


def long_link_line(data: dict, vid: str) -> str:
    """V-031: Zeile fuer die YouTube-Beschreibung eines Short, der Teil eines veroeffentlichten Zusammenschnitt-Langvideos ist.
    Nur wenn das Langvideo einen oeffentlichen Link hat (public_url), sonst leer (nie ein toter Link)."""
    for lv in data["videos"]:
        if lv.get("format") == "lang" and lv.get("public_url") and vid in (lv.get("parts") or []):
            return f"Das ganze Video ({lv.get('topic', 'Zusammenschnitt')}, {len(lv['parts'])} Teile): {lv['public_url']}"
    return ""


def with_long_link(text: str, line: str) -> str:
    if not line or line in text:
        return text
    marker = "Stimme und Grafiken mit KI erstellt"
    if marker in text:  # vor dem KI-Hinweis, Hashtags bleiben am Schluss
        return text.replace(marker, line + "\n\n" + marker, 1)
    return text.rstrip() + "\n\n" + line


def plan(day: str) -> list:
    """Liefert die Posts fuer einen Tag. Pro Format hoechstens ein Video, Serien in Reihenfolge."""
    d = date.fromisoformat(day)
    data = _load("inventory.json", {"videos": []})
    posts = []
    prio, prime = _prio_key("order"), _prio_key("prime")
    pin_times = {p["time"] for p in pins_for(day)}  # durch Pins belegte Sendeplaetze
    done_groups = set()
    used = set()  # Videos, die dieser Plan schon vergeben hat (nie zweimal am selben Tag)
    for fmt, f in config.FORMATS.items():
        group = tuple(config.rotation_group(fmt))
        if group in done_groups:
            continue
        if not any(config.runs_on(g, d) for g in group):
            continue  # Format heute nicht dran (Wochentag)
        times = config.slot_times(group[0], d) if len(group) > 1 else config.slot_times(fmt, d)
        if not times:
            done_groups.add(group)
            continue  # Format laeuft an diesem Wochentag nicht (Sendeplan)
        if config.skips_on_long_day(fmt) and any(
                x["format"] == "lang" and (x.get("due") or "").startswith(day) and x["status"] in ("scheduled", "posted", "ready")
                for x in data["videos"]):
            done_groups.add(group)
            continue  # Langvideo-Tag: nur ein Kurzvideo (YouTube-Tageslimit)
        primary = min(times.values())  # erster Sendeplatz des Tages (Belegung und Pins)
        if primary in pin_times:
            done_groups.add(group)
            continue  # Sendeplatz ist durch einen Pin belegt
        slot_prefix = f"{day}T{primary}"
        if any((v["format"] in group and (v.get("due") or "").startswith(day)) or (v.get("due") or "").startswith(slot_prefix)
               for v in data["videos"]):
            done_groups.add(group)
            continue  # Sendeplatz heute schon belegt -> nie doppelt
        # Format des Tages zuerst; ist dafuer nichts da, springt das andere Format der Gruppe ein.
        order = sorted(group, key=lambda g: not config.runs_on(g, d))
        v = None
        for g in order:
            ready = sorted((x for x in data["videos"] if x["format"] == g and x["status"] == "ready" and x["id"] not in used),
                           key=prio)
            if not ready:  # Reserve aus Google Drive (nur wenn kein neues Video bereitliegt)
                ready = sorted((x for x in data["videos"] if x["format"] == g and x["status"] == "backup" and x["id"] not in used),
                               key=prio)
            if ready:
                v, fmt, f = ready[0], g, config.FORMATS[g]
                break
        if v is None and f.get("fallback"):  # kein eigenes Video fertig: Vorrat eines anderen Formats nehmen
            fb = f["fallback"]
            cand = sorted((x for x in data["videos"] if x["format"] == fb and x["status"] == "ready" and x["id"] not in used),
                          key=prime) or \
                sorted((x for x in data["videos"] if x["format"] == fb and x["status"] == "backup" and x.get("title_tiktok")
                        and x["id"] not in used), key=prime)
            if cand:
                v = cand[0]
        done_groups.add(group)
        if v is None:
            continue
        used.add(v["id"])
        if v.get("source") == "drive" and not v.get("title_tiktok"):
            posts.append({"id": v["id"], "format": fmt, "needs_texts": True, "topic": v["topic"],
                          "drive_id": v["drive_id"], "drive_title": v["drive_title"],
                          "dueAt": datetime(d.year, d.month, d.day, *map(int, primary.split(":")), tzinfo=TZ).isoformat(),
                          "hint": "Erst Drive-Datei freigeben (anyoneWithLink) und Texte schreiben: "
                                  "inventory texts <ID> <json>, dann plan erneut ausfuehren."})
            continue
        times = config.slot_times(fmt, d) or times
        dues = {pf: datetime(d.year, d.month, d.day, *map(int, t.split(":")), tzinfo=TZ) for pf, t in times.items()}
        due = min(dues.values())
        if due <= now() + timedelta(minutes=20):
            continue
        entry = {"id": v["id"], "format": fmt, "dueAt": due.isoformat(), "video_url": v["video_url"],
                 "platforms": config.platforms(fmt), "long_video": f.get("orientation") == "landscape",
                 "due_by_platform": {pf: t.isoformat() for pf, t in dues.items()}}
        if "tiktok" in config.platforms(fmt):
            entry["tiktok"] = {"channelId": config.BUFFER["tiktok_channel_id"], "text": v["text_tiktok"],
                               "metadata": {"tiktok": {"title": v["title_tiktok"], "isAiGenerated": True}}}
        if "youtube" in config.platforms(fmt):
            yt_text = v["text_youtube"] if entry["long_video"] else with_long_link(v["text_youtube"], long_link_line(data, v["id"]))
            entry["youtube"] = {"channelId": config.BUFFER["youtube_channel_id"], "text": yt_text,
                                "metadata": {"youtube": {"title": v["title_youtube"],
                                                         "categoryId": f["youtube_category"],
                                                         "madeForKids": False, "privacy": "public",
                                                         "isAiGenerated": True, "notifySubscribers": True}}}
        posts.append(entry)
    return posts


def mark(vid: str, tiktok: str, youtube: str, due: str, status_: str = "scheduled") -> None:
    data = _load("inventory.json", {"videos": []})
    for v in data["videos"]:
        if v["id"] == vid:
            v["status"] = status_
            v["due"] = due
            if tiktok:
                v["buffer"]["tiktok"] = tiktok
            if youtube:
                v["buffer"]["youtube"] = youtube
            _save("inventory.json", data)
            return
    raise SystemExit(f"{vid} nicht im Vorrat")


def fail(vid: str, reason: str) -> None:
    data = _load("inventory.json", {"videos": []})
    for v in data["videos"]:
        if v["id"] == vid:
            v.setdefault("errors", []).append({"at": now().isoformat(), "reason": reason})
            if v["status"] == "backup":  # Reserve-Video nicht nutzbar (z. B. Thema schon online)
                v["status"] = "skipped"
    _save("inventory.json", data)


def repair_failed(history: dict, retry_max: int = 2) -> list:
    """Selbstheilung (Optimierungspaket 23.11.2026): Ein Buffer-Post mit Status "error" (z. B. YouTube "daily posting limit") wurde nie
    veroeffentlicht. Das Video geht auf "ready" zurueck, nur die fehlende Plattform wird neu eingeplant (der Doppelschutz im Uploader
    findet den gesendeten Post der anderen Plattform). Hoechstens retry_max Versuche je Video und Plattform, danach bleibt es
    liegen und der Tagesbericht meldet es. history: {plattform: [Buffer-Posts]}. Liefert Meldungen."""
    data = _load("inventory.json", {"videos": []})
    msgs = []
    for v in data["videos"]:
        if v.get("status") not in ("scheduled", "posted") or not v.get("buffer"):
            continue
        for pf, pid in list(v["buffer"].items()):
            post = next((x for x in history.get(pf, []) if x.get("id") == pid), None)
            if not post or post.get("status") != "error":
                continue
            n = v.setdefault("retries", {}).get(pf, 0)
            if n >= retry_max:
                msgs.append(f"{v['id']} {pf}: Fehler-Post {pid}, {n} Versuche erreicht - bleibt liegen (Tagesbericht)")
                continue
            v["retries"][pf] = n + 1
            # Messung fuer die Ursache des YouTube-Limits: wie viele YouTube-Uploads lagen in den 24 h vor diesem Slot?
            vor = 0
            try:
                t = datetime.fromisoformat(v["due"])
                for w in data["videos"]:
                    if w is v or not w.get("due") or w.get("status") not in ("scheduled", "posted"):
                        continue
                    if pf not in (w.get("buffer") or {}):
                        continue
                    dt = t - datetime.fromisoformat(w["due"])
                    vor += timedelta(0) <= dt <= timedelta(hours=24)
            except (KeyError, ValueError, TypeError):
                vor = None
            v.setdefault("errors", []).append({"at": now().isoformat(), "uploads_24h_davor": vor, "reason": f"{pf}: Buffer-Post {pid} Status error ({(post.get('error') or {}).get('message', '')[:80]})"})
            v["buffer"].pop(pf)
            v["due_failed"] = v.get("due")
            v["due"] = None
            v["status"] = "ready"
            msgs.append(f"{v['id']} {pf}: Fehler-Post {pid} - Video zurueck auf ready, Versuch {n + 1} von {retry_max}")
    if msgs:
        _save("inventory.json", data)
    return msgs


def perf(vid: str, platform: str, window: str, kv: list) -> None:
    data = _load("performance.json", {"posts": []})
    vals = {k: int(float(x)) for k, x in (i.split("=", 1) for i in kv)}
    inv = {v["id"]: v for v in _load("inventory.json", {"videos": []})["videos"]}
    v = inv.get(vid, {})
    rec = next((p for p in data["posts"] if p["id"] == vid and p["platform"] == platform), None)
    if not rec:
        rec = {"id": vid, "platform": platform, "format": v.get("format"), "topic": v.get("topic"),
               "hook_type": v.get("hook_type"), "due": v.get("due"), "duration": v.get("duration"),
               "group": v.get("group")}
        data["posts"].append(rec)
    rec[window] = {**vals, "at": now().isoformat()}
    _save("performance.json", data)


def due_metrics() -> list:
    inv = _load("inventory.json", {"videos": []})["videos"]
    perf_ = {(p["id"], p["platform"]): p for p in _load("performance.json", {"posts": []})["posts"]}
    out = []
    for v in inv:
        if v["status"] not in ("scheduled", "posted") or not v.get("due"):
            continue
        age = now() - datetime.fromisoformat(v["due"])
        for platform, pid in v.get("buffer", {}).items():
            rec = perf_.get((v["id"], platform), {})
            for window, hours in (("24h", 24), ("7d", 168)):
                if age >= timedelta(hours=hours) and window not in rec:
                    out.append({"id": v["id"], "platform": platform, "window": window, "buffer_post_id": pid})
    return out


def learn() -> dict:
    posts = _load("performance.json", {"posts": []})["posts"]

    def score(p):
        m = p.get("7d") or p.get("24h")
        if not m:
            return None
        return m.get("views", 0) + 20 * m.get("comments", 0) + 10 * m.get("shares", 0) + 5 * m.get("likes", 0)

    groups = {}
    for p in posts:
        sc = score(p)
        if sc is None:
            continue
        hour = datetime.fromisoformat(p["due"]).astimezone(TZ).strftime("%a %H") if p.get("due") else "?"
        for key in (f"format:{p['format']}", f"hook:{p.get('hook_type')}", f"slot:{p['platform']}:{hour}",
                    f"topic:{p.get('topic')}"):
            g = groups.setdefault(key, [])
            g.append(sc)
    insights = {k: {"n": len(v), "avg": round(sum(v) / len(v))} for k, v in groups.items()}
    ranked = sorted(insights.items(), key=lambda kv: -kv[1]["avg"])
    result = {"updated": now().isoformat(), "top": ranked[:15], "bottom": ranked[-10:], "all": insights}
    _save("insights.json", result)

    # Montags: Zeitplan anhand der Slot-Werte anpassen. AUS seit 27.11.2026: Der Inhaber hat einen festen Sendeplan
    # (config.SENDEPLAN) angewiesen; die Werte stehen weiter in insights.json, der Wochenreview schlaegt Aenderungen vor.
    if False and now().weekday() == 0:
        sch = schedule()
        groups_seen = set()
        for fmt in config.FORMATS:
            group = tuple(config.rotation_group(fmt))
            if group in groups_seen or "weekdays" in config.FORMATS[fmt]:
                continue  # lange Videos: Sendetage fest (zu wenig Daten fuer Automatik)
            groups_seen.add(group)
            cands = {}
            for p in posts:
                if p["format"] not in group or not p.get("due") or score(p) is None:
                    continue
                h = datetime.fromisoformat(p["due"]).astimezone(TZ).hour
                cands.setdefault(h, []).append(score(p))
            good = {h: sum(v) / len(v) for h, v in cands.items() if len(v) >= 3}
            if len(good) >= 2:
                best = max(good, key=good.get)
                cur = int(sch[fmt].split(":")[0])
                new = cur + max(-2, min(2, best - cur))
                for g in group:  # Formate im Wechsel behalten denselben Sendeplatz
                    sch[g] = f"{new:02d}:00"
        hours = sorted({int(sch[g].split(":")[0]) for g in config.FORMATS if "weekdays" not in config.FORMATS[g]})
        if all(b - a >= 2 for a, b in zip(hours, hours[1:])):  # mind. 2 h Abstand
            _save("schedule.json", sch)
            result["schedule"] = sch
    return result


def _merge3(base, up, mine):
    """Dreiwege-Zusammenfuehrung einer JSON-Datei mit genau einer Liste (inventory.json: videos, performance.json: posts).
    Aenderungen von 'mine' gegenueber 'base' werden auf 'up' (Stand auf dem Branch) angewendet, nichts anderes geht verloren."""
    out = dict(up)
    for k, lst in mine.items():
        if not isinstance(lst, list):
            if lst != base.get(k):
                out[k] = lst
            continue
        key = (lambda x: (x.get("id"), x.get("platform"))) if k == "posts" else (lambda x: x.get("id"))
        b_map = {key(x): x for x in base.get(k, [])}
        m_map = {key(x): x for x in lst}
        res = {key(x): x for x in up.get(k, [])}
        for kk, x in m_map.items():
            if kk not in b_map or x != b_map[kk]:
                res[kk] = x            # neu oder von uns geaendert
        for kk in b_map:
            if kk not in m_map:
                res.pop(kk, None)      # von uns entfernt
        order = [key(x) for x in up.get(k, [])] + [kk for kk in m_map if kk not in {key(x) for x in up.get(k, [])}]
        out[k] = [res[kk] for kk in order if kk in res]
    return out


def _resolve_conflicts() -> bool:
    """Loest Rebase-Konflikte in inventory.json und performance.json per Dreiwege-Zusammenfuehrung. False, wenn anderes in Konflikt ist."""
    files = [f for f in _git("diff", "--name-only", "--diff-filter=U", check=False).splitlines() if f]
    if not files:
        return False
    for f in files:
        if not (f.endswith("inventory.json") or f.endswith("performance.json")):
            return False
        try:
            base, up, mine = (json.loads(_git("show", f":{n}:{f}")) for n in (1, 2, 3))
        except (RuntimeError, ValueError):
            return False
        (config.DATA / f).write_text(json.dumps(_merge3(base, up, mine), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _git("add", "--sparse", f)
    return True


def sync(msg: str) -> str:
    """Committet und pusht den Daten-Branch. Bei gleichzeitigen Laeufen werden Konflikte in den JSON-Dateien zusammengefuehrt.
    Meldet nur dann 'gepusht', wenn der eigene Commit wirklich auf dem Branch liegt (frueher ging so ein Commit still verloren)."""
    _git("add", "--sparse", "-A")
    if not _git("status", "--porcelain"):
        return "nichts zu committen"
    _git("commit", "-q", "-m", msg)
    branch = config.MEDIA_BRANCH
    err = ""
    for i in range(5):
        r = subprocess.run(["git", "push", "-q", "origin", f"HEAD:{branch}"], cwd=config.DATA, capture_output=True, text=True)
        if r.returncode == 0:
            _git("fetch", "-q", "origin", branch, check=False)
            if subprocess.run(["git", "merge-base", "--is-ancestor", "HEAD", f"origin/{branch}"], cwd=config.DATA).returncode == 0:
                return "gepusht"
            err = "Push gemeldet, aber Commit nicht auf dem Branch"
        else:
            err = r.stderr.strip()
        if "rejected" in err or "fetch first" in err or "nicht auf dem Branch" in err:
            _git("fetch", "-q", "origin", branch)
            rb = subprocess.run(["git", "rebase", f"origin/{branch}"], cwd=config.DATA, capture_output=True, text=True)
            guard = 0
            while rb.returncode != 0 and guard < 5:
                guard += 1
                if not _resolve_conflicts():
                    _git("rebase", "--abort", check=False)
                    raise RuntimeError("Konflikt auf dem Daten-Branch, nicht automatisch loesbar: " + rb.stderr.strip()[-300:])
                rb = subprocess.run(["git", "-c", "core.editor=true", "rebase", "--continue"], cwd=config.DATA, capture_output=True, text=True)
        time.sleep(2 ** (i + 1))
    raise RuntimeError("Push nach 5 Versuchen fehlgeschlagen: " + err)


def compact(keep_days: int = 3) -> str:
    """Entfernt veroeffentlichte Videos aelter als keep_days und fasst die media-History zusammen,
    damit das Repo klein bleibt (Videos sind dann auf TikTok/YouTube, die Kopie wird nicht mehr gebraucht)."""
    data = _load("inventory.json", {"videos": []})
    removed = []
    for v in data["videos"]:
        if v["status"] in ("scheduled", "posted") and v.get("due"):
            if now() - datetime.fromisoformat(v["due"]) > timedelta(days=keep_days):
                f = config.DATA / "videos" / f"{v['id']}.mp4"
                if f.exists():
                    f.unlink()
                    removed.append(v["id"])
                for extra in ("voice.mp3",):
                    e = config.DATA / "content" / v["id"] / extra
                    if e.exists():
                        e.unlink()
    _git("add", "--sparse", "-A")
    tree = _git("write-tree")
    commit = _git("commit-tree", tree, "-m", f"media kompakt {now():%Y-%m-%d}")
    _git("reset", "-q", "--soft", commit)
    r = subprocess.run(["git", "push", "-q", "--force", "origin", f"HEAD:{config.MEDIA_BRANCH}"],
                       cwd=config.DATA, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("compact push: " + r.stderr)
    return f"entfernt: {removed}; History zusammengefasst"


def main(a):
    cmd = a[1] if len(a) > 1 else "status"
    if cmd == "setup":
        print(setup())
    elif cmd == "status":
        print(json.dumps(status(), indent=2, ensure_ascii=False))
    elif cmd == "register":
        print(json.dumps(register(a[2]), indent=2, ensure_ascii=False))
    elif cmd == "plan":
        if config.paused():
            print("[]")
            return
        print(json.dumps(plan(a[2]), indent=2, ensure_ascii=False))
    elif cmd == "mark":
        opts = dict(zip(a[3::2], a[4::2]))
        mark(a[2], opts.get("--tiktok", ""), opts.get("--youtube", ""), opts["--due"],
             opts.get("--status", "scheduled"))
        print("ok")
    elif cmd == "public-url":  # python -m yt_tk.inventory public-url L001 https://www.youtube.com/watch?v=...
        data = _load("inventory.json", {"videos": []})
        hit = [v for v in data["videos"] if v["id"] == a[2]]
        if not hit:
            raise SystemExit(f"{a[2]} nicht im Vorrat")
        hit[0]["public_url"] = a[3]
        _save("inventory.json", data)
        print("ok")
    elif cmd == "import-drive":
        print(f"{import_drive(a[2])} Reserve-Videos aufgenommen")
    elif cmd == "texts":
        set_texts(a[2], a[3])
        print("ok")
    elif cmd == "fail":
        fail(a[2], a[3])
        print("ok")
    elif cmd == "perf":
        perf(a[2], a[3], a[4], a[5:])
        print("ok")
    elif cmd == "due-metrics":
        print(json.dumps(due_metrics(), indent=2))
    elif cmd == "learn":
        print(json.dumps(learn(), indent=2, ensure_ascii=False))
    elif cmd == "sync":
        print(sync(a[2] if len(a) > 2 else "Daten-Update"))
    elif cmd == "compact":
        print(compact())
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv)
