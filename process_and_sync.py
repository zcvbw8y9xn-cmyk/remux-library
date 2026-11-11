"""
Remux Data Processor & Link Health Verifier
- ONLY keeps working ALIVE 🟢 links (dead/expired links are deleted)
- Strictly sorts by Tweet Date descending (newest tweets first)
- Deep-extracts titles from tweet text and download pages (including clicking "View Content")
- Converts all foreign titles and accents to clean English
- Evaluates whether each movie is the Best Quality Available (4K UHD vs 1080p Best vs 4K Exists)
- Persistent health cache so dead links are never re-checked
- Syncs clean alive-only list directly to Google Sheets with custom color coding
"""

import asyncio
import csv
import json
import os
import re
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from patchright.async_api import async_playwright

INPUT_FILE = "remux_links.json"
OUTPUT_CSV = "remux_library.csv"
HEALTH_CACHE_FILE = "health_cache.json"
SPREADSHEET_ID = "1oqYjXc5D9eURyHUGNynR9uW9BDKNKWyGtfDBs8j_j8E"

# Curated English translation dictionary for foreign titles
TRANSLATION_MAP = {
    "ゴニン": "Gonin",
    "下妻物語": "Kamikaze Girls",
    "Летят журавли": "The Cranes Are Flying",
    "一一": "Yi Yi",
    "恐怖份子": "The Terrorizers",
    "蘇州河": "Suzhou River",
    "青少年哪吒": "Rebels of the Neon God",
    "千禧曼波": "Millennium Mambo",
    "阿飛正傳": "Days of Being Wild",
    "二〇四六": "2046",
    "墮落天使": "Fallen Angels",
    "幻の光": "Maborosi",
    "嘉年华": "Angels Wear White",
    "遙かな時代の階段を": "The Stairway to the Distant Past",
    "ドーベルマン刑事": "Doberman Cop",
    "はるか, ノスタルジィ": "Haruka Nostalgia",
    "はるか": "Haruka Nostalgia",
    "少年吔，安啦！": "Dust of Angels",
    "砂の女": "Woman in the Dunes",
    "回路": "Pulse",
    "東京フィスト": "Tokyo Fist",
    "寝ても覚めても": "Asako I & II",
    "殺し屋1": "Ichi the Killer",
    "無間道": "Infernal Affairs",
    "龍虎風雲": "City on Fire",
    "実録・安藤昇侠道（アウトロー）伝 烈火": "Deadly Outlaw: Rekka",
    "Csend és kiáltás": "Silence and Cry",
    "Panna zázračnica": "The Miraculous Virgin",
    "Le Chagrin et la pitié": "The Sorrow and the Pity",
    "Mes séances de lutte": "Love Battles",
    "Orphée": "Orpheus",
    "Les Films Lumière": "The Films of the Lumiere Brothers",
    "Le Samouraï": "The Godson (Le Samourai)",
    "Masculin Féminin": "Masculine Feminine",
    "Céline": "Celine",
    "Séance": "Seance",
    "Marketa Lazarová": "Marketa Lazarova",
    "Jeanne Dielman, 23, quai du Commerce, 1080 Bruxelles": "Jeanne Dielman, 23, quai du Commerce, 1080 Bruxelles",
    "Shinji Sōmai": "Luminous Woman",
    "00004": "The Tragedy of W",
    "Kuime": "Over Your Dead Body",
    "Um Filme Falado": "A Talking Picture",
    "O voyeur do telhado": "The Watcher in the Attic",
    "Dueto para Canibais": "Duet for Cannibals",
    "O Inferno /": "L'Inferno",
    "Cabra Marcado Para Morrer": "Twenty Years Later",
    "Les yeux sans visage": "Eyes Without a Face",
    "La tulipe noire": "The Black Tulip",
    "Flammen & Citronen": "Flame & Citron",
}

