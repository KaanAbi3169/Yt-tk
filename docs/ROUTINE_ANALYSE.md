# Routine: Analyse & Tagesbericht (täglich abends)

```bash
cd <Repo Yt-tk>; git fetch origin claude/faceless-video-automation-pc59ot && git checkout -q FETCH_HEAD
export YTTK_DATA="$(cd .. && pwd)/yt-media"; python3 -m yt_tk.inventory setup
python3 -m yt_tk.inventory due-metrics
```

## 1. Status der heutigen Posts
Für alle Videos mit `due` heute: Buffer `get_post` (beide Kanäle). `sent` → ok (`mark <ID> ... --status posted`), `error` → Fehler wörtlich in den Bericht + `inventory fail`.

## 2. Zahlen sammeln (24 h und 7 Tage nach Upload)
Für jeden Eintrag aus `due-metrics`: Buffer `get_post` mit der `buffer_post_id` (Metriken) bzw. `list_posts` mit `includeMetrics: true`.
Dann: `python3 -m yt_tk.inventory perf <ID> <platform> <24h|7d> views=.. likes=.. comments=.. shares=..`
Ergänzend (nur lesen): Metricool `getAnalyticsDataByMetrics` (brandId 8079551) für Follower/Abos.
Fehlende Werte als fehlend behandeln, nie schätzen.

## 3. Lernen
`python3 -m yt_tk.inventory learn` → `insights.json` (montags werden die Uhrzeiten automatisch angepasst).
Lies das Ergebnis und schreibe 2–3 konkrete Hinweise für die Produktion in `data/trends.json` → `notes` (Quelle: „eigene Zahlen“).

## 4. Aufräumen (sonntags)
`python3 -m yt_tk.inventory compact` (entfernt veröffentlichte Videos > 3 Tage aus dem media-Branch).

## 5. Tagesbericht
Datei `reports/<YYYY-MM-DD>.md` im media-Worktree, dann `python3 -m yt_tk.inventory sync "Bericht <Datum>"`.
Antwort an den Nutzer (max. 12 Zeilen, Deutsch, fürs Handy):
- ✅ Heute gepostet (Format, Titel, Links falls vorhanden)
- 📈 Zahlen (24 h/7 Tage) + Follower TikTok / Abos YouTube
- 🏆 Bestes / schwächstes Video und warum (Vermutung klar als Vermutung)
- 📦 Vorrat pro Format, ElevenLabs-Rest
- 🗓️ Morgen geplant
- ⚠️ Probleme (falls vorhanden – dann als erste Zeile)
