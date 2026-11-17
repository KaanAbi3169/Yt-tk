# Yt-tk – Automatischer Kurzvideo-Kanal @highlightmighlight

Vollautomatisches System für TikTok + YouTube Shorts (Deutsch, 9:16, 1080×1920).
Alles wird von **Claude** erstellt: Trend-Recherche, Skript, Grafiken, Schnitt, Untertitel, Texte, Planung, Auswertung.
Einziger externer Generator: **ElevenLabs** (Stimme + 1 Musiktrack pro Serie). Gepostet wird über **Buffer**.

---

## 📱 Kurz fürs Handy

### Was läuft automatisch?
| Wann (Zürich) | Aufgabe | Was passiert |
|---|---|---|
| täglich 01:23 | **Produktion** | Vorrat prüfen, fehlende Videos recherchieren, schreiben, vertonen, schneiden, prüfen |
| täglich 06:37 | **Planung (ohne Claude)** | GitHub Action `uploader.yml` plant die Videos des Tages in Buffer (TikTok + YouTube). Not-Aus: Variable `UPLOADER_LIVE=false` |
| täglich 21:43 | **Analyse & Bericht (ohne Claude)** | GitHub Action `analyse.yml`: Zahlen holen, lernen, Bericht nach `data/reports/` (Branch media). Sonntags 22:30 räumt `compact.yml` auf |

Sendezeiten (seit 16.11.2026): **10:00 Wissen / Was wäre wenn (täglich im Wechsel) · 18:00 Horror „Du wachst auf“** – je TikTok + YouTube Shorts.
Dazu **Mi + Do 16:00 ein langes YouTube-Video** (Gruselgeschichte, 16:9, 7–10 Min.).
Ab der 2. Woche passt das System die Zeiten jeden Montag an deine Zahlen an.

### ⏸️ Alles pausieren
**Weg 1 – Not-Aus-Datei (empfohlen):**
1. GitHub-App oder github.com öffnen → Repo **Yt-tk** → Branch **media**.
2. „+“ / „Add file“ → **Create new file** → Name: `PAUSE` → Inhalt egal → **Commit**.
3. Ab sofort wird nichts mehr produziert oder geplant. Schon in Buffer geplante Posts löschst du in der Buffer-App.

**Wieder starten:** Die Datei `PAUSE` (oder `STOP`) im Branch `media` löschen.

**Weg 2 – Aufgaben ausschalten:** Claude-App → Code → Sitzung „Autonomer Content-Agent für Faceless-Videos“ → geplante Aufgaben → die 3 „Yt-tk“-Aufgaben deaktivieren. Oder einfach in diese Sitzung schreiben: „Pausiere alles“.

### Wo sehe ich was?
- **Fertige Videos & Daten:** Branch `media` → `videos/`, `content/<ID>/`, `reports/` (Tagesberichte)
- **Vorrat:** `media` → `data/inventory.json` (`ready` = fertig, `scheduled` = in Buffer, `posted` = online)
- **Statistik & Lernergebnisse:** `media` → `data/performance.json`, `data/insights.json`
- **Horror-Serie (Staffel, gewählte Zweige):** `media` → `data/series.json`
- **Geplante Posts:** Buffer-App

---

## 🧱 Aufbau

```
yt_tk/
  config.py      Formate, Stimmen, Zeiten, Buffer-IDs (nur hier ändern)
  tts.py         ElevenLabs: Stimme mit Wort-Zeitstempeln, Musik, Budget-Wächter
  visuals.py     SVG-Szenen (von Claude geschrieben) → Bilder; Serien-Badge, Hook-Titel
  subtitles.py   Wort-für-Wort-Untertitel (ASS)
  render.py      ffmpeg: Kamerafahrten, Übergänge, Effekte, Musik-Ducking, Lautheit −14 LUFS
  qa.py          Qualitätsprüfung: Länge, Auflösung, Ton, Lautheit, Stille, Schwarzbild, Untertitel-Sync, Datei
  build.py       Skript → fertiges MP4  (python -m yt_tk.build <ID> [--check])
  inventory.py   Vorrat, Planung, Statistik, Lernen, Datenablage (python -m yt_tk.inventory …)
tools/svg2png.js Chromium-Renderer für die Grafiken
assets/music/    1 Musiktrack pro Serie (ElevenLabs, wiederverwendet)
docs/            PLAN.md, STIL.md, ROUTINE_*.md (Arbeitsanweisungen der geplanten Aufgaben)
```

### Ablauf eines Videos
1. Claude schreibt `content/<ID>/script.json` + Szenen-SVGs (Stil: `docs/STIL.md`)
2. `build --check` prüft Felder, Länge, Grafik-Regeln (kostenlos)
3. ElevenLabs erzeugt die Stimme inkl. Zeitstempeln (Cache: Neu-Rendern kostet keine Credits)
4. Grafiken → Kamerafahrten → Übergänge → Serien-Overlays → Untertitel → Musik (geduckt) → MP4
5. Automatische QA; nur bestandene Videos kommen in den Vorrat
6. Planung legt die Posts mit KI-Kennzeichnung in Buffer an; Doppel-Schutz über Vorrat + Buffer-Abgleich
7. Nach 24 h / 7 Tagen werden Zahlen gesammelt → `insights.json` → nächste Themen/Hooks/Zeiten

### Formate
| Format | ID | Länge | Stimme (ElevenLabs) |
|---|---|---|---|
| Wissen | W### | 30–50 s | Jan (Social Media, de) |
| Was wäre wenn | X### | 40–60 s | Leander (warm, ruhig, de) |
| Horror „Du wachst auf“ | H### | 61–80 s | Vincent Crowe (düster, de) |

## 🔐 Sicherheit
- Keine Schlüssel im Code. Der ElevenLabs-Schlüssel liegt als Netzwerk-Geheimnis in der Claude-Umgebung **„Yt-tk“**
  (Claude → Einstellungen der Umgebung). Buffer/Metricool laufen über die Claude-Connectoren.
- Regeln: KI-Kennzeichnung immer an, nur eigene Inhalte, max. 3 Videos/Tag/Plattform, keine Reuploads, keine Fake-Interaktionen.

## 💸 Kosten
0 € zusätzlich. ElevenLabs-Creator-Abo (bestehend): ca. 2 900 Credits/Tag für 3 Videos. Der Budget-Wächter
drosselt die Länge, wenn es bis zum monatlichen Reset knapp wird.

## 🛠️ Lokal testen (optional)
```bash
git worktree add ../yt-media media
export YTTK_DATA=../yt-media ELEVENLABS_API_KEY=...   # nur lokal, nie committen
python -m yt_tk.build W001 --check
python -m yt_tk.build W001
```
