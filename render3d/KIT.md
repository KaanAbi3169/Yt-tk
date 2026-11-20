# Szenenbaukasten (Autopilot Stufe 2)

Ein neues 3D-Video braucht keinen eigenen Code mehr: `content3d/<ID>.json` mit `"scene": "kit"` und einem Block `"kit"`. Die Engine (`scenes/kit.js`) baut daraus Kulisse, Bauteile und Kamera und steuert alles über **Beats, die an gesprochene Wörter gebunden sind** (Wortzeiten aus Whisper). Die Prüfung `python3 -m yt_tk.kitcheck content3d/<ID>.json` läuft vor dem Rendern und im täglichen Selbstcheck.

## Ablauf für ein neues Video
1. Skript schreiben (STIL.md: Hook, Fakten mit Quelle, Kommentarfrage).
2. Sprache erzeugen (ElevenLabs, Kanalstimme Jan) und mit der Action `audio` als `audio/<ID>.mp3` auf `media` ablegen.
3. `content3d/<ID>.json` schreiben: Titel und Texte (wie bei Shorts), `"scene": "kit"`, `"kit": {...}`. Optional `"credits"` für echte Bilder.
4. `kitcheck` und `textcheck` laufen lassen, dann Action `render3d` mit der ID. Ergebnis: `videos/<ID>.mp4` und Inventar-Eintrag (Status pinned).
5. Einplanen: Eintrag in `data/pins.json` (Tag, Zeit, Plattform), oder `"status": "ready"` im Inhalt: Dann setzt die Planung das Video selbst ein (bevorzugt vor dem Vorrat, 10:00 und 16:00 nach Priorität).

## Aufbau von `kit`
```json
{
  "set": "sunset | night | room | studio",
  "bg": "#rrggbb (optional)", "drift": 0.35,
  "cams": {"start": {"pos": [x,y,z], "look": [x,y,z]}, "nah": {"pos": [...], "look": [...]}},
  "props": [ {"id": "...", "type": "...", "pos": [x,y,z], "scale": 1, "rot": 0, "show": false, ...} ],
  "beats": [ {"at": "<Wortmuster|Sekunden>", "id": "<Bauteil>", "do": "<Aktion>", ...} ]
}
```
**Sichere Zone** (Untertitel liegen unten, Bedienelemente der Plattformen verdecken den Rand): Inhalte mit y zwischen 2,6 und 6,3 und x zwischen -1,8 und 1,8 bei z nahe 0. Die Kanalfigur (`figure`) darf unten stehen.

## Bauteile (`type`)
| Typ | Parameter |
|---|---|
| `text` | `text`, `w`, `h`, `color`, `bg`, `size`, `stroke` |
| `stamp` | wie `text`, Standard roter Stempel |
| `bubble` | `text` (Standard „…“) |
| `counter` | `fmt` (z. B. `"{n} %"`), `from`; Beat `count` zählt hoch |
| `bar` | `w`, `d`, `color`, `h` (Höhe), wächst nach oben (Beat `grow`) |
| `box`, `sphere`, `cylinder`, `arrow` | `size`, `r`, `h`, `color` |
| `monitor` | `screen` (Text auf dem Bildschirm, z. B. „?“) |
| `console` | allgemeine Konsole, keine Marke |
| `calendar` | `text` (Tag), `month`, `prev` (Blatt davor, Beat `flip`) |
| `photo` | `image` (Bild-ID aus `images.json`), `w`; Quelle über `credits` |
| `figure` | Kanalfigur: `shirt`, `pants`, `headScale`, `rot`; Beat `pose` |

## Aktionen (`do`)
`in`/`pop` (erscheint mit Überschwinger), `out`, `move` (`to`, `dur`), `grow` (`to`, `dur`), `spin` (`speed`), `pulse` (`amp`, `dur`), `pose` (`pose`: idle, point, wave, think, cheer, shrug), `flip` (Kalender, `dur`), `count` (`from`, `to`, `dur`, `fmt`), `cam` (`shot`, `dur`), `shake` (`amp`, `dur`).

## Anker (`at`)
- Zahl: Sekunden. Text: Muster (Regex) gegen die **kleingeschriebenen Wörter ohne Satzzeichen**, z. B. `"gerüchte|geruchte"`, `"^pc$"`.
- Zusätze: `"n": 1` (zweites Treffer-Wort), `"end": true` (Ende des Wortes), `"offset": 0.5` (Sekunden danach), `"fallback": 0.3` (Anteil der Videodauer, falls das Wort nicht erkannt wurde).
- **Zahlen:** Whisper schreibt gesprochene Zahlen als Ziffern („achtzehnhundertneunundsechzig“ wird „1869“, „dreißig“ wird „30“). Muster immer mit Ziffer und Zahlwort angeben (`"1869|neunundsechzig"`) und `fallback` setzen.
- Passt ein Muster auf kein Wort, bricht die Prüfung ab (Fehler), mit `fallback` nur Warnung.

## Echte Bilder
Bild über die Action `images` laden (nur freie Lizenzen), als Bauteil `photo` einsetzen und im Inhalt `"credits": [{"id": "IMG001", "from": "<Wortmuster|Sekunden>", "dur": 4}]` angeben. Die Quelle erscheint klein oben links, solange das Bild sichtbar ist.

## Beispiel
`content3d/K001.json` (Nachbau der GTA-Szene als Test, wird nicht veröffentlicht).
