"""Themenradar (V-020): Was wird gerade gesucht? Ohne Claude, ohne Kosten.

    python -m yt_tk.radar            # holt Daten, schreibt data/reports/themen-<Tag>.md + data/themen.json (Daten-Branch)
    python -m yt_tk.radar --dry      # nur anzeigen

Quellen (offiziell, oeffentlich): Wikipedia-Aufrufzahlen (Wikimedia REST API, deutsche Wikipedia, kein Schluessel) und die
YouTube-Trendliste fuer die Schweiz (videos.list chart=mostPopular, 1 Kontingent-Einheit, nur mit YOUTUBE_API_KEY).
Der Radar liefert Themenvorschlaege, KEINE Fakten. Jedes Thema geht erst nach dem Faktencheck in die Produktion.
Gefiltert werden Gewalt, Verbrechen, Tod, Sex und Sonderseiten. Personen bleiben drin (nicht erkennbar), die Regie
schliesst Nachrufe und lebende Personen als Aufhaenger aus (docs/STIL.md)."""
import json
import os
import re
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from . import inventory

WIKI = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/de.wikipedia/all-access/{y}/{m:02d}/{d:02d}"
YT = "https://www.googleapis.com/youtube/v3/videos"
UA = "brudi-radar/1.0 (https://github.com/KaanAbi3169/Yt-tk; Themenrecherche fuer Wissensvideos)"
DAYS = 8                  # 1 aktueller Tag + 7 Vergleichstage
MIN_VIEWS = 5000          # darunter kein Treffer
MIN_RATIO = 2.0           # mindestens doppelt so viele Aufrufe wie der Schnitt der Vortage
WIKI_API = "https://de.wikipedia.org/w/api.php"
WD_API = "https://www.wikidata.org/w/api.php"
NOISE = re.compile(r"(\((Film|Fernsehserie|Fernsehreihe|Album|Band|Lied|Spiel|Roman|Sendung|Musiker|Schauspieler)[^)]*\)|^Liste |^Nekrolog|"
                   r"^\d+\. (Januar|Februar|M\u00e4rz|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)$|^Tag |Volkstrauertag|Bu\u00df)", re.I)
SKIP_PREFIX = ("Spezial:", "Wikipedia:", "Datei:", "Kategorie:", "Portal:", "Hilfe:", "Vorlage:", "Benutzer:", "Hauptseite")
BLOCK = re.compile(r"(mord|anschlag|massaker|amok|vergewaltig|selbstmord|suizid|hinrichtung|terror|pornograf|sexual|nazi|hitler|"
                   r"holocaust|konzentrationslager|todesfall|leiche|missbrauch|krieg gegen|geiselnahme)", re.I)


