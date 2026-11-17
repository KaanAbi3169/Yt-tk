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
    s = _load("schedule.json", {})
    return {fmt: s.get(fmt, f["slot"]) for fmt, f in config.FORMATS.items()}


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


def plan(day: str) -> list:
    """Liefert die Posts fuer einen Tag. Pro Format hoechstens ein Video, Serien in Reihenfolge."""
    d = date.fromisoformat(day)
    data = _load("inventory.json", {"videos": []})
    sch = schedule()
    posts = []
    done_groups = set()
    used = set()  # Videos, die dieser Plan schon vergeben hat (nie zweimal am selben Tag)
    for fmt, f in config.FORMATS.items():
        group = tuple(config.rotation_group(fmt))
        if group in done_groups:
            continue
        if not any(config.runs_on(g, d) for g in group):
            continue  # Format heute nicht dran (Wochentag)
        slot_prefix = f"{day}T{sch[fmt]}"
        if any((v["format"] in group and (v.get("due") or "").startswith(day)) or (v.get("due") or "").startswith(slot_prefix)
               for v in data["videos"]):
            done_groups.add(group)
            continue  # Sendeplatz heute schon belegt -> nie doppelt
        # Format des Tages zuerst; ist dafuer nichts da, springt das andere Format der Gruppe ein.
        order = sorted(group, key=lambda g: not config.runs_on(g, d))
        v = None
        for g in order:
            ready = sorted((x for x in data["videos"] if x["format"] == g and x["status"] == "ready" and x["id"] not in used),
                           key=lambda x: x["id"])
            if not ready:  # Reserve aus Google Drive (nur wenn kein neues Video bereitliegt)
                ready = sorted((x for x in data["videos"] if x["format"] == g and x["status"] == "backup" and x["id"] not in used),
                               key=lambda x: x["id"])
            if ready:
                v, fmt, f = ready[0], g, config.FORMATS[g]
                break
        if v is None and f.get("fallback"):  # kein eigenes Video fertig: Vorrat eines anderen Formats nehmen
            fb = f["fallback"]
            cand = sorted((x for x in data["videos"] if x["format"] == fb and x["status"] == "ready" and x["id"] not in used),
                          key=lambda x: x["id"]) or \
                sorted((x for x in data["videos"] if x["format"] == fb and x["status"] == "backup" and x.get("title_tiktok")
                        and x["id"] not in used), key=lambda x: x["id"])
            if cand:
                v = cand[0]
        done_groups.add(group)
        if v is None:
            continue
        used.add(v["id"])
        if v.get("source") == "drive" and not v.get("title_tiktok"):
            posts.append({"id": v["id"], "format": fmt, "needs_texts": True, "topic": v["topic"],
                          "drive_id": v["drive_id"], "drive_title": v["drive_title"],
                          "dueAt": datetime(d.year, d.month, d.day, *map(int, sch[fmt].split(":")), tzinfo=TZ).isoformat(),
                          "hint": "Erst Drive-Datei freigeben (anyoneWithLink) und Texte schreiben: "
                                  "inventory texts <ID> <json>, dann plan erneut ausfuehren."})
            continue
        hh, mm = map(int, sch[fmt].split(":"))
        due = datetime(d.year, d.month, d.day, hh, mm, tzinfo=TZ)
        if due <= now() + timedelta(minutes=20):
            continue
        entry = {"id": v["id"], "format": fmt, "dueAt": due.isoformat(), "video_url": v["video_url"],
                 "platforms": config.platforms(fmt), "long_video": f.get("orientation") == "landscape"}
        if "tiktok" in config.platforms(fmt):
            entry["tiktok"] = {"channelId": config.BUFFER["tiktok_channel_id"], "text": v["text_tiktok"],
                               "metadata": {"tiktok": {"title": v["title_tiktok"], "isAiGenerated": True}}}
        if "youtube" in config.platforms(fmt):
            entry["youtube"] = {"channelId": config.BUFFER["youtube_channel_id"], "text": v["text_youtube"],
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


def perf(vid: str, platform: str, window: str, kv: list) -> None:
    data = _load("performance.json", {"posts": []})
    vals = {k: int(float(x)) for k, x in (i.split("=", 1) for i in kv)}
    inv = {v["id"]: v for v in _load("inventory.json", {"videos": []})["videos"]}
    v = inv.get(vid, {})
    rec = next((p for p in data["posts"] if p["id"] == vid and p["platform"] == platform), None)
    if not rec:
        rec = {"id": vid, "platform": platform, "format": v.get("format"), "topic": v.get("topic"),
               "hook_type": v.get("hook_type"), "due": v.get("due"), "duration": v.get("duration")}
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

    # Montags: Zeitplan anhand der Slot-Werte anpassen (nur mit genug Daten, max. +-2 h pro Woche)
    if now().weekday() == 0:
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


def sync(msg: str) -> str:
    _git("add", "-A")
    if not _git("status", "--porcelain"):
        return "nichts zu committen"
    _git("commit", "-q", "-m", msg)
    for i in range(4):
        r = subprocess.run(["git", "push", "-q", "origin", f"HEAD:{config.MEDIA_BRANCH}"], cwd=config.DATA,
                           capture_output=True, text=True)
        if r.returncode == 0:
            return "gepusht"
        if "rejected" in r.stderr or "fetch first" in r.stderr:
            _git("pull", "-q", "--rebase", "origin", config.MEDIA_BRANCH, check=False)
        time.sleep(2 ** (i + 1))
    raise RuntimeError("Push nach 4 Versuchen fehlgeschlagen: " + r.stderr)


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
    _git("add", "-A")
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
