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

## 3. Architektur

```
                 GitHub Actions (Cron, kostenlos)                         Buffer (bestehend)
┌──────────────────────────────────────────────────────────────┐         ┌──────────────┐
│ 1 trends      YouTube Data API → data/trends.json            │         │ TikTok       │
│ 2 plan        Themen wählen (Trends + eigene Performance)    │         │ YouTube      │
│ 3 script      Gemini (Free-Tier) → Skript/JSON pro Video     │         └──────▲───────┘
│ 4 voice       ElevenLabs (Budget-Wächter) → Fallback Piper   │                │
│ 5 visuals     Pexels/Pixabay (+ opt. KI-Bilder)              │                │ createPost
│ 6 subtitles   Wort-Timing (ElevenLabs-Alignment / Whisper)   │                │ (Video-URL)
│ 7 render      ffmpeg: Ken-Burns, Übergänge, Untertitel, Musik│                │
│ 8 qa          Länge, Ton, Lautheit, Schwarzbild, Sync, Datei │                │
│ 9 publish     MP4 → öffentliche URL (GitHub Release)  ───────┼────────────────┘
│10 analytics   +24 h / +7 Tage Zahlen (Buffer + YouTube API)  │
│11 learn       Gewichte für Themen/Hooks/Zeiten anpassen      │
│12 report      tägl. Kurzbericht + Fehler → Push aufs Handy   │
└──────────────────────────────────────────────────────────────┘
Daten (trends, Skripte, Posting-Log, Statistiken) liegen versioniert im Repo unter data/.
```

### 3.1 Tool-Auswahl (alles 0 €)
| Aufgabe | Werkzeug | Kosten | Fallback |
|---|---|---|---|
| Zeitplan / Rechner | GitHub Actions | 0 € (öffentliches Repo: unbegrenzt; privat: 2000 Min./Monat, reicht knapp) | – |
| Trend-Recherche | YouTube Data API v3 (10 000 Einheiten/Tag) | 0 € | – |
| TikTok-Trends | TikTok Creative Center hat **keine offizielle API**, automatisches Auslesen verstösst gegen die TikTok-Nutzungsbedingungen → wir nutzen YouTube-Trends als Format-Signal + **deine eigenen TikTok-Zahlen** (Buffer). | 0 € | – |
| Skripte & Texte | Google Gemini API (Free-Tier) | 0 € | Groq (Free-Tier) |
| Stimme | ElevenLabs (dein Creator-Plan) mit Budget-Wächter | bereits bezahlt | **Piper TTS** (Open Source, Stimme „thorsten“, lizenzfrei), danach edge-tts |
| Musik | ElevenLabs Music: **1 Track pro Serie**, wiederverwendet; bestehende Musik-Betten übernehmen | einmalig wenige Credits | – |
| Bilder/Clips | Pexels + Pixabay API | 0 € | KI-Bilder optional über Cloudflare Workers AI (Free-Tier) |
| Untertitel-Timing | ElevenLabs „with timestamps“ (exakt) / faster-whisper (Piper) | 0 € | – |
| Schnitt | ffmpeg + Python | 0 € | – |
| Video-Hosting für Buffer | GitHub Release-Assets (öffentliche Direkt-URL) | 0 € | Google Drive Direktlink |
| Posting | Buffer API (bestehendes Konto) | 0 € | – |
| Statistik | Buffer-Post-Metriken + YouTube Data API (öffentliche Zahlen) | 0 € | YouTube Analytics (Watchtime) später optional |
| Benachrichtigung | ntfy (Push-App, ohne Konto) | 0 € | Telegram-Bot |

### 3.2 Die 3 Formate (je eigene, feste Optik/Stimme/Musik)
| Slot (Start) | Format | Länge | Look | CTA |
|---|---|---|---|---|
| 10:00 | **Wissen / Fun Fact** | 30–45 s | hell, gelbe Untertitel, Stock-Clips | „Folgen für mehr“ + Ja/Nein-Frage |
| 15:00 | **Was wäre wenn** | 40–60 s | blau/neutral, Ken-Burns auf Bildern | Kommentar-Frage |
| 18:00 | **Horror „Du wachst auf …“ (Serie)** | 61–75 s | dunkel, Rot-Akzent, Rauschen, Vignette | „A oder B?“ → nächste Folge setzt die Mehrheitsantwort fort |

Die Zeiten werden ab Woche 2 jeden Montag aus deinen eigenen Zahlen neu berechnet (Wochentag × Stunde, geglättet, mind. 2 h Abstand).

### 3.3 Horror-Fortsetzung „A oder B“
Nach 20 h liest das System die Kommentare des letzten Teils (YouTube Data API, öffentlich; TikTok-Kommentare via Buffer, soweit verfügbar),
zählt A/B und schreibt den nächsten Teil mit der Mehrheitswahl. Gleichstand/keine Stimmen → vorab geschriebener Standard-Zweig.

### 3.4 Lernen
Für jedes Video speichern wir Thema, Hook-Typ, Länge, Schnitttempo, Uhrzeit. Nach 24 h und 7 Tagen kommen Views, Likes, Kommentare, Shares
(und Watchtime, sobald YouTube-Analytics verbunden ist) dazu. Ein einfacher Bandit-Ansatz (80 % Bewährtes, 20 % Neues testen) steuert
Themen- und Hook-Auswahl – so kippt der Kanal nicht in Wiederholung.

### 3.5 Sicherheit & Regeln
- Alle Schlüssel nur als **GitHub Secrets**; lokal `.env` (in `.gitignore`).
- Keine Fremd-Clips/-Musik/-Texte; Stock nur mit Pexels/Pixabay-Lizenz, Quellen pro Video protokolliert.
- Duplikat-Schutz: Posting-Log im Repo + Abgleich mit Buffer vor jedem Post → nie doppelt.
- Max. 3 Videos/Tag pro Plattform, keine Reuploads, keine Fake-Interaktionen.
- **Not-Aus**: Datei `PAUSE` im Repo anlegen (geht in der GitHub-App) → alle Jobs stoppen sofort, nichts wird gepostet.

---

## 4. Übergang ohne Doppel-Posts
Das neue System übernimmt **formatweise**, sobald es für ein Format den 3-Tage-Vorrat hat. Erst dann wird die alte Aufgabe für genau dieses
Format deaktiviert (nicht gelöscht). Bis dahin läuft alles wie jetzt weiter. Die 79 fertigen Wissensvideos in Drive werden **zuerst
aufgebraucht** (nach QA-Check), danach produziert das System neue Wissensvideos.

---

## 5. Umsetzungs-Reihenfolge (Phase 2)
1. Grundgerüst, Konfiguration, Secrets-Check, Not-Aus, Benachrichtigung
2. Trend-Modul → `data/trends.json`
3. Skript-Modul (3 Format-Vorlagen, Duplikat-/Fakten-Prüfung)
4. Stimme (ElevenLabs + Budget-Wächter + Piper-Fallback)
5. Visuals + Untertitel + Render
6. QA
7. Texte & Hashtags pro Plattform
8. Publish (Release-URL) + Buffer-Planung
9. Analytics + Lernen + Tagesbericht
10. Testlauf (Phase 3): 1 Video pro Format, auf YouTube **privat**, auf TikTok als **Buffer-Entwurf** → du schaust es dir an.
