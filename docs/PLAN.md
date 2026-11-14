# Phase 1 – Analyse & Plan (Stand 14.11.2026)

Kanal: **@highlightmighlight** (TikTok) + YouTube-Kanal „Ai“ (UCQkNK8RA001zW5cjp5EZUuA), Deutsch, 9:16.

---

## 1. Was heute schon läuft (Bestandsaufnahme)

### 1.1 Geplante Claude-Aufgaben (laufen in der Cloud, posten über Buffer)
| Aufgabe | Zeit (Zürich) | Was sie macht | Status |
|---|---|---|---|
| Wissensvideo posten | tägl. 06:47 → plant 10:00 | nimmt nächstes `V###.mp4` aus Drive „Auto-Posting“, schreibt Texte, plant in Buffer (TikTok+YT), verschiebt Datei nach „Gepostet“ | **aktiv** |
| Was-wäre-wenn posten | tägl. 14:51 → 15:00 | rendert Folge aus ElevenLabs-Flow, postet sofort via Buffer; pausiert 15.–20.11. (Metricool) | **aktiv**, Vorrat bis 26.11. |
| Horror „DIE REGELN“ posten | tägl. 17:55 → 18:00 | rendert Folge N aus ElevenLabs-Flow, postet via Buffer | **aktiv**, Vorrat bis Folge 15 (~27.11.) |
| Wöchentlicher Wachstumsreport | So 17:41 | Report als Google-Doc in Drive | **aktiv** |
| YouTube-Upload „Die Stimme im Babyfon“ | einmalig 15.11. 19:30 | 10-Min-Horror als normales YT-Video | **aktiv (einmalig)** |
| Erinnerung „Nachproduktion“ | einmalig 22.11. | Erinnerung, neue Staffel zu produzieren | **aktiv (einmalig)** |
| Auto-Posting TikTok (Metricool) | – | alte Version | bereits **deaktiviert** |

### 1.2 Metricool
Nicht „nur Analyse“: **6 geplante Posts** (15.–20.11., je 16:00, TikTok + YouTube, „Was wäre wenn“ Teil 1).
⚠️ Bei allen 6 ist auf YouTube **„KI-Inhalt“ = Nein** gesetzt (TikTok korrekt = Ja).

### 1.3 Buffer (Free-Plan: 3 Kanäle, **max. 10 geplante Posts gleichzeitig**)
- Kanäle: TikTok `highlightmighlight`, YouTube `Ai`. Warteschlange aktuell leer (alles gesendet).
- ⚠️ 14.11. 09:00: YouTube-Post fehlgeschlagen: *„daily video upload limit for an unverified YouTube account“* → **Kanal muss verifiziert werden**.
- ⚠️ Die laufenden Aufgaben setzen auf YouTube `isAiGenerated: false`, obwohl Stimme + Bilder KI sind.

### 1.4 Google Drive „Auto-Posting“
- ~79 fertige Wissensvideos (V006–V084, je ~1,6 MB), 5 in „Gepostet“. Doc „YT_Fortschritt“ (`letztes_video=V015`), ein als ÜBERHOLT markiertes Paket-Doc.

### 1.5 ElevenLabs
- Creator-Plan: **39 822 / 124 853 Credits** verbraucht (≈ 85 000 übrig, Reset ~14.12.2026).
- Bestehende Flows: Horror `ZFvMZW3oFOfCroV7w47P`, Was-wäre-wenn `iphfEy9BV6HvYNhPLg8B` inkl. Musik-Betten (werden weiterverwendet).

### 1.6 Bisherige Zahlen (dünn, Metricool erst seit 13.11. verbunden)
TikTok ~98 Follower; Alltags-/Haushaltstipps liefen am besten (700–760 Views), Posts nach 22 Uhr am schlechtesten.

---

## 2. Wichtige Plattform-Fakten (beeinflussen die Architektur)

1. **Direkt-Upload per API landet privat.** TikTok-Content-Posting-API: ohne Audit nur privat (SELF_ONLY).
   YouTube-Data-API: Projekte ohne Audit → Uploads werden laut offizieller Doku privat gesperrt (aktuell widersprüchliche Berichte).
   → **Wir posten ausschliesslich über Buffer** (geprüfter Partner, Posts werden öffentlich). Kein Direkt-Upload.