# Curated link-level metadata overrides
LINK_OVERRIDES = {
    "1gN31F9WWDDI": ("Orpheus", "1950"),
    "5qGZM58hTTST": ("Until the End of the World", "1991"),
    "kz6bwU8DkJCK": ("Dementia", "1955"),
    "fSXIurpBkb5A": ("A Summer's Tale", "1996"),
    "6zjtz2gViTqb": ("Moonlighting", "1982"),
    "u8xXkFhnRL6Z": ("I'm Going Home", "2001"),

    "46W2KcwTQLTJ": ("The Seventh Seal", "1957"),
    "aJPt3l4n2ZzL": ("Village of Eight Gravestones", "1977"),
    "w2zw6U0hUJiS": ("The Ascent", "1977"),
    "zG5C3I9XALpZ": ("A Spring for the Thirsty", "1965"),
    "BfAkqclH2LBK": ("The Legend of Princess Olga", "1984"),
    "XBGI6B1TDLzb": ("The Eve of Ivan Kupalo", "1968"),
    "6w0zPNlFwbBb": ("Earth", "1930"),
    "1L1wKN8h1ZSI": ("Man with a Movie Camera", "1929"),
    "JwfreYklkLRa": ("Olga", "2021"),
    "QV0CqFllkbgD": ("The Long Farewell", "1971"),
    "9sEXctpn2BjJ": ("The Tragedy of W", "1984"),
    "A1fbifwh2LCJ": ("Love Battles", "2013"),
    "17x7mfgjwZiC": ("Aquaman", "2018"),
    "qrvRnH5nUBQY": ("Irreversible", "2002"),
    "uEVrHe5HmDZY": ("Ford v Ferrari", "2019"),
    "MrLOOGp3lJ6Y": ("Beetlejuice Beetlejuice", "2024"),
    "7HeKjG5XQBxY": ("The Possessed", "1965"),
    "GISUnLplGZKQ": ("Volver", "2006"),
    "bw3hTb4jELgC": ("The Rachel Papers", "1989"),
    "pqXiya5DFDgL": ("Here", "2024"),
    "5mDgaboHRRZD": ("Love Me If You Dare", "2003"),
    "pxBuOKg1HRjS": ("Jude", "1996"),
    "2JuarKxjBJTI": ("Color of Night", "1994"),
    "AwoqvfpxnRZK": ("Secretary", "2002"),
    "qid3jWxhmThK": ("Malena", "2000"),
    "djWB7D4zzLAS": ("After Life", "1998"),
    "aYnNmGgFWRYJ": ("Swing Girls", "2004"),
    "m549zfxTzRKA": ("Linda Linda Linda", "2005"),
    "x5ZSbCgx2Dib": ("After the Storm", "2016"),
    "K97gjaxFyZrL": ("Like Father, Like Son", "2013"),
    "Z58TiO532ZCD": ("Still Walking", "2008"),
    "mMlsOT4V2DzK": ("Picnic", "1996"),
    "Sl7HbXgHwb7D": ("Distance", "2001"),
    "2SPTqKxlQZ6R": ("Shoplifters", "2018"),
    "SHbJmX5nxJ6S": ("Maborosi", "1995"),
    "FszKOaxz2RgT": ("Lolita", "1997"),
    "m7KMSd8h0LQA": ("Falling Down", "1993"),
    "QPVlTNkVTDxD": ("Csontvary", "1980"),
    "F0FsvU0BADRB": ("The Sorrow and the Pity", "1969"),
    "d8ECLEsnlL4K": ("Voyage of the Rock Aliens", "1984"),
    "rPhk3VkTlD7b": ("Essential Polish Animation, Vol. 2", "2024"),
    "SVwr2RlRwTAb": ("Essential Polish Animation, Vol. 1", "2024"),
    "ZVQ8jNlhGRDB": ("Silence and Cry", "1968"),
    "NjrYjd0zjbCJ": ("The Miraculous Virgin", "1967"),
    "WUqN6VND": ("Over Your Dead Body", "2014"),
    "1uYbThZaLcIMnaWquhoSajGLIvBXyEC6y": ("I'm Going Home", "2001"),
    "1KfbahTk_xGDXMucPghDKyOdN8yq1w8Ni": ("The End of Evangelion", "1997"),
    "1cyRFz0WdzS0MiGdMJAPuvJp1zI33oKhs": ("Lolita", "1997"),
    "m9vWw503wZxB": ("The Exiles", "1961"),
    "gDVLkuwxkDiA": ("Trainspotting", "1996"),
    "ZJiDky": ("Armageddon", "1998"),
    "xYmCNYsxHBIC": ("Perdida", "2009"),
    "XHgMDKx3HR6I": ("Meditation on Violence", "1949"),
    "MdodCHhD0TYB": ("Luminous Woman", "1987"),
    "1PB4eDBMQuaxPaK3vPlas-83N3c4JwsTO": ("Businessman", "2012"),
    "9JSyfWpx3BjI": ("Freeze Me", "2000"),
    "qN9ZjvpXkR7I": ("A Night in Nude", "1993"),
    "0xCRcV511DYL": ("Pearls of the Deep", "1965"),
    "by0sfK94": ("Blue Velvet", "1986"),
    "wCJptEoBhDqD": ("The Guest", "2014"),
    "PD4gYRolyRjQ": ("Affliction", "1997"),
    "6RNXAI4Y": ("Unknown Pleasures", "2002"),
    "mQImcQl11RCT": ("Viva Maria!", "1965"),
    "UNWBBBsDUTQI": ("Sansho the Bailiff", "1954"),
    "a5zSREkHRJpC": ("Alien", "1979"),
    "lkt0Mc1BnB4J": ("Amelie", "2001"),
    "EIL2VR9FQDIB": ("The Fifth Horseman Is Fear", "1965"),
    "HzH69Ytn1ZCL": ("Solo Leveling (Season 2)", "2025"),
    "8L2pQZkHhbgR": ("Flame & Citron", "2008"),
    "AljXRE8TxJbJ": ("Blue Collar", "1978"),
    "txWj4EtBCbYK": ("Fate/Grand Order: Camelot", "2020"),
    "BtbbpB0H3ZwA": ("Dan Da Dan (Season 1)", "2024"),
    "eLBGsAtTGZ7Z": ("Dan Da Dan (Season 2)", "2025"),
    "sxOgEQllRR7a": ("Moonlighting", "1982"),
    "BQZc7zgVRJIY": ("The Maya Deren Collection", "1943-1959"),
    "PcEiEvpXBJpS": ("Mel Brooks Collection", "1967-1995"),
    "yMsSKxhnATqD": ("TCM Archives: Forbidden Hollywood Vol. 1-3", "1931-1934"),
    "VEIDHbonyIyK": ("Poetry", "2010"),
}

# Known movies where an official 4K UHD physical disc release exists in the real world
KNOWN_4K_EXISTS = {
    "True Lies",
    "Terminator 2 Judgment Day",
    "The Bridge on the River Kwai",
    "Blow-Up",
    "Apocalypse Now",
    "Dog Day Afternoon",
    "Vertigo",
    "The Seventh Seal",
    "The Graduate",
    "Lost in Translation",
    "Daisies",
    "Kung Fu Hustle",
    "Battle Royale",
    "Under the Skin",
    "Cape Fear",
    "Chungking Express",
    "Death Becomes Her",
    "The Long Goodbye",
    "The Presidio",
    "Nashville",
    "Badlands",
    "Rio Lobo",
    "The House That Jack Built",
    "Melancholia",
    "Antichrist",
    "A Place in the Sun",
    "Angst",
    "Nights of Cabiria",
    "Written on the Wind",
    "Magnificent Obsession",
    "Brief Encounter",
    "Bigger than Life",
    "Days of Being Wild",
    "2046",
    "Fallen Angels",
    "Nobody Knows",
    "After Life",
    "Shoplifters",
    "The Chaser",
    "The Yellow Sea",
    "Imitation Of Life",
    "Red Desert",
    "Kwaidan",
    "Doberman Cop",
    "Shadows of Forgotten Ancestors",
    "Lolita",
    "The Sorrow and the Pity",
    "The End of Evangelion",
    "Lancelot of the Lake",
}

# Titles where a 1080p Blu-ray exists, but current link is DVD
DVD_UPGRADE_EXISTS = {
    "Cabiria",
    "Secret Things",
    "The Films of the Lumiere Brothers",
    "Colossal Youth",
}


