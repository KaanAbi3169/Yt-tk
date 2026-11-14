"""Vorrat, Planung, Statistik und Datenablage (Branch "media").

    python -m yt_tk.inventory setup                 # media-Worktree anlegen/aktualisieren
    python -m yt_tk.inventory status                # Vorrat, Budget, naechste IDs (JSON)
    python -m yt_tk.inventory register <ID>         # fertiges Video in den Vorrat
    python -m yt_tk.inventory plan <YYYY-MM-DD>     # Buffer-Posts fuer den Tag (JSON)
    python -m yt_tk.inventory mark <ID> --tiktok <postId> --youtube <postId> --due <ISO>
    python -m yt_tk.inventory fail <ID> "<Grund>"
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


def status() -> dict:
    inv = _load("inventory.json", {"videos": []})["videos"]
    out = {"now": now().isoformat(), "paused": config.paused(), "formats": {}, "schedule": schedule()}
    for fmt, f in config.FORMATS.items():
        vids = [v for v in inv if v["format"] == fmt]
        ready = [v["id"] for v in vids if v["status"] == "ready"]
        nums = [int(v["id"][1:]) for v in vids] + _content_ids(f["prefix"])
        out["formats"][fmt] = {
            "ready": ready,
            "days_covered": len(ready),
            # Horror: immer nur die naechste Folge (A/B-Abstimmung muss vorher laufen)
            "needs_production": (1 if not ready else 0) if fmt == "horror"
            else max(0, config.INVENTORY_DAYS + 1 - len(ready)),
            "next_id": f"{f['prefix']}{(max(nums) if nums else 0) + 1:03d}",
            "recent_topics": [v.get("topic") for v in vids][-30:],
        }
    out["series"] = _load("series.json", {})
    try:
        from . import tts
        out["elevenlabs"] = tts.budget_status()
    except Exception as e:  # Budget-Abfrage darf den Status nicht verhindern
        out["elevenlabs"] = {"error": str(e)}
    return out


def _content_ids(prefix: str) -> list:
    c = config.DATA / "content"
    return [int(p.name[1:]) for p in c.glob(f"{prefix}[0-9][0-9][0-9]")] if c.exists() else []


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
        "title_tiktok": s["title_tiktok"], "title_youtube": s["title_youtube"],
        "text_tiktok": s["text_tiktok"], "text_youtube": s["text_youtube"],
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
    for fmt, f in config.FORMATS.items():
        if any(v["format"] == fmt and (v.get("due") or "").startswith(day) for v in data["videos"]):
            continue  # heute schon geplant -> nie doppelt
        ready = sorted((v for v in data["videos"] if v["format"] == fmt and v["status"] == "ready"),
                       key=lambda v: v["id"])
        if not ready:
            continue
        v = ready[0]
        hh, mm = map(int, sch[fmt].split(":"))
        due = datetime(d.year, d.month, d.day, hh, mm, tzinfo=TZ)
        if due <= now() + timedelta(minutes=20):
            continue
        posts.append({
            "id": v["id"], "format": fmt, "dueAt": due.isoformat(), "video_url": v["video_url"],
            "tiktok": {"channelId": config.BUFFER["tiktok_channel_id"], "text": v["text_tiktok"],
                       "metadata": {"tiktok": {"title": v["title_tiktok"], "isAiGenerated": True}}},
            "youtube": {"channelId": config.BUFFER["youtube_channel_id"], "text": v["text_youtube"],
                        "metadata": {"youtube": {"title": v["title_youtube"], "categoryId": f["youtube_category"],
                                                 "madeForKids": False, "privacy": "public",
                                                 "isAiGenerated": True, "notifySubscribers": True}}},
        })
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
        for fmt in config.FORMATS:
            cands = {}
            for p in posts:
                if p["format"] != fmt or not p.get("due") or score(p) is None:
                    continue
                h = datetime.fromisoformat(p["due"]).astimezone(TZ).hour
                cands.setdefault(h, []).append(score(p))
            good = {h: sum(v) / len(v) for h, v in cands.items() if len(v) >= 3}
            if len(good) >= 2:
                best = max(good, key=good.get)
                cur = int(sch[fmt].split(":")[0])
                new = cur + max(-2, min(2, best - cur))
                sch[fmt] = f"{new:02d}:00"
        hours = sorted(int(v.split(":")[0]) for v in sch.values())
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
