"""Musteranalyse YouTube Shorts (V-016, P1c): Was haben Videos gemeinsam, die weit ueber ihrer Kanalgroesse laufen?

    python -m yt_tk.patterns              # holt Daten, schreibt Bericht + data/patterns.json (Daten-Branch)
    python -m yt_tk.patterns --dry        # nur anzeigen, nichts schreiben
    python -m yt_tk.patterns --queries 3  # nur die ersten 3 Suchen (spart Kontingent)

Nur oeffentliche Kennzahlen ueber die offizielle YouTube Data API v3 (Schluessel YOUTUBE_API_KEY). Kein Scraping, keine
fremden Inhalte: gespeichert werden nur Muster (Zahlen) und die Liste der Ausreisser mit Titel/Kanal als Beleg.
Kontingent: search.list kostet 100 Einheiten, videos.list und channels.list je 1 (Tageslimit 10 000).
Nicht verfuegbar ueber die API: Wiedergabezeit und Zuschauerbindung fremder Videos. TikTok ist nicht Teil davon."""
import json
import os
import re
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone

from . import inventory

API = "https://www.googleapis.com/youtube/v3"
# (Format, Suchbegriff): Themen, die zu unseren Formaten passen
QUERIES = [("wissen", "wusstest du schon"), ("wissen", "mythos faktencheck"), ("wissen", "haushalt trick"),
           ("waswaerewenn", "was wäre wenn"), ("wissen", "warum passiert das"), ("wissen", "physik erklärt"),
           ("horror", "unheimliche geschichte"), ("wissen", "geld sparen schweiz")]
MAX_SHORT_S = 90          # Shorts bis 90 s zaehlen mit
# Langvideo-Modus (--long): Videos von 4 bis 15 Minuten, letzte 90 Tage
LONG_MIN_S, LONG_MAX_S, LONG_DAYS = 240, 900, 90
LONG_QUERIES = [("wissen", "mythen faktencheck"), ("wissen", "haushalt tricks"), ("wissen", "wusstest du schon"),
                ("waswaerewenn", "was wäre wenn"), ("horror", "gruselgeschichte"), ("horror", "unheimliche geschichte"),
                ("wissen", "alltagswissen erklärt"), ("wissen", "physik erklärt")]
KIND = [("liste", re.compile(r"^\W*\d+\s|\b(top\s*\d+|\d+\s+(tricks|fakten|dinge|mythen|gründe|tipps))", re.I)),
        ("geschichte", re.compile(r"geschichte|creepypasta|horror|unheimlich|gruselig|mystery", re.I)),
        ("was-waere-wenn", re.compile(r"was wäre wenn|was waere wenn", re.I)),
        ("mythos", re.compile(r"mythos|mythen|wahr oder|stimmt das|wirklich", re.I)),
        ("erklaerung", re.compile(r"warum|wieso|wie funktioniert|erklärt|erklaert", re.I))]
LONG = False
MIN_VIEWS = 10_000        # darunter kein Ausreisser
MIN_SUBS = 1_000          # kleine Kanaele zaehlen mit 1000, sonst Rauschen
OUTLIER_RATIO = 3.0       # Aufrufe mindestens das Dreifache der Abos
QUESTION_WORDS = ("warum", "wieso", "weshalb", "wie", "was", "wer", "wann", "wo", "wusstest", "kann", "ist", "hast", "hat")
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐]")
HASHTAG = re.compile(r"#\w+", re.UNICODE)
DUR = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")
WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


class ApiError(Exception):
    pass


