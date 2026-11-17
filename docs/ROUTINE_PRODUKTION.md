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
Aus `status`: `needs_production` pro Format. Maximal **3 neue Videos pro Lauf** (Claude-Wochenlimit schonen, V-007). Reihenfolge: **Horror-Folge zuerst**, dann das Format mit dem kleinsten Vorrat. Wissen wird nicht produziert, solange mindestens 14 Drive-Reservevideos vorhanden sind (`needs_production` zeigt dann 0). Lange Videos (`lang`): höchstens 1 pro Lauf, bevorzugt montags und dienstags, damit sie Mi/Do bereitstehen.

**Limit-Schonung:** Zeigt `get_session` (eigene Sitzung) `rate_limit_info.status = allowed_warning`, wird nur die Horror-Folge produziert. Bei `rejected`: nichts tun und nicht erneut versuchen. Reihenfolge: Format mit dem kleinsten Vorrat zuerst.
`budget_mode` im Status:
- `normal`: alles produzieren (Längen eher Untergrenze, wenn `per_day_available` < 2800).
- `spar`: Wissen wird nicht neu produziert, die Planung nimmt Reserve-Videos aus Google Drive. Nur Horror + Was wäre wenn produzieren.
- `pause`: ElevenLabs-Kontingent aufgebraucht → **nichts produzieren, keine ⚠️-Push**. Die Planung postet weiter aus Vorrat/Reserve.
  Nach dem monatlichen Reset (`elevenlabs.reset`) läuft die Produktion automatisch wieder an. Nicht nachfragen.
ElevenLabs 401/403/429 mitten im Lauf: aufhören, Rest beim nächsten Lauf (keine Wiederholung heute).

### Lange Videos (Format `lang`, 2 pro Woche, Mi + Do 16:00)
- Höchstens **1 langes Video pro Lauf**, und erst nachdem die Shorts des nächsten Tages fertig sind.
- Gruselgeschichte zum Zuhören, 7–10 Min. (ca. 1 000–1 350 Wörter), eigene Handlung (eine abgeschlossene Geschichte, nicht die Shorts-Staffel nacherzählen).
- 20–70 Szenen, aber nur 12–25 verschiedene SVGs (`svg_file` darf mehrfach verwendet werden, Bewegung variieren), `viewBox="0 0 1920 1080"`.
- Kapitel: `"chapter": "Name"` an der ersten Szene jedes Kapitels (mind. 3, Szene 1 immer). `text_youtube` enthält `{KAPITEL}` – wird beim `register` durch die echten Zeitmarken ersetzt.
- Nur `title_youtube`/`text_youtube` (kein TikTok), kein `#shorts`.
- Vertonung läuft automatisch in Abschnitten (ca. 7–9 Tsd. Credits pro Video). Im Budget-Modus `spar`: Länge an der Untergrenze (7 Min.). Bei `pause`: nicht produzieren.
- Bauen dauert ca. 10–20 Min. Kontaktbogen: `ffmpeg -v error -y -i work/<ID>/<ID>.mp4 -vf "fps=1/30,scale=480:270,tile=5x4" -frames:v 1 work/<ID>-sheet.jpg`.

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
- Horror wird **immer nur eine Folge im Voraus** produziert (`needs_production` ist dann 1): nachts nach dem Post um 18:00,
  damit die Abstimmung (ca. 7 h Kommentare) einfließen kann. Ist die vorige Folge noch nicht online (z. B. Start der Staffel),
  schreibe die Folge so, dass beide Zweige wieder zusammenlaufen.
- Nach dem Finale: neue Staffel (neuer Ort/neue Prämisse), Story-Bible in `series.json`.

## 5. Abschluss
- `python3 -m yt_tk.inventory sync "Produktion <Datum>"`
- Antwort (kurz, Deutsch): produzierte IDs + Themen, Vorrat pro Format in Tagen, ElevenLabs-Rest, Probleme.
- Bei endgültigem Fehler: erste Zeile „⚠️ FEHLER: …“ (löst Push-Nachricht aus).