def log(msg: str) -> None:
    print(f"[{datetime.now(inventory.TZ):%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def wiki_top(day: datetime):
    """Top-1000 der Tages-Aufrufe als {Titel: Aufrufe}, None wenn der Tag noch nicht verfuegbar ist."""
    req = urllib.request.Request(WIKI.format(y=day.year, m=day.month, d=day.day), headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            arts = json.load(r)["items"][0]["articles"]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    return {a["article"].replace("_", " "): a["views"] for a in arts
            if not a["article"].startswith(SKIP_PREFIX) and ":" not in a["article"]}


def analyse(days: list) -> dict:
    """days: Liste von {Titel: Aufrufe}, neuester Tag zuerst."""
    today, prev = days[0], days[1:]
    rising, new, blocked = [], [], 0
    for t, v in today.items():
        if BLOCK.search(t):
            blocked += 1
            continue
        hist = [d[t] for d in prev if t in d]
        if v >= MIN_VIEWS and len(hist) >= 4:
            ratio = v / max(statistics.mean(hist), 1)
            if ratio >= MIN_RATIO:
                rising.append({"title": t, "views": v, "avg_before": int(statistics.mean(hist)), "ratio": round(ratio, 1)})
        elif v >= MIN_VIEWS and len(hist) < 2:
            new.append({"title": t, "views": v})
    evergreen = {}
    for d in days:
        for t, v in d.items():
            if not BLOCK.search(t):
                evergreen.setdefault(t, []).append(v)
    ever = sorted(({"title": t, "avg": int(statistics.mean(v))} for t, v in evergreen.items() if len(v) >= len(days) - 1),
                  key=lambda x: -x["avg"])[:150]
    return {"rising": sorted(rising, key=lambda x: -x["ratio"]), "new": sorted(new, key=lambda x: -x["views"]),
            "evergreen": ever, "blocked": blocked, "days": len(days)}


def _json(url: str) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
        return json.load(r)


def persons(titles: list) -> set:
    """Titel, die laut Wikidata Menschen sind (P31 = Q5). Bei Fehlern leere Menge (dann bleibt die Liste ungefiltert)."""
    qid = {}
    try:
        for i in range(0, len(titles), 50):
            q = urllib.parse.urlencode({"action": "query", "prop": "pageprops", "ppprop": "wikibase_item", "redirects": 1,
                                        "titles": "|".join(titles[i:i + 50]), "format": "json"})
            d = _json(WIKI_API + "?" + q)["query"]
            back = {}
            for k in ("normalized", "redirects"):
                for m in d.get(k, []):
                    back[m["to"]] = m["from"]
            for pg in d.get("pages", {}).values():
                item = pg.get("pageprops", {}).get("wikibase_item")
                if item:
                    t = pg["title"]
                    qid[back.get(t, t)] = item
                    qid[t] = item
        ids = sorted(set(qid.values()))
        human = set()
        for i in range(0, len(ids), 50):
            q = urllib.parse.urlencode({"action": "wbgetentities", "ids": "|".join(ids[i:i + 50]), "props": "claims",
                                        "format": "json"})
            for eid, e in _json(WD_API + "?" + q).get("entities", {}).items():
                for c in e.get("claims", {}).get("P31", []):
                    if c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id") == "Q5":
                        human.add(eid)
        return {t for t, item in qid.items() if item in human}
    except Exception as e:  # Filter ist Zugabe, darf den Radar nicht verhindern
        log(f"Personenfilter fehlgeschlagen: {type(e).__name__}")
        return set()


def clean(a: dict, limit: int = 25) -> dict:
    pool = sorted({r["title"] for k in ("rising", "new", "evergreen") for r in a[k] if not NOISE.search(r["title"])})
    people = persons(pool)
    out = dict(a, people_removed=0)
    for k in ("rising", "new", "evergreen"):
        keep = [r for r in a[k] if r["title"] not in people and not NOISE.search(r["title"])]
        out["people_removed"] += len(a[k]) - len(keep)
        out[k] = keep[:limit]
    return out


def yt_trending(key: str) -> list:
    url = YT + "?part=snippet,statistics&chart=mostPopular&regionCode=CH&maxResults=25"
    req = urllib.request.Request(url, headers={"x-goog-api-key": key, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        items = json.load(r).get("items", [])
    return [{"title": i["snippet"]["title"], "channel": i["snippet"]["channelTitle"],
             "views": int(i.get("statistics", {}).get("viewCount", 0)), "category": i["snippet"].get("categoryId")}
            for i in items if not BLOCK.search(i["snippet"]["title"])]


def report(day: str, a: dict, yt: list) -> str:
    L = [f"# Themenradar {day}", "",
         f"Quellen: Wikipedia-Aufrufzahlen (de, {a['days']} Tage) und YouTube-Trendliste Schweiz. {a['blocked']} Treffer wegen "
         "Gewalt, Verbrechen, Tod oder Sex herausgefiltert. Das sind Themenvorschlaege, keine Fakten: Jedes Thema braucht "
         "den Faktencheck, Nachrufe und lebende Personen bleiben draussen.", "",
         "## Steigende Themen (Aufrufe gestern gegen Schnitt der Vortage)", "| Thema | Aufrufe | Schnitt davor | Faktor |", "|---|---|---|---|"]
    L += [f"| {r['title']} | {r['views']} | {r['avg_before']} | {r['ratio']} |" for r in a["rising"]] or ["| – | | | |"]
    L += ["", "## Neu in den Top 1000", "| Thema | Aufrufe |", "|---|---|"]
    L += [f"| {r['title']} | {r['views']} |" for r in a["new"]] or ["| – | |"]
    L += ["", "## Dauerbrenner (Schnitt der Tage, gute Quellenlage)", "| Thema | Ø Aufrufe pro Tag |", "|---|---|"]
    L += [f"| {r['title']} | {r['avg']} |" for r in a["evergreen"]] or ["| – | |"]
    L += ["", "## YouTube-Trendliste Schweiz (Titel, Kanal, Aufrufe)"]
    L += [f"- {v['title'][:80]} ({v['channel']}, {v['views']})" for v in yt] or ["- n/a (kein YOUTUBE_API_KEY oder keine Daten)"]
    return "\n".join(L) + "\n"


def main(argv: list) -> int:
    base = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    days, d = [], base - timedelta(days=1)
    while len(days) < DAYS and d > base - timedelta(days=DAYS + 4):
        t = wiki_top(d)
        if t is not None:
            days.append(t)
        d -= timedelta(days=1)
    if len(days) < 5:
        print("FEHLER: zu wenige Tage von Wikipedia erhalten:", len(days))
        return 1
    log(f"{len(days)} Tage Wikipedia-Daten")
    a = clean(analyse(days))
    yt = []
    k = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if k:
        try:
            yt = yt_trending(k)
        except Exception as e:  # Trendliste ist Zugabe, darf den Bericht nicht verhindern
            log(f"YouTube-Trendliste fehlgeschlagen: {type(e).__name__}")
    day = datetime.now(inventory.TZ).date().isoformat()
    rep = report(day, a, yt)
    print(rep)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(rep)
    if "--dry" not in argv:
        p = inventory._p(f"reports/themen-{day}.md")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(rep, encoding="utf-8")
        inventory._save("themen.json", {"date": day, **a, "youtube": yt})
        log(inventory.sync(f"Themenradar {day}"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
