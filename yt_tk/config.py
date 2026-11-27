"""Zentrale Konfiguration. Nur hier aendern."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Laufzeitdaten (Inventar, Videos, Statistik) liegen im Branch "media",
# ausgecheckt als Worktree neben dem Code. Lokal ueberschreibbar per YTTK_DATA.
DATA = Path(os.environ.get("YTTK_DATA", ROOT.parent / "yt-media")).resolve()
WORK = Path(os.environ.get("YTTK_WORK", ROOT / "work")).resolve()

REPO_SLUG = "KaanAbi3169/Yt-tk"
MEDIA_BRANCH = "media"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO_SLUG}/{MEDIA_BRANCH}"

TIMEZONE = "Europe/Zurich"

BUFFER = {
    "organization_id": "6af6f247f5147bf43b663522",
    "tiktok_channel_id": "6af6f29a62b70b94b0193977",
    "youtube_channel_id": "6af6f28662b70b94b01938a3",
}

ELEVEN_MODEL = "eleven_multilingual_v2"

# Ein Format = eine Serie mit fester Optik, Stimme, Musik.
FORMATS = {
    "wissen": {
        "label": "Wissen",
        "prefix": "W",
        "slot": "10:00",  # teilt sich den Slot mit waswaerewenn (ROTATION)
        "min_s": 30, "max_s": 50, "wps": 2.6,
        "voice_id": "keqaIOtp0ePlmN5jgQfy",  # Jan - Social Media Creator (de)
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.35, "use_speaker_boost": True, "speed": 1.08},
        "youtube_category": "27",  # Education
        "transition": "smoothleft",
        "font": "Inter Black",
        "sub_primary": "&H00FFFFFF", "sub_highlight": "&H0000E5FF", "sub_outline": "&H00000000",
        "music_volume": 0.10,
        "badge": "WUSSTEST DU?",
        "effects": "light",
    },
    "waswaerewenn": {
        "label": "Was wäre wenn",
        "prefix": "X",
        "slot": "10:00",  # teilt sich den Slot mit wissen (ROTATION)
        "min_s": 40, "max_s": 60, "wps": 2.45,
        "voice_id": "EFMWG4bgYSD1vaE3P8OS",  # Leander - warm, calm (de)
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.8, "style": 0.3, "use_speaker_boost": True, "speed": 1.04},
        "youtube_category": "24",  # Entertainment
        "transition": "dissolve",
        "font": "Inter ExtraBold",
        "sub_primary": "&H00FFFFFF", "sub_highlight": "&H00FFD24A", "sub_outline": "&H00301A0A",
        "music_volume": 0.12,
        "badge": "WAS WÄRE WENN …",
        "effects": "dream",
    },
    "horror": {
        "label": "Horror – Du wachst auf",
        "prefix": "H",
        "slot": "16:00",     # zweiter Kurzvideo-Slot (Sendeplan siehe SENDEPLAN, Inhaber 27.11.2026)
        "weekdays": [0, 1, 2, 3, 4],  # nur Mo bis Fr (Sa und So hat ein Kurzvideo-Slot)
        "fallback": "wissen",  # ist keine Horror-Folge fertig, laeuft hier ein Wissens-Short (Vorrat)
        "min_s": 61, "max_s": 80, "wps": 2.3,  # >60 s: Voraussetzung TikTok Creator Rewards
        "voice_id": "18X2yBovneA0q06wd8E9",  # Vincent Crowe - Dark & Haunting Tales (de)
        "voice_settings": {"stability": 0.55, "similarity_boost": 0.85, "style": 0.4, "use_speaker_boost": True, "speed": 1.0},
        "youtube_category": "24",
        "transition": "fadeblack",
        "font": "DejaVu Serif",
        "sub_primary": "&H00F0F0F0", "sub_highlight": "&H002020E0", "sub_outline": "&H00000000",
        "music_volume": 0.16,
        "badge": "DU WACHST AUF",
        "effects": "horror",
    },
    # Lange YouTube-Videos (kein Short): 16:9, 7-10 Min., nur YouTube, nur an bestimmten Wochentagen.
    "lang": {
        "label": "Gruselgeschichte (lang, YouTube)",
        "prefix": "L",
        "slot": "16:00",
        "weekdays": [2, 3, 4],  # 0=Mo ... 2=Mi, 3=Do, 4=Fr: Anweisung des Inhabers 27.11.2026 (Langvideo Mi, Do, Fr 16:00, YouTube-Spitze laut Metricool)
        "platforms": ["youtube"],
        "orientation": "landscape",
        "style": "horror",   # Optik, Badge-Farben, Musik wie die Horror-Serie
        "music": "horror",
        "min_s": 420, "max_s": 600, "wps": 2.3,  # max 10 Min. -> Datei bleibt < 95 MB (GitHub-Limit 100 MB)
        "min_scenes": 20, "max_scenes": 70,
        "chapters": True,
        "voice_id": "18X2yBovneA0q06wd8E9",  # Vincent Crowe - Dark & Haunting Tales (de)
        "voice_settings": {"stability": 0.6, "similarity_boost": 0.85, "style": 0.35, "use_speaker_boost": True, "speed": 0.98},
        "youtube_category": "24",
        "transition": "fadeblack",
        "font": "DejaVu Serif",
        "sub_primary": "&H00F0F0F0", "sub_highlight": "&H002020E0", "sub_outline": "&H00000000",
        "music_volume": 0.10,
        "badge": "GRUSELGESCHICHTE",
        "effects": "horror",
    },
}

# Sendeplan Kurzvideos (Anweisung des Inhabers 27.11.2026, Metricool-Bestzeiten 28.11. bis 4.12.): je Format und Plattform eine Uhrzeit.
# "woche" = Mo bis Fr, "ende" = Sa und So. Fehlt der Eintrag fuer den Tag, laeuft das Format an dem Tag nicht.
# TikTok-Spitzen 10:00 und 18:00, YouTube-Spitzen 16:00 und 10:00. Am Wochenende (Werte rund halb so hoch) ein Kurzvideo:
# TikTok 10:00, YouTube 16:00. Die Zeiten sind fest (keine automatische Verschiebung); der Wochenreview gleicht sie ab.
SENDEPLAN = {
    "wissen": {"woche": {"tiktok": "10:00", "youtube": "10:00"}, "ende": {"tiktok": "10:00", "youtube": "16:00"}},
    "waswaerewenn": {"woche": {"tiktok": "10:00", "youtube": "10:00"}, "ende": {"tiktok": "10:00", "youtube": "16:00"}},
    "horror": {"woche": {"tiktok": "18:00", "youtube": "16:00"}, "ohne_langvideo": True},
}
# "ohne_langvideo": An Tagen mit einem Langvideo (16:00, Metricool) laeuft dieser zweite Kurzvideo-Slot nicht. Grund: Auf YouTube
# traten die Fehler "daily posting limit" an Langvideo-Tagen auf (20. und 22.11.), der Fehler vom 24.11. war der dritte Upload in 24 h.


def slot_times(fmt: str, day) -> dict:
    """Uhrzeiten je Plattform fuer ein Format an einem Tag (datetime.date), leer = Format laeuft nicht."""
    plan = SENDEPLAN.get(fmt)
    if plan is None:
        return {pf: FORMATS[fmt]["slot"] for pf in platforms(fmt)}
    return dict(plan.get("ende" if day.weekday() >= 5 else "woche") or {})


def skips_on_long_day(fmt: str) -> bool:
    return bool((SENDEPLAN.get(fmt) or {}).get("ohne_langvideo"))


# Formate, die sich einen Sendeplatz teilen und taeglich abwechseln (2 Shorts pro Tag statt 3).
ROTATION = [["wissen", "waswaerewenn"]]


def rotation_group(fmt: str) -> list:
    return next((g for g in ROTATION if fmt in g), [fmt])


def runs_on(fmt: str, day) -> bool:
    """Ist das Format an diesem Tag (datetime.date) dran?"""
    f = FORMATS[fmt]
    if "weekdays" in f and day.weekday() not in f["weekdays"]:
        return False
    g = rotation_group(fmt)
    return g[day.toordinal() % len(g)] == fmt


def platforms(fmt: str) -> list:
    return FORMATS[fmt].get("platforms", ["tiktok", "youtube"])


def style(fmt: str) -> str:
    return FORMATS[fmt].get("style", fmt)


def dims(fmt: str) -> tuple:
    """(Breite, Hoehe) des fertigen Videos."""
    if FORMATS[fmt].get("orientation") == "landscape":
        return 1920, 1080
    return VIDEO_W, VIDEO_H

VIDEO_W, VIDEO_H, FPS = 1080, 1920, 30
XFADE = 0.35          # Sekunden Uebergang zwischen Szenen
TAIL = 0.8            # Sekunden Nachlauf nach letztem Wort
TARGET_LUFS = -14.0

INVENTORY_DAYS = 3    # Mindestvorrat in Tagen pro Format
WISSEN_SKIP_RESERVE = 14   # Wissen wird nicht neu produziert, solange so viele Drive-Reserve-Videos (mit Texten) da sind
MAX_PRODUCE_PER_RUN = 3    # Claude-Limit schonen (V-007)
ELEVEN_DAILY_RESERVE = 3000  # Credits pro Tag, die bis zum Reset frei bleiben muessen


def paused() -> bool:
    """Not-Aus: Datei PAUSE im Code-Repo oder im Daten-Branch."""
    return any((d / n).exists() for d in (ROOT, DATA) for n in ("PAUSE", "STOP"))