def evaluate_quality_tier(quality_str: str, title: str) -> str:
    """
    Evaluates whether this copy is the best quality available in the real world.
    - 4K UHD Remux: Peak quality available (⭐ Yes (4K UHD))
    - 1080p Remux: If no 4K exists in the world, it's the definitive best available (🟢 Yes (1080p Best))
    - 1080p Remux: If an official 4K disc exists, flag it (⚠️ 4K UHD Exists)
    - DVD Remux: If no 1080p exists, DVD is the definitive best available (📀 Yes (DVD is Best))
    - DVD Remux: If 1080p exists, flag it (⚠️ 1080p Exists)
    """
    q_lower = quality_str.lower()

    if "4k" in q_lower or "2160p" in q_lower or "uhd" in q_lower:
        return "⭐ Yes (4K UHD)"

    if "dvd" in q_lower or "576p" in q_lower or "480p" in q_lower or "480i" in q_lower:
        if title in DVD_UPGRADE_EXISTS or title in KNOWN_4K_EXISTS:
            return "⚠️ 1080p Exists"
        return "📀 Yes (DVD is Best)"

    if title in KNOWN_4K_EXISTS:
        return "⚠️ 4K UHD Exists"

    return "🟢 Yes (1080p Best)"


EXACT_TITLE_TRANSLATIONS = {
    "shi": "Poetry",
    "jagten": "The Hunt",
    "el sur": "The South",
    "les yeux sans visage": "Eyes Without a Face",
    "flammen & citronen": "Flame & Citron",
}


def clean_to_english_title(text: str) -> str:
    """
    Translates foreign titles to English and strips non-ASCII accents and symbols.
    """
    if not text or text == "Unknown Title":
        return text

    # Direct translation check (specific phrases safe against description false-positives)
    for foreign_k, eng_v in TRANSLATION_MAP.items():
        if foreign_k in text:
            text = eng_v
            break

    # If title has slash like 'O voyeur do telhado / The Watcher in the Attic', prefer English segment
    if " / " in text:
        parts = [p.strip() for p in text.split(" / ") if p.strip()]
        if len(parts) >= 2:
            p0_ascii = sum(1 for c in parts[0] if ord(c) < 128)
            p1_ascii = sum(1 for c in parts[1] if ord(c) < 128)
            p0_non_en_prefix = bool(re.match(r'^(O|Os|As|Um|Uma|La|Le|Les|El|Los|Las|Il|Un|Una|Dueto|Cabra)\s+', parts[0], re.I))
            p1_en_prefix = bool(re.match(r'^(The|A|An)\s+', parts[1], re.I))
            if (p0_ascii < len(parts[0]) * 0.5 and p1_ascii > 0) or (p0_non_en_prefix and p1_en_prefix):
                text = parts[1]
            elif p0_ascii > 0:
                text = parts[0]
            else:
                text = parts[1]

    # Clean typographic punctuation before unicode stripping
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("•", "-").replace("–", "-").replace("—", "-")
    text = text.replace("\xa0", " ").replace("\u3000", " ")

    # Strip Asian/CJK characters
    text = re.sub(r'[\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\uff00-\uffef\u4e00-\u9faf]+', '', text)

    # Normalize accents (e.g. é -> e, à -> a, ó -> o, etc.)
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')

    # Clean brackets and whitespace
    text = re.sub(r'[\[\]]', '', text).strip(" -:\t\n*#,.")
    text = re.sub(r'\s+', ' ', text)

    # Move trailing ', The' to leading 'The ' (e.g. 'Fifth Horseman Is Fear, The')
    m_the = re.match(r'^(.+?),\s+The$', text, re.I)
    if m_the:
        text = f"The {m_the.group(1)}"

    # Safe exact-title translations after cleanup
    if text.lower() in EXACT_TITLE_TRANSLATIONS:
        text = EXACT_TITLE_TRANSLATIONS[text.lower()]

    # Ensure no URL leaked through as a title (safeguard)
    if re.search(r'https?://|t\.co/|transfer\.it/|gofile\.io/|ibb\.co/|\.jpg\)?|\.png\)?', text, re.I) and ".com for murder" not in text.lower():
        return "Unknown Title"

    if not is_valid_movie_title(text):
        return "Unknown Title"

    return text or "Unknown Title"


INVALID_EXACT_TITLES = {
    "ray", "blu", "remux", "bd", "dvd", "rip", "uhd", "4k", "1080p", "720p", "2160p",
    "hdr", "dv", "dolby", "vision", "atmos", "dts", "truehd", "flac", "aac", "hevc",
    "x264", "x265", "h264", "h265", "re-up", "reup", "reupload", "link", "download",
    "collection", "archive", "part", "disc", "volume", "vol", "subs", "unknown",
    "unknown title", "bluray", "bdremux", "dvdrip", "webdl", "webrip", "criterion",
    "arrow", "radiance", "eureka", "kino", "lorber", "b-ray", "blu-ray"
}


def is_valid_movie_title(title: str) -> bool:
    """
    Validates whether a candidate string is a plausible movie title
    and not a media format fragment (e.g. 'ray', '1080p', 'Blu-ray', 'remux').
    """
    if not title or not isinstance(title, str):
        return False
    t = title.strip().strip("-: \t\n*#[],")
    t_lower = t.lower()

    # 1. Exact match against blacklisted single words or format terms
    if t_lower in INVALID_EXACT_TITLES:
        return False

    # 2. Too short (except genuine 1-2 letter titles like 'GO', 'Pi', 'Io', 'Us', 'M', 'O', 'Z')
    if len(t) < 2 and t_lower not in ["m", "o", "z"]:
        return False

    # 3. Contains URLs or domain remnants
    if re.search(r'https?://|transfer\.it|gofile\.io|pixeldrain|mega\.nz|t\.co|\.jpg|\.png', t_lower):
        return False

    # 4. Purely composed of format / codec / resolution / rip tokens
    words = set(re.findall(r'[a-z0-9]+', t_lower))
    format_tokens = {
        "1080p", "2160p", "720p", "480p", "576p", "4k", "uhd", "bluray", "remux", "bd",
        "dvd", "rip", "hdr", "dv", "hevc", "x264", "x265", "h264", "h265", "dts", "flac",
        "aac", "truehd", "atmos", "gb", "mb", "reup", "re", "up", "ray", "blu", "b", "subs"
    }
    if words and words.issubset(format_tokens):
        return False

    # 5. Starts with obvious format specification like '1080p BluRay REMUX'
    if re.search(r'^(1080p|2160p|720p|4k|uhd|bluray|bd\s+remux|dvd\s+remux)\b', t_lower):
        return False

    return True


