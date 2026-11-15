# Routine: Planung (täglich früh)

Ziel: Die 3 Videos des Tages (je TikTok + YouTube) in Buffer zu festen Zeiten einplanen. Nie doppelt.

## Ablauf
```bash
cd <Repo Yt-tk>; git fetch origin claude/faceless-video-automation-pc59ot && git checkout -q FETCH_HEAD
export YTTK_DATA="$(cd .. && pwd)/yt-media"; python3 -m yt_tk.inventory setup
test -f PAUSE -o -f "$YTTK_DATA/PAUSE" && echo PAUSE   # -> nichts planen, nur melden
python3 -m yt_tk.inventory plan "$(TZ=Europe/Zurich date +%F)"
```
Die Ausgabe ist eine Liste. Für **jeden** Eintrag:
1. **Doppel-Schutz:** Buffer `list_posts` (organizationId 6af6f247f5147bf43b663522, status scheduled/sending/sent, dueAt heute). Gibt es auf einem Kanal schon einen Post mit gleichem Titel/Text-Anfang → diesen Kanal überspringen.
2. Prüfen, dass die Video-URL erreichbar ist: `curl -sfI <video_url> >/dev/null`.
3. Buffer `create_post` für TikTok: `channelId`, `schedulingType "automatic"`, `mode "customScheduled"`, `dueAt` aus dem Eintrag, `text`, `assets [{"video":{"url": video_url}}]`, `metadata` aus dem Eintrag.
4. Dasselbe für YouTube.
5. `python3 -m yt_tk.inventory mark <ID> --tiktok <postId> --youtube <postId> --due <dueAt>`
6. Fehler bei einem Post: einmal nach 60 s wiederholen. Danach `python3 -m yt_tk.inventory fail <ID> "<Fehlertext>"` und melden.

**Reserve-Videos aus Google Drive** (Eintrag mit `"needs_texts": true`, ID `D###`):
1. Google-Drive-Connector `share_file` (fileId = `drive_id`, anyoneWithLink, reader).
2. Titel/Texte nach `docs/STIL.md` schreiben (Thema = `topic`; im Zweifel kurz per Websuche prüfen) als JSON
   `{"title_tiktok","title_youtube","text_tiktok","text_youtube"}` → `python3 -m yt_tk.inventory texts <ID> <datei.json>`.
3. Doppel-Check: Steht das Thema schon in einem gesendeten Buffer-Post (TikTok oder YouTube)? → `inventory fail <ID> "Thema schon online"`,
   im Inventar Status bleibt backup; dann `plan` erneut ausführen (nimmt die nächste Reserve).
4. `plan` erneut ausführen → normaler Eintrag → wie oben posten.

**Limits (automatisch weitermachen, nicht nachfragen):**
- Buffer-Limit (max. 10 geplante Posts) oder YouTube-Fehler „daily upload limit“: betroffenen Post nicht erzwingen.
  Video bleibt `ready` (kein `mark`), es wird beim nächsten Lauf automatisch neu eingeplant. Nur im Bericht erwähnen, keine ⚠️-Push.
- Buffer-API-Rate-Limit: `resetSeconds` abwarten (falls < 15 Min.), dann fortfahren.

Danach: `python3 -m yt_tk.inventory sync "Planung <Datum>"`.

Leere Liste, obwohl kein PAUSE: Vorrat leer → erste Zeile „⚠️ VORRAT LEER: <Format>“.

Antwort (kurz, Deutsch): was wann geplant ist, Vorrat pro Format, Fehler wörtlich.
YouTube-Fehler „daily upload limit / unverified“: melden, dass der Kanal unter youtube.com/verify verifiziert sein muss.