2. **Buffer hat eine neue offizielle API** (GraphQL, persönlicher API-Key, auch im Free-Plan). Video-Posts gehen per öffentlicher Video-URL,
   die bis zur Veröffentlichung erreichbar bleiben muss. Die alte REST-API wird am 01.02.2027 abgeschaltet – wir nutzen nur die neue.
3. **Buffer Free = max. 10 geplante Posts.** 3 Videos × 2 Plattformen = 6 Posts/Tag → der 3-Tage-Vorrat liegt **fertig gerendert bei uns**,
   in Buffer wird immer nur der nächste Tag eingeplant.
4. **TikTok Creator Rewards** zahlt nur für Videos **über 1 Minute** (plus 10 000 Follower, 100 000 Views/30 Tage).
   Die Schweiz ist in keiner mir auffindbaren Länderliste – **bitte in TikTok Studio → Creator Rewards prüfen**.
   → Empfehlung: Horror-Format auf **61–75 s** auslegen (dein Wunsch 30–60 s bleibt für Wissen/Was-wäre-wenn).
5. **YouTube-Partnerprogramm & „unoriginelle/massenproduzierte Inhalte“**: Templates sind erlaubt, aber jedes Video braucht eigenen Mehrwert
   (eigenes Skript, eigene Visuals, Abwechslung). Das System erzwingt das (Duplikat-Check, Themen-Sperrliste, wechselnde Hooks).
6. **KI-Kennzeichnung**: YouTube verlangt sie bei realistisch wirkenden synthetischen Inhalten, TikTok bei KI-generierten Inhalten.
   → Unser System setzt **immer** `isAiGenerated: true` auf beiden Plattformen (sicher, kein Reichweiten-Nachteil bekannt).

---

## 3. Architektur – „Alles in Claude“ (Entscheidung vom 14.11.2026)

Alles wird von Claude erstellt und gesteuert. Einzige externe Generatoren: **ElevenLabs** (Stimme + 1 Musiktrack pro Serie).
Keine Gemini-, Pexels- oder sonstigen Fremd-Generatoren.

```
Geplante Claude-Aufgaben (Cloud, Umgebung „Yt-tk“, Repo wird geklont)
┌────────────────────────────────────────────────────────────────────┐
│ PRODUKTION (täglich nachts, bei Vorrat < 3 Tage)                   │
│  1 Trends     Claude-Websuche + eigene Zahlen → data/trends.json   │
│  2 Skript     Claude schreibt Hook, Story, CTA (3 Format-Vorlagen) │
│  3 Stimme     ElevenLabs-API mit Wort-Zeitstempeln (Budget-Wächter)│
│  4 Visuals    von Claude programmierte Grafiken/Animationen (SVG → │
│               Chromium → Frames), pro Serie feste Optik            │
│  5 Untertitel Wort für Wort aus den ElevenLabs-Zeitstempeln        │
│  6 Schnitt    ffmpeg: Kamerafahrten, Übergänge, Musik, 1080x1920   │
│  7 QA         Länge, Ton, Lautheit, Schwarzbild, Sync, Datei-Check │
│  8 Ablage     MP4 → öffentlicher Repo-Branch „media“ (Direkt-URL)  │
├────────────────────────────────────────────────────────────────────┤
│ PLANUNG (täglich früh): nächste 6 Posts in Buffer (Connector)      │
│  Titel/Beschreibung/Hashtags pro Plattform, KI-Kennzeichnung = Ja  │
├────────────────────────────────────────────────────────────────────┤
│ ANALYSE (täglich): Zahlen nach 24 h / 7 Tagen (Buffer, Metricool)  │
│  → data/performance.json → Gewichte für Themen, Hooks, Zeiten      │
│  Tagesbericht + Fehler als Push-Benachrichtigung aufs Handy        │
└────────────────────────────────────────────────────────────────────┘
```

### 3.1 Werkzeuge
| Aufgabe | Werkzeug | Kosten |
|---|---|---|
| Zeitplan / Rechner | Geplante Claude-Aufgaben (dein Claude-Abo) | 0 € extra |
| Trends | Claude-Websuche (YouTube/TikTok-Trendberichte), eigene Zahlen | 0 € |
| Skripte, Texte, Hashtags | Claude | 0 € extra |
| Stimme | ElevenLabs-API (Schlüssel sicher in der Umgebung hinterlegt) | bestehendes Abo |
| Musik | ElevenLabs, 1 Track pro Serie, wiederverwendet | wenige Credits einmalig |
| Visuals | Von Claude erzeugte Vektor-Grafiken/Animationen | 0 € |
| Schnitt, QA | ffmpeg, Python | 0 € |
| Video-Hosting für Buffer | öffentlicher Branch `media` dieses Repos | 0 € |
| Posting | Buffer-Connector (keine Schlüssel nötig) | 0 € |
| Statistik | Buffer- und Metricool-Connector (nur lesen) | 0 € |
| Benachrichtigung | Push der geplanten Claude-Aufgaben (Claude-App) | 0 € |