def sanitize_technical_terms(text: str) -> str:
    """
    Normalizes hyphenated technical terms (e.g. 'Blu-ray' -> 'BluRay', 'Ultra-HD' -> 'UltraHD')
    so that hyphens inside technical specs are never confused with movie title separators.
    """
    substitutions = [
        (r'\bblu\s*-\s*ray\b', 'BluRay'),
        (r'\bultra\s*-\s*hd\b', 'UltraHD'),
        (r'\bweb\s*-\s*dl\b', 'WebDL'),
        (r'\bweb\s*-\s*rip\b', 'WebRip'),
        (r'\bbd\s*-\s*remux\b', 'BDRemux'),
        (r'\bbd\s*-\s*rip\b', 'BDRip'),
        (r'\bdvd\s*-\s*rip\b', 'DVDRip'),
        (r'\bdvd\s*-\s*remux\b', 'DVDRemux'),
        (r'\b4k\s*-\s*remux\b', '4K Remux'),
        (r'\b1080p\s*-\s*remux\b', '1080p Remux'),
        (r'\bre\s*-\s*up\b', 'ReUp'),
        (r'\bre\s*-\s*upload\b', 'ReUpload'),
    ]
    for pattern, repl in substitutions:
        text = re.sub(pattern, repl, text, flags=re.I)
    return text


def clean_text_for_title(raw_text: str):
    """
    Extracts English Title and Year from tweet text.
    Handles multi-line, director credits, bracketed foreign titles, and single-line tweets.
    Guarantees no 'ray' or technical format fragments are returned as titles.
    """
    norm_text = raw_text.replace("\xa0", " ").replace("\u3000", " ")
    # Normalize hyphenated technical specs first
    sanitized = sanitize_technical_terms(norm_text)

    # Clean image urls, bracketed urls, or trailing url fragments
    cleaned_text = re.sub(r'\(\s*(?:https?://|i\.ibb\.co)[^\)]*\)', '', sanitized)
    cleaned_text = re.sub(r'https?://\S*', '', cleaned_text)
    lines = [l.strip() for l in cleaned_text.strip().split("\n") if l.strip()]
    if not lines:
        return "Unknown Title", "Unknown"

    for foreign_k, eng_v in TRANSLATION_MAP.items():
        if foreign_k in norm_text:
            m_yr = re.search(r'\b(19\d{2}|20\d{2})\b', norm_text)
            yr = m_yr.group(1) if m_yr else "Unknown"
            return eng_v, yr

    # Filter out archive collection headers, link lines, or courtesy/remux prefix lines
    filtered = []
    for l in lines:
        if re.search(r'^\d+(?:st|nd|rd|th)\s+film\s+of|archive collection', l, re.I):
            continue
        if re.search(r'transfer\.it|gofile\.io|pixeldrain|mega\.nz|t\.co|drive\.google|ibb\.co|\.jpg|\.png', l, re.I):
            continue
        if re.search(r'^(?:remux[!:\s]|courtesy\s+of|@\w+$)', l, re.I):
            continue
        filtered.append(l)

    if not filtered:
        filtered = lines

    # Pattern 0: Non-Latin original title followed by parenthesized English title & year
    # e.g. '色‧戒 (Lust, Caution - 2007)', '無常 (This Transient Life, 1970)', 'ひそひそ星 (The Whispering Star, 2015)'
    for line in filtered[:2]:
        m0 = re.search(r'^\s*[^\x00-\x7F][^(]*\(\s*([A-Za-z0-9\s\'\-\:\,\.\!\?&/]+?)\s*[,\-–]\s*(19\d{2}|20\d{2})\s*\)', line)
        if m0:
            t = m0.group(1).strip(" -:\t\n*#[],/")
            if "/" in t:
                t = t.split("/")[0].strip()
            if is_valid_movie_title(t):
                return t, m0.group(2)

    # Pattern A: English Title [Foreign Title] (Director, Year) or (Year)
    for line in filtered[:2]:
        mA = re.search(r'^([A-Za-z0-9\s\'\-\:\,\.\!\?&]+?)\s*(?:\[[^\]]+\])\s*(?:[\(\[](?:[^\)\]]*?\b(19\d{2}|20\d{2})\b[^\)\]]*)[\)\]])?', line)
        if mA:
            t = mA.group(1).strip(" -:\t\n*#[],")
            m_yr = re.search(r'\b(19\d{2}|20\d{2})\b', norm_text)
            yr = m_yr.group(1) if m_yr else "Unknown"
            if is_valid_movie_title(t):
                return t, yr

    # Pattern B: Det Sjunde Inseglet - The Seventh Seal (requires non-format words on both sides)
    m_seal = re.search(r'^([A-Za-z0-9\s\'\,\.\!\?&]+?)\s+-\s+([A-Za-z0-9\s\'\:\,\.\!\?&]+?)(?:\s+CRITERION|\s+1080p|\s+bluray|\s+remux|$)', filtered[0], re.I)
    if m_seal:
        left = m_seal.group(1).strip(" -:\t\n*#[],")
        right = m_seal.group(2).strip(" -:\t\n*#[],")
        if is_valid_movie_title(right) and not re.search(r'^(1080p|4k|bluray|bd|remux)', left, re.I):
            m_yr = re.search(r'\b(19\d{2}|20\d{2})\b', norm_text)
            yr = m_yr.group(1) if m_yr else "Unknown"
            return right, yr

    # Pattern E0: Standard Title (Year) or Title (Year, Director) on first line before checking multi-line bonus text
    mE0 = re.search(r'([^\n\r(\[]+?)\s*[\(\[](?:[^\)\]]*?\b(19\d{2}|20\d{2})\b[^\)\]]*)[\)\]]', filtered[0])
    if mE0:
        t = mE0.group(1).strip(" -:\t\n*#[],")
        if is_valid_movie_title(t):
            return t, mE0.group(2)

    # Pattern C: Multi-line English / Foreign / Director, Year
    for i in range(1, min(len(filtered), 5)):
        m_dir_year = re.search(r'\b(19\d{2}|20\d{2})\b', filtered[i])
        if m_dir_year and ('directed' in filtered[i].lower() or ',' in filtered[i] or 'by' in filtered[i].lower() or 'shepitko' in filtered[i].lower() or 'illienko' in filtered[i].lower() or 'dovzhenko' in filtered[i].lower() or 'vertov' in filtered[i].lower() or 'muratova' in filtered[i].lower() or 'grappe' in filtered[i].lower()):
            cand = filtered[0].strip(" -:\t\n*#[],")
            if is_valid_movie_title(cand):
                return cand, m_dir_year.group(1)

    # Pattern D: Line with Title YYYY
    for line in filtered[:3]:
        mC = re.search(r'^([A-Za-z0-9\s\'\-\:\,\.\!\?&]+?)\s+\b(19\d{2}|20\d{2})\b(?:\s+.*)?$', line.strip(), re.I)
        if mC:
            t = mC.group(1).strip(" -:\t\n*#[],")
            if is_valid_movie_title(t):
                return t, mC.group(2)

    # Pattern E: Standard Title (Year) on subsequent lines
    for line in filtered[:3]:
        mE = re.search(r'([^\n\r(\[]+?)\s*[\(\[](?:[^\)\]]*?\b(19\d{2}|20\d{2})\b[^\)\]]*)[\)\]]', line)
        if mE:
            t = mE.group(1).strip(" -:\t\n*#[],")
            if is_valid_movie_title(t):
                return t, mE.group(2)

    m_all_yr = re.search(r'\b(19\d{2}|20\d{2})\b', norm_text)
    return "Unknown Title", m_all_yr.group(1) if m_all_yr else "Unknown"


