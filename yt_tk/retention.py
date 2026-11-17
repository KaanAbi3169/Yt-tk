"""Retention-Zahlen unserer eigenen YouTube-Videos (V-019): Ø Wiedergabedauer und Ø angesehene Prozent je Video.

    python -m yt_tk.retention            # holt Daten der letzten 28 Tage, schreibt Bericht + data/retention.json
    python -m yt_tk.retention --dry

Braucht drei GitHub-Secrets (vom Inhaber angelegt): YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN
(Scope yt-analytics.readonly) und YOUTUBE_API_KEY fuer die Titel. Geheimnisse werden nie ausgegeben."""
import json
import os
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from . import inventory

TOKEN = "https://oauth2.googleapis.com/token"
REPORTS = "https://youtubeanalytics.googleapis.com/v2/reports"
VIDEOS = "https://www.googleapis.com/youtube/v3/videos"


class RetentionError(Exception):
    pass


def log(msg: str) -> None:
    print(f"[{datetime.now(inventory.TZ):%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def _env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise RetentionError(f"{name} fehlt (GitHub-Secret anlegen)")
    return v


def _open(req):
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:300]
        if "invalid_grant" in body:
            raise RetentionError("Zugang abgelaufen oder widerrufen (invalid_grant): Refresh-Token neu erzeugen")
        raise RetentionError(f"HTTP {e.code}: {body}")


def access_token() -> str:
    data = urllib.parse.urlencode({"client_id": _env("YOUTUBE_CLIENT_ID"), "client_secret": _env("YOUTUBE_CLIENT_SECRET"),
                                   "refresh_token": _env("YOUTUBE_REFRESH_TOKEN"), "grant_type": "refresh_token"}).encode()
    return _open(urllib.request.Request(TOKEN, data=data))["access_token"]


def analytics(token: str, start: str, end: str) -> list:
    q = urllib.parse.urlencode({"ids": "channel==MINE", "startDate": start, "endDate": end, "dimensions": "video",
                                "metrics": "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage",
                                "sort": "-views", "maxResults": 200})
    d = _open(urllib.request.Request(REPORTS + "?" + q, headers={"Authorization": f"Bearer {token}"}))
    cols = [c["name"] for c in d.get("columnHeaders", [])]
    return [dict(zip(cols, r)) for r in d.get("rows", [])]


def titles(ids: list) -> dict:
    out, key = {}, _env("YOUTUBE_API_KEY")
    for i in range(0, len(ids), 50):
        q = urllib.parse.urlencode({"part": "snippet", "id": ",".join(ids[i:i + 50])})
        d = _open(urllib.request.Request(VIDEOS + "?" + q, headers={"x-goog-api-key": key}))
        out.update({it["id"]: it["snippet"]["title"] for it in d.get("items", [])})
    return out


def join(rows: list, names: dict, inv: list) -> list:
    by_title = {v.get("title_youtube"): v for v in inv if v.get("title_youtube")}
    out = []
    for r in rows:
        t = names.get(r["video"], "")
        v = by_title.get(t, {})
        out.append({"yt_id": r["video"], "id": v.get("id", "–"), "format": v.get("format", "–"),
                    "hook": v.get("hook_type", "–"), "title": t, "views": int(r["views"]),
                    "avg_s": round(float(r["averageViewDuration"]), 1), "avg_pct": round(float(r["averageViewPercentage"]), 1)})
    return out


def report(day: str, rows: list) -> str:
    L = [f"# Retention YouTube {day}", "", "Quelle: YouTube Analytics API, eigener Kanal, letzte 28 Tage. "
         "Ø angesehen in % = durchschnittlicher Anteil der Videolaenge, den Zuschauer sehen.", "",
         "| Video | Format | Aufrufe | Ø Sekunden | Ø angesehen % | Titel |", "|---|---|---|---|---|---|"]
    L += [f"| {r['id']} | {r['format']} | {r['views']} | {r['avg_s']} | {r['avg_pct']} | {r['title'][:60]} |" for r in rows[:40]]
    fm = {}
    for r in rows:
        fm.setdefault(r["format"], []).append(r)
    L += ["", "## Nach Format (Median)", "| Format | Videos | Ø Sekunden | Ø angesehen % |", "|---|---|---|---|"]
    for k, g in sorted(fm.items()):
        L.append(f"| {k} | {len(g)} | {statistics.median(x['avg_s'] for x in g)} | {statistics.median(x['avg_pct'] for x in g)} |")
    return "\n".join(L) + "\n"


def main(argv: list) -> int:
    day = datetime.now(inventory.TZ).date()
    try:
        tok = access_token()
        rows = analytics(tok, (day - timedelta(days=28)).isoformat(), (day - timedelta(days=1)).isoformat())
        if not rows:
            print("Keine Daten (Analytics liefert Werte mit Verzoegerung von 1 bis 2 Tagen).")
            return 0
        inv = inventory._load("inventory.json", {"videos": []})["videos"]
        joined = join(rows, titles([r["video"] for r in rows]), inv)
    except RetentionError as e:
        print("FEHLER:", e)
        return 1
    rep = report(day.isoformat(), joined)
    print(rep)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(rep)
    if "--dry" not in argv:
        p = inventory._p(f"reports/retention-{day.isoformat()}.md")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(rep, encoding="utf-8")
        inventory._save("retention.json", {"date": day.isoformat(), "videos": joined})
        log(inventory.sync(f"Retention {day.isoformat()}"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
