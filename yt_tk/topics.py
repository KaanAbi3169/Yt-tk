"""Stufe 3 Autopilot: woechentlich/taeglich die Themenliste fuer die naechsten 14 Tage (ohne Claude, 0 EUR).

    python -m yt_tk.topics            # schreibt data/topics.json und data/reports/topics-<Tag>.md
    python -m yt_tk.topics --dry      # nur anzeigen

Quellen: data/themen.json (Radar), data/performance.json (Gruppen). Jeder Kandidat hat Quelle und Zahl.
Die Claude-Routine (Tageszyklus) waehlt daraus, prueft Fakten und setzt den Status:
candidate -> chosen -> produced | rejected (mit Grund). Entscheidungen bleiben bei neuen Laeufen erhalten.
Regeln: hoechstens 30 % Test-Slots, Nachrufe/Gewalt/lebende Personen bleiben draussen (Radar filtert vor)."""
import sys
from datetime import datetime, timedelta

from . import inventory

TEST_SHARE = 0.30
KEEP_DAYS = 14


def _score(p):
    m = p.get("7d") or p.get("24h")
    return None if not m else m.get("views", 0) + 20 * m.get("comments", 0) + 10 * m.get("shares", 0) + 5 * m.get("likes", 0)


def group_table() -> list:
    g = {}
    for p in inventory._load("performance.json", {"posts": []})["posts"]:
        s = _score(p)
        if s is not None:
            g.setdefault(p.get("group") or p.get("format") or "?", []).append(s)
    rows = [{"group": k, "n": len(v), "avg": round(sum(v) / len(v))} for k, v in g.items()]
    return sorted(rows, key=lambda r: -r["avg"])


def candidates(th: dict) -> list:
    out = []
    for r in th.get("rising", []):
        if r["ratio"] >= 2:
            out.append({"title": r["title"], "signal": f"Wikipedia-Aufrufe {r['views']} gestern, Faktor {r['ratio']} gegen Schnitt {r['avg_before']}", "kind": "steigend"})
    for r in th.get("evergreen", []):
        if r["avg"] >= 4000:
            out.append({"title": r["title"], "signal": f"Wikipedia-Schnitt {r['avg']} Aufrufe pro Tag ({th.get('days', '?')} Tage)", "kind": "dauerbrenner"})
    for r in th.get("new", []):
        if r["views"] >= 10000:
            out.append({"title": r["title"], "signal": f"neu in den Top 1000 mit {r['views']} Aufrufen", "kind": "neu"})
    return out


def build(today: datetime) -> dict:
    old = inventory._load("topics.json", {"items": []})
    day = today.date().isoformat()
    keep = []
    cutoff = (today - timedelta(days=KEEP_DAYS)).date().isoformat()
    for it in old.get("items", []):
        if it.get("status") in ("chosen", "produced", "rejected") or it.get("added", day) >= cutoff:
            keep.append(it)
    known = {it["title"].lower() for it in keep}
    for c in candidates(inventory._load("themen.json", {})):
        if c["title"].lower() not in known:
            keep.append({**c, "added": day, "status": "candidate", "source": "radar"})
            known.add(c["title"].lower())
    items = [it for it in keep if it["status"] != "candidate" or it.get("added", day) >= cutoff]
    live = [it for it in items if it["status"] in ("candidate", "chosen")]
    return {"date": day, "test_share": TEST_SHARE,
            "slots_14d": {"proven": round(28 * (1 - TEST_SHARE)), "test": round(28 * TEST_SHARE)},
            "groups": group_table(), "open": len(live), "items": items}


def report(t: dict) -> str:
    L = [f"# Themenliste {t['date']}", "",
         f"Kontingent 14 Tage (2 Videos/Tag): {t['slots_14d']['proven']} bewaehrt, hoechstens {t['slots_14d']['test']} Test. Offen: {t['open']}.", "",
         "## Gruppen (Durchschnitt 7 Tage, sonst 24 h)", "| Gruppe | Videos | Ø Wert |", "|---|---|---|"]
    L += [f"| {g['group']} | {g['n']} | {g['avg']} |" for g in t["groups"]] or ["| n/a (keine Messwerte) | | |"]
    L += ["", "## Themen", "| Status | Thema | Art | Signal |", "|---|---|---|---|"]
    L += [f"| {i['status']} | {i['title']} | {i.get('kind', '-')} | {i.get('signal', '-')} |" for i in t["items"]]
    return "\n".join(L) + "\n"


def main(argv: list) -> int:
    t = build(inventory.now())
    rep = report(t)
    print(rep)
    if "--dry" not in argv:
        inventory._save("topics.json", t)
        p = inventory._p(f"reports/topics-{t['date']}.md")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(rep, encoding="utf-8")
        inventory.sync(f"Themenliste {t['date']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