def extract_title_from_filename(filename: str):
    """Parse release filename like 'Beetlejuice.Beetlejuice.2024.UHD.Remux.mkv' or 'Viva_Maria(1965)_BD-Remux.mkv'"""
    ascii_name = unicodedata.normalize('NFKD', filename).encode('ascii', 'ignore').decode('utf-8')
    cleaned = re.sub(r'\s+', ' ', ascii_name.replace(".", " ").replace("_", " ")).strip()
    m = re.search(r'^([A-Za-z0-9\s\'\-\:\,\!\?&]+?)\s*[\(\[]?\b(19\d{2}|20\d{2})\b[\)\]]?', cleaned)
    if m:
        cand = m.group(1).strip(" -:,")
        m_the = re.match(r'^(.+?),\s+The$', cand, re.I)
        if m_the:
            cand = f"The {m_the.group(1)}"
        if is_valid_movie_title(cand):
            return cand, m.group(2)
    return None, None


def extract_format_info(raw_text: str) -> str:
    """Extracts quality markers (4K, 1080p, 720p, 576p DVD, 480p DVD, DVD, HDR, DV, file size)."""
    tags = []
    if re.search(r'\b4K\b|2160p|UHD', raw_text, re.I):
        tags.append("4K UHD")
    elif re.search(r'\b1080p\b|1080i\b|\bbd[\s\-]?remux\b', raw_text, re.I):
        tags.append("1080p")
    elif re.search(r'\b720p\b', raw_text, re.I):
        tags.append("720p")
    elif re.search(r'\b576p\b|576i\b', raw_text, re.I):
        tags.append("576p DVD")
    elif re.search(r'\b480p\b|480i\b', raw_text, re.I):
        tags.append("480p DVD")
    elif re.search(r'\bDVD\b|dvd[\s\-]?remux', raw_text, re.I):
        tags.append("DVD")

    if re.search(r'\bHDR\b', raw_text, re.I):
        tags.append("HDR")
    if re.search(r'\bDV\b|Dolby Vision', raw_text, re.I):
        tags.append("DV")
    if re.search(r'\bREMUX\b|bdremux|dvdremux', raw_text, re.I):
        tags.append("REMUX")

    msize = re.search(r'(\d+(?:\.\d+)?\s*(?:GB|GiB|MB))', raw_text, re.I)
    if msize:
        tags.append(msize.group(1).upper())

    return " | ".join(tags) if tags else "Remux"