def log(msg: str) -> None:
    print(f"[{datetime.now(inventory.TZ):%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def _key() -> str:
    k = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{30,60}", k):
        raise ApiError("YOUTUBE_API_KEY fehlt oder ist kein gueltiger Schluessel (nur Buchstaben, Ziffern, _ und -, "
                       f"30 bis 60 Zeichen, gefunden {len(k)}). Secret ohne Anfuehrungszeichen und Leerzeichen neu anlegen.")
    return k


class Quota:
    used = 0


def get(path: str, params: dict, cost: int) -> dict:
    url = f"{API}/{path}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"x-goog-api-key": _key(), "Accept": "application/json"})
    Quota.used += cost
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise ApiError(f"HTTP {e.code} bei {path}: {e.read().decode('utf-8', 'ignore')[:300]}")


def parse_duration(s: str) -> int:
    m = DUR.fullmatch(s or "")
    if not m:
        return 10 ** 6
    h, mi, se = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + se


def chunks(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def collect(queries: list) -> list:
    """Gibt eine Liste von Videos mit Kennzahlen zurueck (Shorts, oder mit --long Videos von 4 bis 15 Minuten)."""
    after = (datetime.now(timezone.utc) - timedelta(days=LONG_DAYS if LONG else 30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ids = {}
    for fmt, q in queries:
        d = get("search", {"part": "snippet", "type": "video", "q": q, "order": "viewCount", "publishedAfter": after,
                           "relevanceLanguage": "de", "videoDuration": "medium" if LONG else "short", "maxResults": 50}, cost=100)
        for it in d.get("items", []):
            ids.setdefault(it["id"]["videoId"], fmt)
        log(f"Suche '{q}': {len(d.get('items', []))} Treffer")
    vids = []
    for part in chunks(list(ids), 50):
        d = get("videos", {"part": "snippet,contentDetails,statistics", "id": ",".join(part)}, cost=1)
        for it in d.get("items", []):
            sn, st = it["snippet"], it.get("statistics", {})
            lang = (sn.get("defaultAudioLanguage") or sn.get("defaultLanguage") or "de").lower()
            dur = parse_duration(it["contentDetails"].get("duration"))
            too_long = dur > LONG_MAX_S if LONG else dur > MAX_SHORT_S
            too_short = LONG and dur < LONG_MIN_S
            if too_long or too_short or not lang.startswith("de") or "viewCount" not in st:
                continue
            vids.append({"id": it["id"], "format": ids[it["id"]], "title": sn["title"], "channel_id": sn["channelId"],
                         "channel": sn["channelTitle"], "published": sn["publishedAt"], "duration": dur,
                         "views": int(st["viewCount"]), "likes": int(st.get("likeCount", 0)),
                         "comments": int(st.get("commentCount", 0)), "desc": (sn.get("description") or "")[:300],
                         "tags": sn.get("tags", [])})
    subs = {}
    for part in chunks(sorted({v["channel_id"] for v in vids}), 50):
        d = get("channels", {"part": "statistics", "id": ",".join(part)}, cost=1)
        for it in d.get("items", []):
            s = it.get("statistics", {})
            subs[it["id"]] = None if s.get("hiddenSubscriberCount") else int(s.get("subscriberCount", 0))
    out = []
    for v in vids:
        s = subs.get(v["channel_id"])
        if s is None:
            continue  # Abozahl verborgen oder unbekannt: nie schaetzen
        v["subs"] = s
        v["ratio"] = round(v["views"] / max(s, MIN_SUBS), 2)
        out.append(v)
    return out


def features(v: dict) -> dict:
    t = v["title"]
    pub = datetime.fromisoformat(v["published"].replace("Z", "+00:00")).astimezone(inventory.TZ)
    first = re.sub(r"^\W+", "", t).split(" ")[0].lower() if t else ""
    kind = next((k for k, rx in KIND if rx.search(t + " " + v["desc"][:120])), "sonstiges")
    chapters = bool(re.search(r"(^|\n)\s*\(?0?0:\d\d", v["desc"]))
    return {"kind": kind, "chapters": chapters, "title_len": len(t), "question": "?" in t or first in QUESTION_WORDS, "digit": bool(re.search(r"\d", t)),
            "emoji": bool(EMOJI.search(t)), "hashtags": len(HASHTAG.findall(t + " " + v["desc"])),
            "duration": v["duration"], "hour": pub.hour, "weekday": pub.weekday()}


MAX_PER_CHANNEL = 3  # ein Kanal darf das Bild nicht allein bestimmen


def split_outliers(vids: list) -> tuple:
    out = [v for v in vids if v["views"] >= MIN_VIEWS and v["ratio"] >= OUTLIER_RATIO]
    if len(out) < 8 and vids:  # zu wenige: oberstes Fuenftel nach Verhaeltnis
        out = sorted(vids, key=lambda v: -v["ratio"])[:max(1, len(vids) // 5)]
    seen, capped = Counter(), []
    for v in sorted(out, key=lambda v: -v["ratio"]):
        if seen[v["channel_id"]] < MAX_PER_CHANNEL:
            seen[v["channel_id"]] += 1
            capped.append(v)
    out = capped
    ids = {v["id"] for v in out}
    return out, [v for v in vids if v["id"] not in ids]


def summarize(group: list) -> dict:
    if not group:
        return {}
    f = [features(v) for v in group]
    med = statistics.median
    return {"n": len(group), "title_len": med(x["title_len"] for x in f), "duration": med(x["duration"] for x in f),
            "hashtags": med(x["hashtags"] for x in f),
            "chapters": round(100 * sum(x["chapters"] for x in f) / len(f)),
            "question": round(100 * sum(x["question"] for x in f) / len(f)),
            "digit": round(100 * sum(x["digit"] for x in f) / len(f)),
            "emoji": round(100 * sum(x["emoji"] for x in f) / len(f))}


def analyze(vids: list) -> dict:
    out, rest = split_outliers(vids)
    of = [features(v) for v in out]
    tags = Counter(h.lower() for v in out for h in set(HASHTAG.findall(v["title"] + " " + v["desc"])))
    by_fmt = {}
    for fmt in sorted({v["format"] for v in vids}):
        g = [v for v in out if v["format"] == fmt]
        by_fmt[fmt] = {"outliers": len(g), "videos": sum(1 for v in vids if v["format"] == fmt),
                       "median_views": int(statistics.median(v["views"] for v in g)) if g else None}
    oid = {v["id"] for v in out}
    top_all = [{"id": v["id"], "kind": features(v)["kind"], "views": v["views"], "duration": v["duration"], "out": v["id"] in oid}
               for v in vids]
    return {"top_all": top_all, "long": LONG, "date": datetime.now(inventory.TZ).date().isoformat(), "videos": len(vids), "outliers": len(out), "outlier_channels": len({v["channel_id"] for v in out}),
            "outlier_summary": summarize(out), "rest_summary": summarize(rest), "by_format": by_fmt,
            "hours": Counter(x["hour"] for x in of).most_common(5),
            "weekdays": [(WEEKDAYS[d], n) for d, n in Counter(x["weekday"] for x in of).most_common(3)],
            "hashtags": [(h, n) for h, n in tags.most_common(10) if n >= 3],
            "top": [{k: v[k] for k in ("id", "format", "title", "channel", "views", "subs", "ratio", "duration")}
                    for v in sorted(out, key=lambda v: -v["ratio"])[:15]]}


def report(a: dict, quota: int) -> str:
    o, r = a["outlier_summary"], a["rest_summary"]
    L = [f"# Musterbericht YouTube {'Langvideos' if LONG else 'Shorts'} {a['date']}", "",
         f"Quelle: YouTube Data API v3, deutschsprachige {'Videos von 4 bis 15 Minuten der letzten 90 Tage' if LONG else f'Shorts bis {MAX_SHORT_S} s der letzten 30 Tage'}. "
         f"{a['videos']} Videos geprueft, davon {a['outliers']} Ausreisser von {a['outlier_channels']} Kanaelen, je Kanal hoechstens {MAX_PER_CHANNEL} (Aufrufe mindestens {OUTLIER_RATIO:g}x Abos "
         f"und mindestens {MIN_VIEWS} Aufrufe; sonst oberstes Fuenftel). Kontingent verbraucht: {quota} Einheiten.", ""]
    if not o:
        return "\n".join(L + ["Keine Daten."]) + "\n"
    L += ["## Ausreisser gegen Rest", "| Merkmal | Ausreisser | Rest |", "|---|---|---|",
          f"| Videos | {o['n']} | {r.get('n', 'n/a')} |",
          f"| Titellaenge (Median, Zeichen) | {o['title_len']} | {r.get('title_len', 'n/a')} |",
          f"| Dauer (Median, Sekunden) | {o['duration']} | {r.get('duration', 'n/a')} |",
          f"| Titel mit Frage | {o['question']} % | {r.get('question', 'n/a')} % |",
          f"| Titel mit Zahl | {o['digit']} % | {r.get('digit', 'n/a')} % |",
          f"| Titel mit Emoji | {o['emoji']} % | {r.get('emoji', 'n/a')} % |",
          f"| Hashtags (Median) | {o['hashtags']} | {r.get('hashtags', 'n/a')} |",
          f"| Beschreibung mit Kapiteln | {o['chapters']} % | {r.get('chapters', 'n/a')} % |", "",
          "## Format", "| Format | Videos | Ausreisser | Median Aufrufe der Ausreisser |", "|---|---|---|---|"]
    for k, v in a["by_format"].items():
        L.append(f"| {k} | {v['videos']} | {v['outliers']} | {v['median_views'] if v['median_views'] is not None else 'n/a'} |")
    L += ["", "## Wann die Ausreisser veroeffentlicht wurden (Zeit Zuerich)",
          "Hinweis: Das ist der Zeitpunkt des Hochladens, nicht bewiesen die beste Zeit. Mit unseren eigenen Zahlen abgleichen.",
          "- Stunden: " + (", ".join(f"{h}:00 ({n}x)" for h, n in a["hours"]) or "n/a"),
          "- Wochentage: " + (", ".join(f"{d} ({n}x)" for d, n in a["weekdays"]) or "n/a"), "",
          "## Haeufige Hashtags der Ausreisser (mindestens 3x)",
          ", ".join(f"{h} ({n}x)" for h, n in a["hashtags"]) or "keine", "", "## Top Ausreisser (Beleg)",
          "| Video | Format | Aufrufe | Abos | Verhaeltnis | Sek | Titel |", "|---|---|---|---|---|---|---|"]
    for t in a["top"]:
        L.append(f"| {t['id']} | {t['format']} | {t['views']} | {t['subs']} | {t['ratio']} | {t['duration']} | "
                 f"{t['title'][:70].replace('|', '/')} |")
    L += ["", "## Grenzen", "- Keine Wiedergabezeit und keine Zuschauerbindung fremder Videos ueber die API.",
          "- Kleine Stichprobe, bis zu 8 Suchen mit je 50 Treffern. Muster sind Hinweise, keine Beweise.",
          "- TikTok ist nicht enthalten (Scraping ist verboten). Fuer TikTok zaehlen unsere eigenen Zahlen.",
          "- Nur Muster uebernehmen (Aufbau, Tempo, Titelform), nie Inhalte anderer."]
    return "\n".join(L) + "\n"


def main(argv: list) -> int:
    global LONG
    LONG = "--long" in argv
    qs = LONG_QUERIES if LONG else QUERIES
    n = int(argv[argv.index("--queries") + 1]) if "--queries" in argv else len(qs)
    try:
        vids = collect(qs[:n])
    except ApiError as e:
        print("FEHLER:", e)
        return 1
    log(f"{len(vids)} Shorts mit bekannter Abozahl, Kontingent {Quota.used}")
    a = analyze(vids)
    rep = report(a, Quota.used)
    print(rep)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(rep)
    if "--dry" not in argv:
        day = a["date"]
        p = inventory._p(f"reports/muster-{'lang-' if LONG else ''}{day}.md")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(rep, encoding="utf-8")
        inventory._save("patterns-lang.json" if LONG else "patterns.json", a)
        log(inventory.sync(f"Musterbericht {day}"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