**ElevenLabs-Budget-Wächter:** ~3 Videos/Tag × ~900 Zeichen ≈ 2 700 Credits/Tag. Fällt das Restbudget unter die Menge für
die verbleibenden Tage bis zum Reset, wird automatisch auf kürzere Skripte umgestellt und du bekommst eine Warnung.

### 3.2 Die 3 Formate (je eigene, feste Optik/Stimme/Musik)
| Slot (Start) | Format | Länge | Look | CTA |
|---|---|---|---|---|
| 10:00 | **Wissen / Fun Fact** | 30–45 s | hell, grosse Infografiken, gelbe Untertitel | Folgen + Ja/Nein-Frage |
| 15:00 | **Was wäre wenn** | 40–60 s | dunkelblau, Szenen-Illustrationen | Kommentar-Frage |
| 18:00 | **Horror „Du wachst auf …“ (Serie)** | 61–75 s | schwarz/rot, Rauschen, Vignette, Glitch | „A oder B?“ → nächste Folge folgt der Mehrheit |

Ab Woche 2 werden die Zeiten jeden Montag aus deinen eigenen Zahlen neu berechnet.

### 3.3 Horror-Fortsetzung „A oder B“
Vor der Produktion der nächsten Folge werden die Kommentare des letzten Teils ausgewertet (soweit über die Connectoren lesbar).
Mehrheit gewinnt; ohne Stimmen gilt der vorab geschriebene Standard-Zweig.

### 3.4 Lernen
Pro Video: Thema, Hook-Typ, Länge, Schnitttempo, Uhrzeit. Nach 24 h / 7 Tagen: Views, Likes, Kommentare, Shares, Follower.
80 % Bewährtes, 20 % Neues testen.

### 3.5 Sicherheit & Regeln
- Keine Schlüssel im Code oder Repo. ElevenLabs-Schlüssel liegt als Netzwerk-Geheimnis in der Claude-Umgebung.
- Nur eigene Inhalte, keine Fremd-Clips/-Musik/-Texte. Fakten bei Wissensvideos werden per Websuche gegengeprüft.
- Duplikat-Schutz: Posting-Log im Repo + Abgleich mit Buffer vor jedem Post.
- Max. 3 Videos/Tag pro Plattform, keine Reuploads, keine Fake-Interaktionen, KI-Kennzeichnung immer an.
- **Not-Aus**: Datei `PAUSE` im Repo anlegen → alle Aufgaben brechen sofort ab.

## 4. Übergang (erledigt am 14.11.2026, auf deinen Wunsch „alles sofort stoppen“)
- Deaktiviert (nicht gelöscht): Wissen 10:00, Was-wäre-wenn 15:00, Horror 18:00, Wochenreport, Babyfon-Upload (15.11.), Erinnerung 22.11.
- Metricool: die 6 Posts vom 15.–20.11. auf **Entwurf** gesetzt (werden nicht veröffentlicht), KI-Kennzeichnung auf Ja korrigiert.
- Die alten Drive-Videos werden **nicht** verwendet. Es wird nur noch gepostet, was das neue System produziert.

---

## 5. Umsetzungs-Reihenfolge (Phase 2)
1. Grundgerüst, Konfiguration, Not-Aus
2. Trend-Notizen → `data/trends.json`
3. Skript-Vorlagen (3 Formate, Duplikat-/Fakten-Prüfung)
4. Stimme (ElevenLabs + Budget-Wächter)
5. Visuals + Untertitel + Render
6. QA
7. Texte & Hashtags pro Plattform
8. Ablage (`media`-Branch) + Buffer-Planung
9. Analyse + Lernen + Tagesbericht
10. Testlauf (Phase 3): 1 Video pro Format, auf YouTube **privat**, auf TikTok als **Buffer-Entwurf** → du schaust es dir an.