async def check_link_health(link: str, page) -> tuple[str, str | None, str | None]:
    """
    Checks whether the file link is still alive or expired.
    Deep-inspects the download page (clicking 'View content' on transfer.it if needed)
    to extract the exact movie title and year.
    Returns: (status, fallback_title, fallback_year)
    """
    try:
        if "transfer.it" in link:
            await page.goto(link, wait_until="domcontentloaded", timeout=12000)
            await page.wait_for_timeout(3000)
            body = (await page.inner_text("body")).lower()

            if any(term in body for term in ["oops", "can’t find this transfer", "can't find this transfer", "expired", "removed", "incorrect"]):
                return "Dead 🔴", None, None

            if "ready to download" in body or "1 file" in body or "files" in body:
                btn = await page.query_selector("text=View content")
                if btn:
                    try:
                        await btn.click()
                        await page.wait_for_timeout(1500)
                    except Exception:
                        pass

                body_after = await page.inner_text("body")
                lines = [l.strip() for l in body_after.split("\n") if l.strip()]

                for l in lines:
                    if any(ext in l.lower() for ext in [".mkv", ".mp4", ".avi", ".iso"]):
                        fn_title, fn_year = extract_title_from_filename(l)
                        if fn_title:
                            return "Alive 🟢", fn_title, fn_year

                for idx, line in enumerate(lines):
                    if line.lower() == "ready to download" and idx + 1 < len(lines):
                        cand = lines[idx + 1]
                        fn_title, fn_year = extract_title_from_filename(cand)
                        if fn_title:
                            return "Alive 🟢", fn_title, fn_year
                        m = re.search(r'^([^\n\r(\[]+?)\s*[\(\[](19\d{2}|20\d{2})[\)\]]', cand)
                        if m:
                            return "Alive 🟢", m.group(1).strip(), m.group(2)

                return "Alive 🟢", None, None

            return "Dead 🔴", None, None

        elif "gofile.io" in link:
            await page.goto(link, wait_until="domcontentloaded", timeout=12000)
            await page.wait_for_timeout(3500)
            body = (await page.inner_text("body")).lower()
            if "this content does not exist" in body or "error-notfound" in body or "not found" in body:
                return "Dead 🔴", None, None
            if "download" in body or "files" in body:
                lines = [l.strip() for l in (await page.inner_text("body")).split("\n") if l.strip()]
                for l in lines:
                    if any(ext in l.lower() for ext in [".mkv", ".mp4"]):
                        fn_title, fn_year = extract_title_from_filename(l)
                        if fn_title:
                            return "Alive 🟢", fn_title, fn_year
                    m = re.search(r'^([^\n\r(\[]+?)\s*[\(\[](19\d{2}|20\d{2})[\)\]]', l)
                    if m and not re.search(r'guest|account|file manager|premium', m.group(1), re.I):
                        return "Alive 🟢", m.group(1).strip(), m.group(2)
                return "Alive 🟢", None, None
            return "Dead 🔴", None, None

        elif "pixeldrain.com" in link:
            pid = link.split("/")[-1]
            try:
                req = urllib.request.Request(f"https://pixeldrain.com/api/file/{pid}/info", headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    pdata = json.loads(resp.read().decode())
                    if pdata.get("success"):
                        pname = pdata.get("name", "")
                        fn_title, fn_year = extract_title_from_filename(pname)
                        return "Alive 🟢", fn_title, fn_year
            except Exception:
                pass
            return "Alive 🟢", None, None

        elif "mega.nz" in link:
            await page.goto(link, wait_until="domcontentloaded", timeout=12000)
            await page.wait_for_timeout(3500)
            body = (await page.inner_text("body")).lower()
            if any(term in body for term in ["no longer available", "removed", "does not exist", "invalid link"]):
                return "Dead 🔴", None, None
            return "Alive 🟢", None, None

        return "Alive 🟢", None, None

    except Exception:
        return "Dead 🔴", None, None


def get_letterboxd_link(title: str, year: str) -> str:
    """Generates direct Letterboxd search URL for the movie."""
    if not title or title == "Unknown Title":
        return ""
    q = f"{title} {year}".strip() if year and year != "Unknown" else title.strip()
    return f"https://letterboxd.com/search/{urllib.parse.quote_plus(q)}/"


def get_imdb_link(title: str, year: str) -> str:
    """Generates direct IMDb search URL for the movie."""
    if not title or title == "Unknown Title":
        return ""
    q = f"{title} {year}".strip() if year and year != "Unknown" else title.strip()
    return f"https://www.imdb.com/find/?q={urllib.parse.quote_plus(q)}&s=tt"


def parse_cached_entry(entry):
    """Parses status and timestamp from cache, supporting both legacy strings and new dict formats."""
    if isinstance(entry, dict):
        return entry.get("status", "Pending"), entry.get("checked_at", "1970-01-01T00:00:00Z")
    elif isinstance(entry, str):
        return entry, "1970-01-01T00:00:00Z"
    return "Pending", "1970-01-01T00:00:00Z"


def to_direct_download_url(url: str) -> str:
    """Converts hosts with direct streaming endpoints to raw file URLs (e.g. Pixeldrain for FDM/JDownloader)."""
    if "pixeldrain.com/u/" in url:
        pid = url.split("pixeldrain.com/u/")[-1].split("?")[0].strip("/")
        return f"https://pixeldrain.com/api/file/{pid}?download"
    return url


def export_download_batches(alive_rows):
    """Exports raw download links for batch downloading in Free Download Manager (FDM), JDownloader, or Real-Debrid."""
    with open("downloads_all_alive.txt", "w", encoding="utf-8") as f:
        for r in alive_rows:
            f.write(to_direct_download_url(r["File Link"]) + "\n")

    with open("downloads_4k_alive.txt", "w", encoding="utf-8") as f:
        for r in alive_rows:
            if "4K" in r.get("Quality", ""):
                f.write(to_direct_download_url(r["File Link"]) + "\n")

    with open("downloads_newest_50.txt", "w", encoding="utf-8") as f:
        for r in alive_rows[:50]:
            f.write(to_direct_download_url(r["File Link"]) + "\n")

    print("📦 Exported batch download link lists (downloads_all_alive.txt, downloads_4k_alive.txt, downloads_newest_50.txt).")


def send_webhook_notifications(alive_rows, dead_count):
    """Sends optional Discord or Telegram notifications if configured in config.json or environment."""
    config = {}
    config_file = "config.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            pass

    discord_url = config.get("discord_webhook_url") or os.environ.get("DISCORD_WEBHOOK_URL")
    telegram_token = config.get("telegram_bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN")
    telegram_chat = config.get("telegram_chat_id") or os.environ.get("TELEGRAM_CHAT_ID")

    if not discord_url and not (telegram_token and telegram_chat):
        return

    total_alive = len(alive_rows)
    uhd_count = sum(1 for r in alive_rows if "4K" in r.get("Quality", ""))
    dvd_count = sum(1 for r in alive_rows if "DVD" in r.get("Quality", ""))
    newest_3 = [f"• {r['Title']} ({r['Year']}) — {r['Quality']}" for r in alive_rows[:3]]
    newest_text = "\n".join(newest_3)

    if discord_url:
        try:
            payload = {
                "embeds": [{
                    "title": "🎬 Remux Library Updated",
                    "color": 3066993,
                    "description": f"**{total_alive} active movies** currently available in the library.",
                    "fields": [
                        {"name": "⭐ 4K UHD Remuxes", "value": str(uhd_count), "inline": True},
                        {"name": "📀 DVD Remuxes", "value": str(dvd_count), "inline": True},
                        {"name": "🗑️ Pruned Dead Links", "value": str(dead_count), "inline": True},
                        {"name": "✨ Latest Additions", "value": newest_text or "N/A", "inline": False},
                        {"name": "📊 Google Sheet", "value": f"[Open Library](https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID})", "inline": True}
                    ],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }]
            }
            req = urllib.request.Request(
                discord_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "RemuxBot/1.0"}
            )
            urllib.request.urlopen(req, timeout=10)
            print("📣 Discord notification sent successfully!")
        except Exception as e:
            print(f"⚠️ Discord notification failed: {e}")

    if telegram_token and telegram_chat:
        try:
            tg_lines = [
                "🎬 *Remux Library Update*",
                "",
                f"• Active movies: *{total_alive}*",
                f"• 4K UHD: *{uhd_count}*",
                f"• DVD Remux: *{dvd_count}*",
                "",
                "*Latest Additions:*",
                newest_text,
                "",
                f"[Open Google Sheet](https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID})"
            ]
            tg_text = "\n".join(tg_lines)
            tg_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
            payload = {
                "chat_id": telegram_chat,
                "text": tg_text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            req = urllib.request.Request(
                tg_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=10)
            print("📣 Telegram notification sent successfully!")
        except Exception as e:
            print(f"⚠️ Telegram notification failed: {e}")


def is_non_remux_link(raw_text: str, file_link: str, all_links: list[str]) -> bool:
    """
    When a tweet contains multiple links (e.g. both a REMUX and an Encode/Stream/Extras mirror),
    identify links that are explicitly non-remux so only actual remux links are indexed.
    Never drops links when the tweet only has a single file link.
    """
    if len(all_links) <= 1 or not raw_text:
        return False

    # Rejoin X.com wrapped URLs so we can inspect the text adjacent to each link
    norm = re.sub(r'(https?://)\s*\n\s*', r'\1', raw_text)
    for _ in range(2):
        norm = re.sub(r'(https?://[^\s]*?(?:/|#))\s*\n\s*', r'\1', norm)
    norm = re.sub(r'(https?://drive\.google\.com/[^\s]*?)\s*\n\s*([A-Za-z0-9_\-/?=&]+)', r'\1\2', norm)

    idx = norm.find(file_link)
    if idx == -1 and len(file_link) > 20:
        idx = norm.find(file_link[:28])

    low_all = norm.lower()
    has_transfer_remux_alt = any("transfer.it" in u and u != file_link for u in all_links)

    if idx != -1:
        after = norm[idx + len(file_link): idx + len(file_link) + 45]
        # Stop at the next URL so we only inspect this link's own annotation
        after = re.split(r'https?://', after)[0].lower()
        before = norm[max(0, idx - 30): idx].lower()

        if re.search(r'(?:^|[\s\-…\(])(?:encode|stream)\b', after):
            return True
        if re.search(r'\bextras\s*:\s*$', before.strip()):
            return True

        # Check explicit encode size in tweet text matching this link's annotated size
        m_enc_sz = re.search(r'encode\s*[:\(]?\s*(\d+(?:[.,]\d+)?)\s*(?:gb|gib)', low_all)
        m_rem_sz = re.search(r'remux\s*[:\(]?\s*(\d+(?:[.,]\d+)?)\s*(?:gb|gib)', low_all)
        m_link_sz = re.search(r'\((\d+(?:[.,]\d+)?)\s*(?:gb|gib)', after)
        if m_enc_sz and m_link_sz:
            enc_val = m_enc_sz.group(1).replace(",", ".")
            link_val = m_link_sz.group(1).replace(",", ".")
            if enc_val == link_val and (not m_rem_sz or m_rem_sz.group(1).replace(",", ".") != link_val):
                return True

        # Common split pattern: tweet offers Transfer.it Remux + Drive Encode (not joined by 'or')
        if "drive.google.com" in file_link and has_transfer_remux_alt:
            if ("encode" in low_all or "stream" in low_all) and not re.search(r'\bor\b\s*$', before.strip()):
                return True

    # Ordered season/pack lines matching link order (e.g. 'S01 - encodes\nS02 - Remux')
    spec_lines = [l.strip() for l in norm.split("\n") if l.strip() and re.search(r'\b(?:remux|encodes?|extras)\b', l, re.I) and "http" not in l.lower()]
    if len(spec_lines) == len(all_links) and file_link in all_links:
        pos = all_links.index(file_link)
        line_low = spec_lines[pos].lower()
        if ("encode" in line_low or "extras" in line_low) and "remux" not in line_low:
            if any("remux" in sl.lower() for sl in spec_lines):
                return True

    return False


async def process_and_verify():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ {INPUT_FILE} not found!")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    hits = data.get("hits", [])
    print(f"📊 Processing {len(hits)} scraped posts...")

    # Load persistent health cache
    health_cache = {}
    if os.path.exists(HEALTH_CACHE_FILE):
        try:
            with open(HEALTH_CACHE_FILE, "r", encoding="utf-8") as f:
                health_cache = json.load(f)
        except Exception:
            health_cache = {}

    rows = []
    links_to_check = []

    for entry in hits:
        text = entry.get("text", "")
        tweet_url = entry.get("tweet_url", "")
        raw_time = entry.get("timestamp", "")
        tweet_date = raw_time[:16].replace("T", " ") if raw_time else "Unknown"

        title, year = clean_text_for_title(text)
        quality = extract_format_info(text)

        entry_links = entry.get("file_links", [])
        for file_link in entry_links:
            if is_non_remux_link(text, file_link, entry_links):
                continue
            host = file_link.split("/")[2] if "/" in file_link else "unknown"
            cached_status, cached_time = parse_cached_entry(health_cache.get(file_link, "Pending"))

            # Check LINK_OVERRIDES first
            eff_title = title
            eff_year = year
            for k, (ov_t, ov_y) in LINK_OVERRIDES.items():
                if k in file_link:
                    eff_title = ov_t
                    eff_year = ov_y
                    break

            if not is_valid_movie_title(eff_title):
                eff_title = "Unknown Title"

            item = {
                "Tweet Date": tweet_date,
                "Title": eff_title,
                "Year": eff_year,
                "Quality": quality,
                "Best Quality?": "Pending",
                "File Host": host,
                "File Link": file_link,
                "Letterboxd": get_letterboxd_link(eff_title, eff_year),
                "IMDb": get_imdb_link(eff_title, eff_year),
                "Status": cached_status,
                "Tweet URL": tweet_url,
                "_raw_time": raw_time or "1970-01-01",
            }
            rows.append(item)
            if cached_status == "Pending" or (cached_status != "Dead 🔴" and (eff_title == "Unknown Title" or not is_valid_movie_title(eff_title))):
                links_to_check.append(file_link)

    # Periodic Maintenance: Re-verify up to 10 active links older than 21 days
    now_utc = datetime.now(timezone.utc)
    recheck_candidates = []
    for flink, entry in health_cache.items():
        st, ctime = parse_cached_entry(entry)
        if "Alive" in st and flink not in links_to_check:
            try:
                c_dt = datetime.fromisoformat(ctime.replace("Z", "+00:00"))
                age_days = (now_utc - c_dt).total_seconds() / 86400
                if age_days > 21:
                    recheck_candidates.append((age_days, flink))
            except Exception:
                pass
    recheck_candidates.sort(reverse=True)
    for _, flink in recheck_candidates[:10]:
        links_to_check.append(flink)

    # Deep-check links that need status verification
    if links_to_check:
        print(f"🔍 Checking {len(links_to_check)} link(s) for verification & title extraction...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            for i, link in enumerate(links_to_check, 1):
                status, fn_title, fn_year = await check_link_health(link, page)
                health_cache[link] = {
                    "status": status,
                    "checked_at": datetime.now(timezone.utc).isoformat()
                }
                print(f"   [{i}/{len(links_to_check)}] {link} -> {status} (Extracted: {fn_title or 'N/A'})")

                for r in rows:
                    if r["File Link"] == link:
                        r["Status"] = status
                        if (r["Title"] == "Unknown Title" or not is_valid_movie_title(r["Title"])) and fn_title and is_valid_movie_title(fn_title):
                            r["Title"] = fn_title
                            if fn_year:
                                r["Year"] = fn_year

            await browser.close()

        # Save health cache to disk
        with open(HEALTH_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(health_cache, f, indent=2)

    # Apply Link Overrides, English Cleaning, Quality Tier Evaluation, and Letterboxd link across all rows
    for r in rows:
        fl = r["File Link"]
        for k, (ov_t, ov_y) in LINK_OVERRIDES.items():
            if k in fl:
                r["Title"] = ov_t
                r["Year"] = ov_y
                break

        # Convert to clean English title
        r["Title"] = clean_to_english_title(r["Title"])
        if not is_valid_movie_title(r["Title"]):
            r["Title"] = "Unknown Title"
        
        # Evaluate Best Quality Available status
        r["Best Quality?" ] = evaluate_quality_tier(r["Quality"], r["Title"])

        # Update Letterboxd and IMDb links with final title and year
        r["Letterboxd"] = get_letterboxd_link(r["Title"], r["Year"])
        r["IMDb"] = get_imdb_link(r["Title"], r["Year"])

    # STRICT FILTER: REMOVE ALL DEAD LINKS
    alive_rows = [r for r in rows if "Alive" in r.get("Status", "")]
    dead_count = len(rows) - len(alive_rows)

    # SORT BY TWEET DATE DESCENDING (newest tweets at top)
    alive_rows.sort(key=lambda x: (x["Title"] != "Unknown Title", x["_raw_time"]), reverse=True)

    # DEDUPLICATE BY FILE LINK (keep newest/best parsed entry if same link was quoted/reposted)
    deduped_rows = []
    seen_links = set()
    for r in alive_rows:
        fl = r["File Link"]
        if fl not in seen_links:
            seen_links.add(fl)
            deduped_rows.append(r)
    alive_rows = deduped_rows
    alive_rows.sort(key=lambda x: x["_raw_time"], reverse=True)

    # Write CSV with Alive items only
    fieldnames = ["Tweet Date", "Title", "Year", "Quality", "Best Quality?", "File Host", "File Link", "Letterboxd", "IMDb", "Status", "Tweet URL"]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(alive_rows)

    print("\n" + "=" * 55)
    print(f"✅ Filtered & Exported {len(alive_rows)} ALIVE items to {OUTPUT_CSV}")
    print(f"🗑️ Permanently removed {dead_count} dead/expired links.")
    print(f"📅 Sorted by Tweet Date: Newest first ({alive_rows[0]['Tweet Date'] if alive_rows else 'N/A'})")

    # Export batch download link lists for Real-Debrid / JDownloader
    export_download_batches(alive_rows)

    # Send optional Discord/Telegram notifications
    send_webhook_notifications(alive_rows, dead_count)

    # Clear Google Sheet completely and re-import with new 11-column layout
    print(f"\n📊 Syncing to Google Sheet ({SPREADSHEET_ID})...")
    end_fmt_row = max(len(alive_rows) + 100, 1000)
    os.system(f"gsheets mutate clear '{SPREADSHEET_ID}' 'Sheet1!A1:Z5000'")
    os.system(f"gsheets mutate import-csv '{SPREADSHEET_ID}' '{OUTPUT_CSV}'")
    os.system(f"gsheets mutate freeze '{SPREADSHEET_ID}' --sheet-id 0 --rows 1")
    os.system(f"gsheets mutate format '{SPREADSHEET_ID}' --sheet-id 0 --start-row 0 --end-row 1 --start-col 0 --end-col 11 --bold --align CENTER --bg-color '#1E293B' --fg-color '#FFFFFF'")
    os.system(f"gsheets mutate autosize '{SPREADSHEET_ID}' --sheet-id 0 --start-col 0 --end-col 11")
    
    # Conditional formatting for Best Quality? (Col 4)
    # Green for Yes (4K, 1080p Best, or DVD Best)
    os.system(f"gsheets mutate conditional-format '{SPREADSHEET_ID}' --sheet-id 0 --start-row 1 --end-row {end_fmt_row} --start-col 4 --end-col 5 --condition 'TEXT_CONTAINS' --value 'Yes' --color '#DCFCE7'")
    # Amber for when a higher resolution (4K or 1080p) exists
    os.system(f"gsheets mutate conditional-format '{SPREADSHEET_ID}' --sheet-id 0 --start-row 1 --end-row {end_fmt_row} --start-col 4 --end-col 5 --condition 'TEXT_CONTAINS' --value 'Exists' --color '#FEF3C7'")
    
    # Conditional formatting for Quality (Col 3)
    # Soft purple for DVD
    os.system(f"gsheets mutate conditional-format '{SPREADSHEET_ID}' --sheet-id 0 --start-row 1 --end-row {end_fmt_row} --start-col 3 --end-col 4 --condition 'TEXT_CONTAINS' --value 'DVD' --color '#F3E8FF'")
    # Soft gold for 4K
    os.system(f"gsheets mutate conditional-format '{SPREADSHEET_ID}' --sheet-id 0 --start-row 1 --end-row {end_fmt_row} --start-col 3 --end-col 4 --condition 'TEXT_CONTAINS' --value '4K' --color '#FEF08A'")
    
    # Conditional formatting for Status (Col 9)
    os.system(f"gsheets mutate conditional-format '{SPREADSHEET_ID}' --sheet-id 0 --start-row 1 --end-row {end_fmt_row} --start-col 9 --end-col 10 --condition 'TEXT_CONTAINS' --value 'Alive' --color '#DCFCE7'")
    print("✅ Google Sheet refreshed successfully with transfer.it, Letterboxd, IMDb, and Quality Tier evaluation!")


if __name__ == "__main__":
    asyncio.run(process_and_verify())
