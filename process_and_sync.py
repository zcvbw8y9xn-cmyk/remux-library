"""
Remux Data Processor & Link Health Verifier
- ONLY keeps working ALIVE 🟢 links (dead/expired links are deleted)
- Strictly sorts by Tweet Date descending (newest tweets first)
- Deep-extracts titles from tweet text and download pages (including clicking "View Content")
- Converts all foreign titles and accents to clean English
- Persistent health cache so dead links are never re-checked
- Syncs clean alive-only list directly to Google Sheets
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
    "Kuime": "Over Your Dead Body"
}

# Curated link-level metadata overrides
LINK_OVERRIDES = {
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
    "MdodCHhD0TYB": ("Luminous Woman", "1987")
}


def clean_to_english_title(text: str) -> str:
    """
    Translates foreign titles to English and strips non-ASCII accents and symbols.
    """
    if not text or text == "Unknown Title":
        return text

    # Direct translation check
    for foreign_k, eng_v in TRANSLATION_MAP.items():
        if foreign_k in text:
            text = eng_v
            break

    # If title has slash like 'Abraham\'s Valley / Vale Abraão', keep English first part
    if " / " in text:
        parts = text.split(" / ")
        if any(ord(c) < 128 for c in parts[0]):
            text = parts[0]

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
    return text or "Unknown Title"


def clean_text_for_title(raw_text: str):
    """
    Extracts English Title and Year from tweet text.
    Handles multi-line, director credits, bracketed foreign titles, and single-line tweets.
    """
    lines = [l.strip() for l in raw_text.strip().split("\n") if l.strip()]
    if not lines:
        return "Unknown Title", "Unknown"

    for foreign_k, eng_v in TRANSLATION_MAP.items():
        if foreign_k in raw_text:
            m_yr = re.search(r'\b(19\d{2}|20\d{2})\b', raw_text)
            yr = m_yr.group(1) if m_yr else "Unknown"
            return eng_v, yr

    # Pattern A: English Title [Foreign Title] (Director, Year) or (Year)
    mA = re.search(r'^([A-Za-z0-9\s\'\-\:\,\.\!\?&]+?)\s*(?:\[[^\]]+\])?\s*[\(\[](?:[^\)\]]*?\b(19\d{2}|20\d{2})\b[^\)\]]*)[\)\]]', lines[0])
    if mA:
        t = mA.group(1).strip(" -:\t\n*#[],")
        if t and not re.search(r'^(1080p|4k|bluray|uhd|remux)', t, re.I):
            return t, mA.group(2)

    # Pattern B: English Title (Foreign Title / aka) (Year)
    mB = re.search(r'^([A-Za-z0-9\s\'\-\:\,\.\!\?&]+?)(?:\[.*?\]|\(aka.*?\))\s*(?:\n|\b)', raw_text)
    m_yr = re.search(r'\b(19\d{2}|20\d{2})\b', raw_text)
    if mB and m_yr:
        t = mB.group(1).strip(" -:\t\n*#[],")
        if t and len(t) > 2 and not re.search(r'^(1080p|4k|bluray|uhd|remux)', t, re.I):
            return t, m_yr.group(1)

    # Pattern C: Line with Title YYYY (e.g. Mystic River 2003 Directed by Clint Eastwood)
    for line in lines[:3]:
        mC = re.search(r'^([A-Za-z0-9\s\'\-\:\,\.\!\?&]+?)\s+\b(19\d{2}|20\d{2})\b(?:\s+.*)?$', line.strip(), re.I)
        if mC:
            t = mC.group(1).strip(" -:\t\n*#[],")
            if t and not re.search(r'^(1080p|4k|bluray|uhd|remux|bd)', t, re.I) and len(t) > 1:
                return t, mC.group(2)

    # Pattern D: Multi-line English / Foreign / Director, Year
    for i in range(1, min(len(lines), 4)):
        m_dir_year = re.search(r'\b(19\d{2}|20\d{2})\b', lines[i])
        if m_dir_year and ('directed' in lines[i].lower() or ',' in lines[i] or 'by' in lines[i].lower()):
            cand = lines[0].strip(" -:\t\n*#[],")
            if cand and not re.search(r'archive|collection|remux|bluray|1080p|4k', cand, re.I):
                return cand, m_dir_year.group(1)

    # Pattern E: Standard Title (Year)
    for line in lines[:3]:
        mE = re.search(r'([^\n\r(\[]+?)\s*[\(\[](?:[^\)\]]*?\b(19\d{2}|20\d{2})\b[^\)\]]*)[\)\]]', line)
        if mE:
            t = mE.group(1).strip(" -:\t\n*#[],")
            if not re.search(r'^(1080p|4k|bluray|uhd|remux)', t, re.I):
                return t, mE.group(2)

    m_all_yr = re.search(r'\b(19\d{2}|20\d{2})\b', raw_text)
    return "Unknown Title", m_all_yr.group(1) if m_all_yr else "Unknown"


def extract_title_from_filename(filename: str):
    """Parse release filename like 'Beetlejuice.Beetlejuice.2024.UHD.Remux.mkv'"""
    cleaned = filename.replace(".", " ").replace("_", " ")
    # Clean release tags
    m = re.search(r'^([A-Za-z0-9\s\'\-\!\?]+?)\s+\b(19\d{2}|20\d{2})\b', cleaned)
    if m:
        return m.group(1).strip(), m.group(2)
    return None, None


def extract_format_info(raw_text: str) -> str:
    """Extracts quality markers (4K, 1080p, HDR, DV, file size)."""
    tags = []
    if re.search(r'\b4K\b|2160p|UHD', raw_text, re.I):
        tags.append("4K UHD")
    elif re.search(r'\b1080p\b', raw_text, re.I):
        tags.append("1080p")

    if re.search(r'\bHDR\b', raw_text, re.I):
        tags.append("HDR")
    if re.search(r'\bDV\b|Dolby Vision', raw_text, re.I):
        tags.append("DV")
    if re.search(r'\bREMUX\b', raw_text, re.I):
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
                # Try clicking 'View content' button to reveal the actual file name
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

                # Fallback to checking line immediately below 'Ready to download'
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

        for file_link in entry.get("file_links", []):
            host = file_link.split("/")[2] if "/" in file_link else "unknown"
            cached_status = health_cache.get(file_link, "Pending")

            item = {
                "Tweet Date": tweet_date,
                "Title": title,
                "Year": year,
                "Quality": quality,
                "File Host": host,
                "File Link": file_link,
                "Status": cached_status,
                "Tweet URL": tweet_url,
                "_raw_time": raw_time or "1970-01-01",
            }
            rows.append(item)
            if cached_status == "Pending" or title == "Unknown Title":
                links_to_check.append(file_link)

    # Deep-check links that need status or title verification
    if links_to_check:
        print(f"🔍 Checking {len(links_to_check)} link(s) for verification & title extraction...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            for i, link in enumerate(links_to_check, 1):
                status, fn_title, fn_year = await check_link_health(link, page)
                health_cache[link] = status
                print(f"   [{i}/{len(links_to_check)}] {link} -> {status} (Extracted: {fn_title or 'N/A'})")

                for r in rows:
                    if r["File Link"] == link:
                        r["Status"] = status
                        if (r["Title"] == "Unknown Title" or not r["Title"]) and fn_title:
                            r["Title"] = fn_title
                            if fn_year:
                                r["Year"] = fn_year

            await browser.close()

        # Save health cache to disk
        with open(HEALTH_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(health_cache, f, indent=2)

    # Apply Link Overrides and English Cleaning across all rows
    for r in rows:
        fl = r["File Link"]
        for k, (ov_t, ov_y) in LINK_OVERRIDES.items():
            if k in fl:
                r["Title"] = ov_t
                r["Year"] = ov_y
                break

        # Convert to clean English title
        r["Title"] = clean_to_english_title(r["Title"])

    # STRICT FILTER: REMOVE ALL DEAD LINKS
    alive_rows = [r for r in rows if "Alive" in r.get("Status", "")]
    dead_count = len(rows) - len(alive_rows)

    # SORT BY TWEET DATE DESCENDING (newest tweets at top)
    alive_rows.sort(key=lambda x: x["_raw_time"], reverse=True)

    # Write CSV with Alive items only
    fieldnames = ["Tweet Date", "Title", "Year", "Quality", "File Host", "File Link", "Status", "Tweet URL"]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(alive_rows)

    print(f"\n{'=' * 55}")
    print(f"✅ Filtered & Exported {len(alive_rows)} ALIVE items to {OUTPUT_CSV}")
    print(f"🗑️ Permanently removed {dead_count} dead/expired links.")
    print(f"📅 Sorted by Tweet Date: Newest first ({alive_rows[0]['Tweet Date'] if alive_rows else 'N/A'})")

    # Clear Google Sheet completely and re-import only alive rows
    print(f"\n📊 Syncing to Google Sheet ({SPREADSHEET_ID})...")
    os.system(f"gsheets mutate clear '{SPREADSHEET_ID}' 'Sheet1!A1:Z600'")
    os.system(f"gsheets mutate import-csv '{SPREADSHEET_ID}' '{OUTPUT_CSV}'")
    os.system(f"gsheets mutate freeze '{SPREADSHEET_ID}' --sheet-id 0 --rows 1")
    os.system(f"gsheets mutate format '{SPREADSHEET_ID}' --sheet-id 0 --start-row 0 --end-row 1 --start-col 0 --end-col 8 --bold --align CENTER --bg-color '#1E293B' --fg-color '#FFFFFF'")
    os.system(f"gsheets mutate autosize '{SPREADSHEET_ID}' --sheet-id 0 --start-col 0 --end-col 8")
    os.system(f"gsheets mutate conditional-format '{SPREADSHEET_ID}' --sheet-id 0 --start-row 1 --end-row 500 --start-col 6 --end-col 7 --condition 'TEXT_CONTAINS' --value 'Alive' --color '#DCFCE7'")
    print("✅ Google Sheet refreshed successfully with clean alive-only list!")


if __name__ == "__main__":
    asyncio.run(process_and_verify())
