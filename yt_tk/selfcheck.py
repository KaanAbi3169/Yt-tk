"""Taegliche Selbstpruefung des Systems (ohne Claude): findet Fehler, bevor sie Posts kosten.

    python -m yt_tk.selfcheck            # prueft Code und Inventar, schreibt data/reports/selfcheck-<Tag>.md
    python -m yt_tk.selfcheck --dry      # nur anzeigen

Ergebnis je Pruefung: OK, WARN oder FEHLER. Exit 1 nur bei FEHLER. Die Claude-Routine liest den Bericht jeden Morgen,
behebt Fehler (Stufe A, mit Dry-Run) und schlaegt Optimierungen vor (docs/ROUTINE_CODEREVIEW.md im Repo passiv-einkommen)."""
import importlib
import pkgutil
import sys
from datetime import datetime, timedelta

from . import inventory, textcheck

R = []  # (Stufe, Text)


def add(level: str, msg: str) -> None:
    R.append((level, msg))


def check_modules() -> None:
    import yt_tk
    bad = []
    for m in pkgutil.iter_modules(yt_tk.__path__):
        try:
            importlib.import_module(f"yt_tk.{m.name}")
        except Exception as e:
            bad.append(f"{m.name}: {type(e).__name__} {str(e)[:80]}")
    add("FEHLER" if bad else "OK", "Module importierbar" if not bad else "Importfehler: " + "; ".join(bad))


def check_inventory(inv: list) -> None:
    ids = [v["id"] for v in inv]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    add("FEHLER" if dup else "OK", f"IDs eindeutig ({len(ids)} Videos)" if not dup else f"Doppelte IDs: {dup}")
    miss = []
    for v in inv:
        st = v["status"]
        if st in ("scheduled", "posted") and not (v.get("due") and v.get("buffer")):
            miss.append(f"{v['id']} ohne due/buffer")
        if st in ("ready", "backup") and not v.get("video_url"):
            miss.append(f"{v['id']} ohne video_url")
    add("FEHLER" if miss else "OK", "Pflichtfelder vorhanden" if not miss else "Pflichtfelder fehlen: " + "; ".join(miss[:6]))
    bad = []
    for v in inv:
        if v["status"] in ("ready", "backup") and v["format"] != "lang":
            t = {k: v.get(k) for k in ("title_tiktok", "title_youtube", "text_tiktok", "text_youtube")}
            if not all(t.values()):
                bad.append(f"{v['id']} Texte fehlen")
            else:
                e = textcheck.check(t)
                if e:
                    bad.append(f"{v['id']} {e[0]}")
    add("WARN" if bad else "OK", "Texte der Shorts regelkonform" if not bad else f"{len(bad)} Videos mit Textproblem: " + "; ".join(bad[:5]))
    longs = [v for v in inv if v["format"] == "lang" and v["status"] in ("ready", "scheduled")]
    short_long = [v["id"] for v in longs if (v.get("duration") or 0) < 600]
    add("FEHLER" if short_long else "OK", f"Langvideos mindestens 10 Minuten ({len(longs)})" if not short_long else f"Langvideo unter 10 Minuten: {short_long}")


def check_plan(inv_ok: bool) -> None:
    today = datetime.now(inventory.TZ).date()
    problems, n = [], 0
    for k in range(0, 4):
        day = (today + timedelta(days=k)).isoformat()
        try:
            posts = inventory.plan(day)
        except Exception as e:
            problems.append(f"{day}: plan() Fehler {type(e).__name__} {str(e)[:60]}")
            continue
        n += len(posts)
        ids = [p["id"] for p in posts]
        if len(ids) != len(set(ids)):
            problems.append(f"{day}: dasselbe Video zweimal geplant")
        slots = [p["dueAt"] for p in posts]
        if len(slots) != len(set(slots)):
            problems.append(f"{day}: zwei Posts im selben Slot")
        for p in posts:
            if p.get("needs_texts"):
                problems.append(f"{day}: {p['id']} braucht Texte")
    add("FEHLER" if problems else "OK", f"Plan der naechsten 4 Tage stimmig ({n} Posts)" if not problems else "Plan: " + "; ".join(problems))


def check_stock(inv: list) -> None:
    usable = [v for v in inv if v["format"] != "lang" and v["status"] in ("ready", "backup") and v.get("title_tiktok")]
    days = len(usable) / 2  # zwei Shorts pro Tag
    add("WARN" if days < 14 else "OK", f"Short-Vorrat {len(usable)} Videos = {days:.0f} Tage (Notvorrat 14 Tage)")
    nxt = [v for v in inv if v["format"] == "lang" and v["status"] == "ready"]
    add("WARN" if len(nxt) < 3 else "OK", f"Langvideos bereit: {len(nxt)} (3 pro Woche: So, Mi, Fr)")


def main(argv: list) -> int:
    inv = inventory._load("inventory.json", {"videos": []})["videos"]
    check_modules()
    check_inventory(inv)
    check_plan(True)
    check_stock(inv)
    day = datetime.now(inventory.TZ).date().isoformat()
    n = {k: sum(1 for l, _ in R if l == k) for k in ("FEHLER", "WARN", "OK")}
    L = [f"# Selbstpruefung {day}", "", f"{n['FEHLER']} Fehler, {n['WARN']} Warnungen, {n['OK']} in Ordnung", ""]
    L += [f"- **{l}**: {m}" for l, m in R]
    rep = "\n".join(L) + "\n"
    print(rep)
    import os
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(rep)
    if "--dry" not in argv:
        p = inventory._p(f"reports/selfcheck-{day}.md")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(rep, encoding="utf-8")
        inventory.sync(f"Selbstpruefung {day}")
    return 1 if n["FEHLER"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
