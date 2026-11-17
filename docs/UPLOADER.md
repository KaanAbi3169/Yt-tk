# Uploader ohne Claude (V-001)

Plant die Videos des Tages in Buffer, **ohne Claude**. Läuft als GitHub Action (`.github/workflows/uploader.yml`) täglich 06:37 MEZ (und 08:37 als zweiter Versuch). Kosten: 0 €.

## Einrichten (einmalig)
1. Buffer: publish.buffer.com/settings/api → „Personal“ → „+ New Key“. Key kopieren (wird nur einmal gezeigt).
2. GitHub: Repo Yt-tk → Settings → Secrets and variables → Actions → **Secrets** → New repository secret: Name `BUFFER_API_KEY`.
3. Trockenlauf prüfen: Actions → uploader → Run workflow. Im Log steht „TROCKENLAUF …“ pro geplantem Post.
4. Live schalten: Settings → Secrets and variables → Actions → **Variables** → `UPLOADER_LIVE` = `true`. Erst danach wird wirklich geplant.
5. Danach die Claude-Aufgabe „Yt-tk Planung (Posten)“ deaktivieren (nie beide gleichzeitig live).

## Verhalten
- Plan aus `inventory.plan` (Sendeplan: 10:00 Wissen/Was wäre wenn im Wechsel, 18:00 Horror, Mi+Do 16:00 lange Videos nur YouTube).
- **Doppelschutz** über die ganze Kanal-Historie (Video-Datei oder Text-Anfang), Buffer-Limit 10 geplante Posts, nie blind wiederholen.
- Fehlen Titel/Texte bei einem Drive-Reservevideo, wird es übersprungen (siehe Notvorrat).
- Fehler → Exit-Code 1 → GitHub meldet den fehlgeschlagenen Lauf.
- Ohne `BUFFER_API_KEY` macht die Action nichts (kein Fehlalarm).

## Notvorrat
14 Drive-Reservevideos (D016–D032) haben Titel und Texte und sind per Link freigegeben. Das reicht für 14 Tage Notbetrieb ohne Claude (Wissens-Slot). Horror (A/B-Abstimmung) und lange Videos brauchen Claude und pausieren.

## Status der Buffer-Abfragen
- **Schema geprüft** (17.11.2026, Introspektion über `uploader.yml` mit Argument `--introspect`). Der Client nutzt `posts(input: PostsInput!)` und `createPost(input: CreatePostInput!)` mit den Pflichtfeldern `channelId`, `mode`, `schedulingType`, `needsApproval`, `assets: [{video: {url}}]`.
- **Noch nicht geprüft:** die erste echte, angemeldete Abfrage. Sie braucht einen gültigen Key im Secret.
- Der Client erkennt ein falsch eingefügtes Secret (viele Sonderzeichen) und bricht mit einer klaren Meldung ab. Es wird nie ein Wert ausgegeben.

## Testen
- Schema: Actions → uploader → Run workflow, Argumente `--introspect` (optional `--types Name1,Name2`).
- Trockenlauf für einen Tag: Argumente `--day 2026-11-18`. Fragt Buffer lesend ab und zeigt, was gepostet würde.
- Live: Variable `UPLOADER_LIVE=true`.
