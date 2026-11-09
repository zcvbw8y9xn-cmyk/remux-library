"""
Remux Data Processor & Link Health Verifier
- ONLY keeps working ALIVE 🟢 links (dead/expired links are deleted)
- Strictly sorts by Tweet Date descending (newest tweets first)
- Resolves all movie titles from tweet text or download page title
- Persistent health cache so dead links are never re-checked
- Syncs clean alive-only list directly to Google Sheets
"""

import asyncio
import csv
import json
import os
import re
from datetime import datetime, timezone
from patchright.async_api import async_playwright

INPUT_FILE = "remux_links.json"
OUTPUT_CSV = "remux_library.csv"
HEALTH_CACHE_FILE = "health_cache.json"
SPREADSHEET_ID = "1oqYjXc5D9eURyHUGNynR9uW9BDKNKWyGtfDBs8j_j8E"


def clean_text_for_title(raw_text: str):
    """
    Extracts Title and Year from tweet text.
    Handles multi-line, director credits, and non-ASCII titles (e.g. Salò).
    """
    lines = [l.strip() for l in raw_text.strip().split("\n") if l.strip()]
    if not lines:
        return "Unknown Title", "Unknown"

    # Pattern 1: Title (Year...) on first line
    m1 = re.search(r'^([^\n\r(\[]+?)\s*[\(\[](?:[^\)\]]*?\b(19\d{2}|20\d{2})\b[^\)\]]*)[\)\]]', lines[0])
    if m1:
        t = m1.group(1).strip(" -:\t\n*#")
        t = re.sub(r'\s*\*[^*]+\*\s*', ' ', t).strip()
        if not re.search(r'^(1080p|4k|bluray|uhd|remux)', t, re.I):
            return t, m1.group(2)

    # Pattern 2: Title on previous line, 'YYYY Directed by ...' on current line
    for i, line in enumerate(lines):
        m_yd = re.search(r'\b(19\d{2}|20\d{2})\b.*?(?:directed by|dir\.)', line, re.I)
        if m_yd and i > 0:
            t = lines[i-1].strip(" -:\t\n*#")
            t = re.sub(r'\s*\*[^*]+\*\s*', ' ', t).strip()
            return t, m_yd.group(1)

    # Pattern 3: Ukrainian archive or 'Larisa Shepitko, 1977' style
    for i, line in enumerate(lines):
        m_dir_year = re.search(r'^(?:[A-Za-z\s]+),\s*(19\d{2}|20\d{2})$', line)
        if m_dir_year:
            for prev in lines[:i]:
                if not re.search(r'archive|collection|remux|bluray', prev, re.I) and re.search(r'^[A-Za-z0-9\s\':,-]+$', prev):
                    return prev.strip(), m_dir_year.group(1)

    # Pattern 4: Any line with Title (Year)
    for line in lines:
        m2 = re.search(r'([^\n\r(\[]+?)\s*[\(\[](?:[^\)\]]*?\b(19\d{2}|20\d{2})\b[^\)\]]*)[\)\]]', line)
        if m2:
            t = m2.group(1).strip(" -:\t\n*#")
            t = re.sub(r'\s*\*[^*]+\*\s*', ' ', t).strip()
            if not re.search(r'^(1080p|4k|bluray|uhd|remux)', t, re.I):
                return t, m2.group(2)

    myear = re.search(r'\b(19\d{2}|20\d{2})\b', raw_text)
    year = myear.group(1) if myear else "Unknown"
    return "Unknown Title", year


def extract_title_from_filename(filename: str):
    """Parse release filename like 'The.Exiles.1961.1080p.BluRay.Remux.AVC.FLAC2.0-PSTX.mkv'"""
    cleaned = filename.replace(".", " ").replace("_", " ")
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
    Also extracts the exact filename/title shown on the download page.
    Returns: (status, fallback_title, fallback_year)
    """
    try:
        if "transfer.it" in link:
            await page.goto(link, wait_until="domcontentloaded", timeout=12000)
            await page.wait_for_timeout(3500)
            body = (await page.inner_text("body")).lower()

            if any(term in body for term in ["oops", "can’t find this transfer", "can't find this transfer", "expired", "removed", "incorrect"]):
                return "Dead 🔴", None, None

            if "ready to download" in body:
                lines = [l.strip() for l in (await page.inner_text("body")).split("\n") if l.strip()]
                for idx, line in enumerate(lines):
                    if line.lower() == "ready to download" and idx + 1 < len(lines):
                        fn_title, fn_year = extract_title_from_filename(lines[idx + 1])
                        return "Alive 🟢", fn_title, fn_year
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
                    m = re.search(r'^([^\n\r(\[]+?)\s*[\(\[](19\d{2}|20\d{2})[\)\]]', l)
                    if m and not re.search(r'guest|account|file manager|premium', m.group(1), re.I):
                        return "Alive 🟢", m.group(1).strip(), m.group(2)
                return "Alive 🟢", None, None
            return "Dead 🔴", None, None

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

    # Load persistent health cache (remembers dead links so we never re-check them)
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

    if links_to_check:
        print(f"🔍 Checking {len(links_to_check)} link(s) for verification...")
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

    # Edge-case title mapping
    for r in rows:
        if "m9vWw503wZxB" in r["File Link"]:
            r["Title"] = "The Exiles"
            r["Year"] = "1961"
        elif "gDVLkuwxkDiA" in r["File Link"] and (r["Title"] == "Unknown Title" or not r["Title"]):
            r["Title"] = "Trainspotting"
            r["Year"] = "1996"
        elif "ZJiDky" in r["File Link"] and (r["Title"] == "Unknown Title" or not r["Title"]):
            r["Title"] = "Armageddon"
            r["Year"] = "1998"
        elif r["Title"].startswith(", or"):
            r["Title"] = "Salò, or the 120 Days of Sodom"
            r["Year"] = "1975"

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
    os.system(f"gsheets mutate clear '{SPREADSHEET_ID}' 'Sheet1!A1:Z500'")
    os.system(f"gsheets mutate import-csv '{SPREADSHEET_ID}' '{OUTPUT_CSV}'")
    os.system(f"gsheets mutate freeze '{SPREADSHEET_ID}' --sheet-id 0 --rows 1")
    os.system(f"gsheets mutate format '{SPREADSHEET_ID}' --sheet-id 0 --start-row 0 --end-row 1 --start-col 0 --end-col 8 --bold --align CENTER --bg-color '#1E293B' --fg-color '#FFFFFF'")
    os.system(f"gsheets mutate autosize '{SPREADSHEET_ID}' --sheet-id 0 --start-col 0 --end-col 8")
    os.system(f"gsheets mutate conditional-format '{SPREADSHEET_ID}' --sheet-id 0 --start-row 1 --end-row 300 --start-col 6 --end-col 7 --condition 'TEXT_CONTAINS' --value 'Alive' --color '#DCFCE7'")
    print("✅ Google Sheet refreshed successfully with clean alive-only list!")


if __name__ == "__main__":
    asyncio.run(process_and_verify())
