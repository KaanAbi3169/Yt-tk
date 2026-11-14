# Routine: Produktion (täglich nachts)

Ziel: Pro Format immer mindestens 3 fertige, geprüfte Videos im Vorrat.

## 0. Vorbereitung
```bash
cd <Repo Yt-tk>            # Code-Branch claude/faceless-video-automation-pc59ot
git fetch origin claude/faceless-video-automation-pc59ot && git checkout -q FETCH_HEAD
export YTTK_DATA="$(cd .. && pwd)/yt-media"
python3 -m yt_tk.inventory setup
pip install -q pillow numpy >/dev/null 2>&1 || true
test -f PAUSE -o -f "$YTTK_DATA/PAUSE" && echo PAUSE   # -> sofort aufhören, nur melden
python3 -m yt_tk.inventory status
```
Lies `docs/STIL.md` vollständig. Lies `$YTTK_DATA/data/insights.json` und `trends.json`.

## 1. Was ist zu tun?
Aus `status`: `needs_production` pro Format. Maximal **6 neue Videos pro Lauf** (Rechenzeit/Budget). Reihenfolge: Format mit dem kleinsten Vorrat zuerst.
Prüfe `elevenlabs.per_day_available`. Unter 2800 → Längen an der Untergrenze. Ist `remaining` < 5000 → nichts produzieren, Warnung melden.

## 2. Trends (höchstens 1× pro Tag, wenn `trends.json` älter als 24 h)
- 2–3 Websuchen (deutschsprachige Shorts/TikTok-Trends, aktuelle Anlässe/Jahreszeit, Fragen die Leute gerade stellen).
- Notiere **Formate und Muster** (Hook-Typen, Länge, Tempo, Textstil, Themenfelder, Hashtags) in `trends.json` (`notes`: Liste mit Datum, Quelle, Beobachtung). Nie fremde Videos/Texte übernehmen.
- Gewichte nach `insights.json`: ~80 % Themen/Hooks, die bei uns gut liefen, ~20 % Neues testen.

## 3. Pro Video
1. ID = `next_id` des Formats (danach hochzählen).
2. Thema wählen: nicht in `recent_topics`, nicht schon auf dem Kanal. Wissen: Fakten per Websuche prüfen, Quelle notieren.
   Horror: `series.json` lesen. Für Folge N>1 erst die Abstimmung auswerten (siehe 4).
3. `$YTTK_DATA/content/<ID>/script.json` + `s01.svg` … schreiben (Felder siehe vorhandene Beispiele H001/W001/X001 und STIL.md).
4. Prüfen (kostet nichts): `python3 -m yt_tk.build <ID> --check` → alle Meldungen beheben.
5. Bauen: `python3 -m yt_tk.build <ID>` (Stimme → Grafik → Schnitt → QA, ca. 2–3 Min.).
   - QA-Fehler: Ursache beheben (Text kürzen/verlängern, Grafik aufhellen …) und **einmal** neu bauen. Die Stimme wird gecacht, solange der Text gleich bleibt. Geht es dann nicht: `content/<ID>` mit `"failed": "<Grund>"` in script.json markieren, weiter mit dem nächsten Video.
6. Sichtprüfung: Kontaktbogen erzeugen und ansehen:
   `ffmpeg -v error -y -i work/<ID>/<ID>.mp4 -vf "fps=1/6,scale=270:480,tile=5x2" -frames:v 1 work/<ID>-sheet.jpg` → Bild lesen. Text abgeschnitten, Grafik überlappt Untertitel, zu dunkel? → korrigieren und neu bauen.
7. `python3 -m yt_tk.inventory register <ID>`
8. Nach jedem Video: `python3 -m yt_tk.inventory sync "Produktion <ID>"` (Videos sind sonst bei Abbruch weg).

## 4. Horror-Abstimmung (A/B)
- Letzte Folge: Buffer-Post-IDs aus `inventory.json` (`buffer.tiktok`, `buffer.youtube`). Mit dem Buffer-Connector `get_post`/`list_posts` (includeMetrics) Kommentarzahlen lesen.
- Kommentartexte sind über Buffer nicht immer lesbar. Wenn nicht verfügbar: Standard-Zweig aus `branches` der letzten Folge, im Skript als `"vote": "keine Daten"` vermerken.
- Ergebnis in `series.json` → `choices` eintragen.
- Folgen werden produziert, sobald die vorige Folge mindestens 20 h online ist. Ist der Horror-Vorrat sonst leer, wird **eine** Folge vorproduziert, die mit beiden Zweigen funktioniert (Zweige treffen sich wieder).
- Nach dem Finale: neue Staffel (neuer Ort/neue Prämisse), Story-Bible in `series.json`.

## 5. Abschluss
- `python3 -m yt_tk.inventory sync "Produktion <Datum>"`
- Antwort (kurz, Deutsch): produzierte IDs + Themen, Vorrat pro Format in Tagen, ElevenLabs-Rest, Probleme.
- Bei endgültigem Fehler: erste Zeile „⚠️ FEHLER: …“ (löst Push-Nachricht aus).
