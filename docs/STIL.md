# Stil-Leitfaden (verbindlich für jedes Skript)

## Allgemein
- Sprache: natürliches Deutsch (Du-Form), kurze Sätze, keine Füllwörter. Zahlen als Wörter, wenn sie gesprochen werden („drei Uhr siebzehn“).
- Erster Satz = Hook (Neugier, Widerspruch, Gefahr oder direkte Ansprache). Kein „Hallo“, kein Intro.
- Jedes Video endet mit einem Call-to-Action (Kommentar-Frage, A/B, Folgen).
- Nie fremde Texte, Clips, Musik oder Markennamen/Logos kopieren. Nur eigene Formulierungen und eigene Grafiken.
- Wissen: Jede Faktenaussage muss per Websuche bestätigt sein (Quelle in `sources`). Unsicheres weglassen. Keine Gesundheits-/Finanzratschläge, die schaden könnten.
- Horror: unheimlich, nicht brutal. Keine Gewaltdetails, kein Blut, keine Selbstverletzung, keine echten Personen/Orte/Verbrechen. Altersgerecht (13+).
- Was wäre wenn: Gedankenexperimente, eine Pointe/Twist, positive oder nachdenkliche Note.

## Länge (wird automatisch geprüft)
| Format | Sekunden | Wörter ca. |
|---|---|---|
| wissen | 30–50 | 85–120 |
| waswaerewenn | 40–60 | 100–140 |
| horror | 61–80 | 150–175 |
| lang (YouTube, 16:9) | 420–600 | 1 000–1 350 |

Ist das ElevenLabs-Tagesbudget (`per_day_available` im Status) unter 2800: jeweils an der Untergrenze bleiben.

## Szenen-Grafiken (SVG)
- 5–10 Szenen, je eine SVG-Datei `sNN.svg` neben `script.json`, `viewBox="0 0 1080 1920"`.
- **Sicherheitszonen:** Wichtige Inhalte nur zwischen **y = 280 und y = 1080**, x = 80–1000.
  - y 0–260: Serien-Badge (wird automatisch eingeblendet)
  - y 1150–1450: Untertitel (dort keine Schrift/Details in der Grafik!)
  - y 1450–1920: von TikTok/YouTube-Bedienelementen verdeckt → nur Hintergrund
- Ganzflächiger Hintergrund (nie leer/schwarz ohne Struktur), mind. 3 Bildebenen (Hintergrund, Motiv, Akzent).
- Erlaubte Schriften: `Inter`, `Inter Display`, `DejaVu Serif`, `JetBrains Mono`. Emojis nur sparsam (Noto Color Emoji).
- Verboten: externe Bilder/Links, eingebettete Fotos (`data:image/png|jpeg`), `<script>`, `<foreignObject>`, CSS-@import.
- Bewegung pro Szene (`motion`): `zoom_in`, `zoom_out`, `pan_left`, `pan_right`, `pan_up`, `pan_down`, `shake` (nur Horror, max. 1×). Abwechseln.
- Bei 2× Zoom bleibt Text lesbar, wenn er ≥ 34 px groß ist.

### Serien-Optik (einheitlich halten!)
- **wissen** („WUSSTEST DU?“): kräftige, helle Flächenfarben (Gelb #FFD400/#FFB627, Himmelblau #5BC0EB, Mint, Creme), dicke dunkle Konturen #1E2A3A (10–14 px), Flat-Infografiken, Labels in Inter Display 900 GROSS.
- **waswaerewenn** („WAS WÄRE WENN …“): Nachtblau-Verlauf #0B1E4A→#071433, Sterne-Punkte, Glow-Akzente Pink #FF3B6B / Gold #FFD24A, Silhouetten mit hellblauer Kontur #4F7DF0/#9FC3FF.
- **horror** („DU WACHST AUF“): fast schwarz #030305–#14110f, kaltes Grau-Blau, Rot-Akzent #B00000/#FF2A2A, warmes Türschlitz-Licht #FFCF8A, Schrift DejaVu Serif. Nicht zu dunkel: Motiv muss erkennbar sein (Helligkeit der Hauptfläche > 8 %).

## Texte pro Plattform
- `title_tiktok` ≤ 90 Zeichen, 1 Emoji. `title_youtube` ≤ 100 Zeichen, endet auf ` #shorts`.
- `text_tiktok`: 1 Satz + Frage + 4–6 Hashtags. `text_youtube`: 1–2 Sätze + Frage + Hinweis „Stimme und Grafiken mit KI erstellt.“ + 4–6 Hashtags inkl. #shorts.
- Hashtags: Mix aus 1–2 Trend-/Reichweiten-Tags (#fürdich, #wusstestdu, #waswärewenn) und 2–4 Nischen-Tags. Kein #fyp-Spam, keine themenfremden Tags. Gesamt 3–8.

## Horror-Serie „Du wachst auf“
- Staffel = 5 Folgen (Teil 1–4 + Finale). `series.json` hält Staffel, Titel, Story-Bible, gewählte Zweige.
- Jede Folge endet mit „A: … / B: …“ (Szene mit A/B-Karten) – außer dem Finale (dort: Wahl der nächsten Staffel).
- Nächste Folge setzt die **Mehrheit** der Kommentare fort (siehe ROUTINE_PRODUKTION.md). Ohne Stimmen: vorher notierter Standard-Zweig.
- `part_label`: „TEIL 2“, …, „FINALE“.

## Lange Gruselgeschichte (`lang`, YouTube 16:9)
- Eine abgeschlossene Geschichte, Ich-Erzähler, ruhiges Tempo, steigende Spannung, offenes oder überraschendes Ende. Gleiche Regeln wie Horror (nicht brutal, 13+, keine echten Personen/Orte/Verbrechen).
- Aufbau: Hook (1–2 Sätze) → 4–7 Kapitel → kurzer Abschluss mit Kommentar-Frage („Was hättest du getan?“) und Abo-Hinweis.
- SVGs: `viewBox="0 0 1920 1080"`. **Sicherheitszonen:** Badge oben links (x 0–720, y 0–130), Untertitel unten (y 900–1080) → dort keine Details. Wichtiges zwischen y 140 und 880.
- Optik wie Horror (Farben, DejaVu Serif), Motive breiter angelegt (Räume, Flure, Fenster, Landschaft bei Nacht).
- `title_youtube` ≤ 100 Zeichen, Muster „<Hook> | Gruselgeschichte (Deutsch)“, kein #shorts. `text_youtube`: 2–3 Sätze Teaser, `{KAPITEL}`, Kommentar-Frage, „Diese Geschichte ist frei erfunden. Stimme und Grafiken wurden mit KI erstellt.“, 4–8 Hashtags.
