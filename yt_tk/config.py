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
        "slot": "10:00",
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
        "slot": "15:00",
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
        "slot": "18:00",
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
}

VIDEO_W, VIDEO_H, FPS = 1080, 1920, 30
XFADE = 0.35          # Sekunden Uebergang zwischen Szenen
TAIL = 0.8            # Sekunden Nachlauf nach letztem Wort
TARGET_LUFS = -14.0

INVENTORY_DAYS = 3    # Mindestvorrat in Tagen pro Format
ELEVEN_DAILY_RESERVE = 3000  # Credits pro Tag, die bis zum Reset frei bleiben muessen


def paused() -> bool:
    """Not-Aus: Datei PAUSE im Code-Repo oder im Daten-Branch."""
    return (ROOT / "PAUSE").exists() or (DATA / "PAUSE").exists()
