"""Taegliche Auswertung OHNE Claude (laeuft als GitHub Action, V-009).

    python -m yt_tk.analyze                 # Auswertung fuer heute, schreibt Zahlen + Bericht (Daten-Branch)
    python -m yt_tk.analyze --day 2026-11-17
    python -m yt_tk.analyze --dry           # nur lesen und anzeigen, nichts schreiben

Ablauf wie docs/ROUTINE_ANALYSE.md, soweit ohne Sprachmodell moeglich:
1. Status der Posts mit Buffer abgleichen (gesendet / Fehler) und im Inventar nachfuehren
2. Zahlen (views, likes, comments, shares) 24 h und 7 Tage nach dem Post sammeln (nie schaetzen)
3. `inventory learn` (Auswertung nach Format, Hook, Uhrzeit)
4. Tagesbericht nach data/reports/<Datum>.md (und in die GitHub-Zusammenfassung)
Nicht Teil davon (braucht ein Modell): Hinweise fuer die Produktion, Follower/Abos (Metricool-Connector). Beides
liefert die Claude-Routine "Betrieb & Dashboard".
"""
import os
import sys
from datetime import datetime

from . import buffer_api, config, inventory

ORG = config.BUFFER["organization_id"]
CHANNELS = {"tiktok": config.BUFFER["tiktok_channel_id"], "youtube": config.BUFFER["youtube_channel_id"]}

Q_SENT = """
query Sent($input: PostsInput!, $after: String) {
  posts(first: 100, after: $after, input: $input) {
    edges { node { id status dueAt sentAt channelId metrics { type value unit } metricsUpdatedAt error { message } } }
    pageInfo { hasNextPage endCursor }
  }
}"""


def log(msg: str) -> None:
    print(f"[{datetime.now(inventory.TZ):%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def fetch_posts(channel: str, pages: int = 3) -> list:
    out, after = [], None
    for _ in range(pages):
        inp = {"organizationId": ORG, "filter": {"channelIds": [channel], "status": ["sent", "error"]},
               "sort": [{"field": "dueAt", "direction": "desc"}]}
        d = buffer_api.gql(Q_SENT, {"input": inp, "after": after})["posts"]
        out += [e["node"] for e in (d["edges"] or [])]
        if not d["pageInfo"]["hasNextPage"]:
            break
        after = d["pageInfo"]["endCursor"]
    return out


def metric_dict(post: dict) -> dict:
    return {m["type"]: m["value"] for m in (post.get("metrics") or [])}


def kv_from_metrics(m: dict) -> list:
    """views/likes/comments/shares fuer inventory.perf. Fehlende Werte bleiben weg (nie schaetzen)."""
    likes = m.get("likes", m.get("reactions"))
    vals = {"views": m.get("views"), "likes": likes, "comments": m.get("comments"), "shares": m.get("shares")}
    kv = [f"{k}={int(v)}" for k, v in vals.items() if v is not None]
    if m.get("averageTimeWatched") is not None:
        kv.append(f"watch_ms={int(m['averageTimeWatched'] * 1000)}")  # Sekunden -> Millisekunden
    return kv


def run(day: str, dry: bool) -> int:
    if config.paused():
        log("PAUSE/STOP vorhanden - nichts zu tun.")
        return 0
    posts = {}
    for pf, ch in CHANNELS.items():
        for p in fetch_posts(ch):
            posts[p["id"]] = (pf, p)
    log(f"{len(posts)} Posts aus Buffer gelesen.")
    inv = inventory._load("inventory.json", {"videos": []})["videos"]
    now = inventory.now()
    notes, problems, today_posted = [], [], []

    # 1) Status nachfuehren
    for v in inv:
        if v["status"] != "scheduled" or not v.get("due"):
            continue
        if datetime.fromisoformat(v["due"]) > now:
            continue  # noch nicht faellig
        states = {}
        for pf, pid in (v.get("buffer") or {}).items():
            hit = posts.get(pid)
            states[pf] = (hit[1]["status"] if hit else "unbekannt")
            if hit and hit[1]["status"] == "error":
                problems.append(f"{v['id']} {pf}: " + ((hit[1].get("error") or {}).get("message") or "Fehler ohne Text"))
        if states and all(s == "sent" for s in states.values()):
            if not dry:
                b = v["buffer"]
                inventory.mark(v["id"], b.get("tiktok", ""), b.get("youtube", ""), v["due"], "posted")
            notes.append(f"{v['id']} gesendet ({', '.join(states)})")
            if v["due"].startswith(day):
                today_posted.append(v)
        elif any(s == "error" for s in states.values()) and not dry:
            inventory.fail(v["id"], "Buffer-Fehler, siehe Bericht")

    # 2) Zahlen
    got = 0
    for e in inventory.due_metrics():
        hit = posts.get(e["buffer_post_id"])
        if not hit:
            continue
        kv = kv_from_metrics(metric_dict(hit[1]))
        if not any(k.startswith("views=") for k in kv):
            continue  # Buffer hat noch keine Zahlen (bis zu 24 h Verzoegerung): morgen erneut
        if not dry:
            inventory.perf(e["id"], e["platform"], e["window"], kv)
        got += 1
        notes.append(f"Zahlen {e['id']} {e['platform']} {e['window']}: {', '.join(kv)}")
    log(f"{got} Zahlenwerte gesammelt.")

    # 3) Lernen
    if not dry:
        try:
            inventory.learn()
        except Exception as ex:  # Lernen darf den Bericht nicht verhindern
            problems.append(f"learn: {ex}")

    # 4) Bericht
    report = build_report(day, today_posted, notes, problems, inv)
    print(report)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(report)
    if not dry:
        p = inventory._p(f"reports/{day}.md")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(report, encoding="utf-8")
        log(inventory.sync(f"Analyse {day}"))
    return 0


def build_report(day, today_posted, notes, problems, inv) -> str:
    perf = inventory._load("performance.json", {"posts": []})["posts"]

    def views(p):
        m = p.get("7d") or p.get("24h") or {}
        return m.get("views")

    ranked = sorted([p for p in perf if views(p) is not None], key=views, reverse=True)
    counts = {}
    for v in inv:
        counts.setdefault(v["format"], {}).setdefault(v["status"], 0)
        counts[v["format"]][v["status"]] += 1
    def lst(items):
        return items or ["- –"]

    L = [f"# Tagesbericht {day}", ""]
    L.append("## Heute gepostet")
    L += lst([f"- {v['id']} {v.get('topic', '')[:60]} ({v['format']})" for v in today_posted])
    L += ["", "## Zahlen und Status (aktueller Lauf)"] + lst([f"- {n}" for n in notes])
    L += ["", "## Bestes / schwächstes Video (nach Views, soweit Zahlen vorliegen)"]
    if len(ranked) >= 2:
        b, w = ranked[0], ranked[-1]
        L += [f"- Bestes: {b['id']} {b['platform']} {views(b)} Views ({b.get('topic', '')[:50]})",
              f"- Schwächstes: {w['id']} {w['platform']} {views(w)} Views ({w.get('topic', '')[:50]})"]
    else:
        L.append("- n/a (noch zu wenige Zahlen)")
    L += ["", "## Formate im Vergleich (Ø je Video, Quelle: gesammelte Zahlen)"]
    fm = {}
    for pr in perf:
        m = pr.get("7d") or pr.get("24h")
        if m and m.get("views") is not None:
            e = fm.setdefault(pr.get("format") or "?", {"n": 0, "views": 0, "watch": [], "likes": 0})
            e["n"] += 1; e["views"] += m["views"]; e["likes"] += m.get("likes", 0)
            if m.get("watch_ms"):
                e["watch"].append(m["watch_ms"])
    if fm:
        L.append("| Format | Videos | Ø Views | Ø Likes | Ø Watch-Zeit |")
        L.append("|---|---|---|---|---|")
        for k, e in sorted(fm.items(), key=lambda kv: -kv[1]["views"] / kv[1]["n"]):
            w = f"{sum(e['watch']) / len(e['watch']) / 1000:.1f} s" if e["watch"] else "n/a"
            L.append(f"| {k} | {e['n']} | {e['views'] / e['n']:.0f} | {e['likes'] / e['n']:.1f} | {w} |")
    else:
        L.append("- n/a (noch keine Zahlen)")
    L += ["", "## Gruppen im Vergleich (V-033, Ø je Video, Quelle: gesammelte Zahlen)"]
    gm = {}
    grp_of = {v["id"]: v.get("group") for v in inv}
    for pr in perf:
        g = pr.get("group") or grp_of.get(pr["id"])
        m = pr.get("7d") or pr.get("24h")
        if g and m and m.get("views") is not None:
            e = gm.setdefault(g, {"n": 0, "views": 0, "watch": []})
            e["n"] += 1; e["views"] += m["views"]
            if m.get("watch_ms"):
                e["watch"].append(m["watch_ms"])
    if gm:
        L += ["| Gruppe | Posts | Ø Views | Ø Watch-Zeit |", "|---|---|---|---|"]
        for k, e in sorted(gm.items(), key=lambda kv: -kv[1]["views"] / kv[1]["n"]):
            w = f"{sum(e['watch']) / len(e['watch']) / 1000:.1f} s" if e["watch"] else "n/a"
            L.append(f"| {k} | {e['n']} | {e['views'] / e['n']:.0f} | {w} |")
    else:
        L.append("- n/a (noch keine Zahlen je Gruppe)")
    L += ["", "## Vorrat (Inventar)"]
    for fmt, st in sorted(counts.items()):
        L.append(f"- {fmt}: " + ", ".join(f"{k} {n}" for k, n in sorted(st.items())))
    L += ["", "## Probleme"] + lst([f"- ⚠️ {p}" for p in problems])
    return "\n".join(L) + "\n"


def main(argv: list) -> int:
    day = argv[argv.index("--day") + 1] if "--day" in argv else datetime.now(inventory.TZ).date().isoformat()
    return run(day, "--dry" in argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
