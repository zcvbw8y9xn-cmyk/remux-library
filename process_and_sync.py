"""
Remux Data Processor & Accurate Link Health Verifier
Extracts Movie Title, Year, Quality/Size info, and tests whether each link is ALIVE or DEAD.
Exports the cleaned table to remux_library.csv and updates Google Sheets.
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
SPREADSHEET_ID = "1oqYjXc5D9eURyHUGNynR9uW9BDKNKWyGtfDBs8j_j8E"


def clean_text_for_title(raw_text: str):
    """
    Extracts Title and Year from tweet text.
    Handles formats like:
      - Fish Story (2009) 1080p BluRay REMUX
      - Lawrence of Arabia (David Lean, 1962)
      - Perfect Blue (1997, Satoshi Kon)
      - An Autumn's Tale *4K Restoration* (1987, Mabel Cheung)
    """
    first_line = raw_text.strip().split("\n")[0].strip()

    # Pattern 1: Title (Director?, Year, etc.)
    m1 = re.search(r'^([A-Za-z0-9\s\'\:\,\.\-\!\?*#&]+?)\s*[\(\[](?:[^\)\]]*?\b(19\d{2}|20\d{2})\b[^\)\]]*)[\)\]]', first_line)
    if m1:
        raw_title = m1.group(1).strip(" -:\t\n*#")
        raw_title = re.sub(r'\s*\*[^*]+\*\s*', ' ', raw_title).strip()
        year = m1.group(2)
        return raw_title, year

    # Pattern 2: Search throughout entire text
    for line in raw_text.split("\n"):
        line = line.strip()
        m2 = re.search(r'([A-Za-z0-9\s\'\:\,\.\-\!\?*#&]+?)\s*[\(\[](?:[^\)\]]*?\b(19\d{2}|20\d{2})\b[^\)\]]*)[\)\]]', line)
        if m2:
            raw_title = m2.group(1).strip(" -:\t\n*#")
            raw_title = re.sub(r'\s*\*[^*]+\*\s*', ' ', raw_title).strip()
            if not re.search(r'^(1080p|4k|bluray|uhd|remux)', raw_title, re.I):
                return raw_title, m2.group(2)

    myear = re.search(r'\b(19\d{2}|20\d{2})\b', raw_text)
    year = myear.group(1) if myear else "Unknown"
    return "Unknown Title", year


def extract_title_from_filename(filename: str):
    """Fallback: Parse release filename like 'Aniki.Bobo.1942.1080p.BluRay.REMUX.mkv'"""
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
    Returns: (status, fallback_title, fallback_year)
    """
    try:
        if "transfer.it" in link:
            await page.goto(link, wait_until="domcontentloaded", timeout=12000)
            # Give client-side SPA 2.5 seconds to populate transfer data or error message
            await page.wait_for_timeout(2500)
            body = (await page.inner_text("body")).lower()

            # Strict dead detection
            if any(term in body for term in ["oops", "can’t find this transfer", "can't find this transfer", "expired", "removed", "incorrect"]):
                return "Dead 🔴", None, None

            # Strict alive detection
            if "ready to download" in body:
                # Try to extract actual movie filename from the line under 'Ready to download'
                lines = [l.strip() for l in (await page.inner_text("body")).split("\n") if l.strip()]
                for idx, line in enumerate(lines):
                    if line.lower() == "ready to download" and idx + 1 < len(lines):
                        fn_title, fn_year = extract_title_from_filename(lines[idx + 1])
                        return "Alive 🟢", fn_title, fn_year
                return "Alive 🟢", None, None

            return "Dead 🔴", None, None

        elif "gofile.io" in link:
            await page.goto(link, wait_until="domcontentloaded", timeout=12000)
            await page.wait_for_timeout(2500)
            body = (await page.inner_text("body")).lower()
            if "this content does not exist" in body or "error-notfound" in body or "not found" in body:
                return "Dead 🔴", None, None
            if "download" in body or "files" in body:
                return "Alive 🟢", None, None
            return "Dead 🔴", None, None

        elif "mega.nz" in link:
            await page.goto(link, wait_until="domcontentloaded", timeout=12000)
            await page.wait_for_timeout(2500)
            body = (await page.inner_text("body")).lower()
            if any(term in body for term in ["no longer available", "removed", "does not exist", "invalid link"]):
                return "Dead 🔴", None, None
            return "Alive 🟢", None, None

        return "Alive 🟢", None, None

    except Exception as e:
        return "Dead 🔴", None, None


async def process_and_verify():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ {INPUT_FILE} not found!")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    hits = data.get("hits", [])
    print(f"📊 Processing {len(hits)} scraped posts with file links...")

    rows = []
    links_to_check = []

    for entry in hits:
        text = entry.get("text", "")
        tweet_url = entry.get("tweet_url", "")
        title, year = clean_text_for_title(text)
        quality = extract_format_info(text)

        for file_link in entry.get("file_links", []):
            host = file_link.split("/")[2] if "/" in file_link else "unknown"
            rows.append({
                "Title": title,
                "Year": year,
                "Quality": quality,
                "File Host": host,
                "File Link": file_link,
                "Status": "Pending",
                "Checked Date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "Tweet URL": tweet_url,
            })
            links_to_check.append(file_link)

    print(f"🔍 Verifying health for all {len(links_to_check)} link(s) with strict checks...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for i, link in enumerate(links_to_check, 1):
            status, fn_title, fn_year = await check_link_health(link, page)
            checked_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            print(f"   [{i}/{len(links_to_check)}] {link} -> {status}")

            for r in rows:
                if r["File Link"] == link:
                    r["Status"] = status
                    r["Checked Date"] = checked_date
                    if (r["Title"] == "Unknown Title" or not r["Title"]) and fn_title:
                        r["Title"] = fn_title
                        if fn_year:
                            r["Year"] = fn_year

        await browser.close()

    # Sort rows by Status (Alive first), then Title, then Year
    rows.sort(key=lambda x: (x["Status"] != "Alive 🟢", x["Title"] == "Unknown Title", x["Title"], x["Year"]))

    # Write to CSV
    fieldnames = ["Title", "Year", "Quality", "File Host", "File Link", "Status", "Checked Date", "Tweet URL"]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    alive_count = sum(1 for r in rows if "Alive" in r["Status"])
    dead_count = sum(1 for r in rows if "Dead" in r["Status"])
    print(f"\n{'=' * 55}")
    print(f"✅ Exported {len(rows)} verified items to {OUTPUT_CSV}")
    print(f"   🟢 Alive: {alive_count} | 🔴 Dead: {dead_count}")

    # Directly update Google Sheets
    print(f"\n📊 Updating Google Sheet ({SPREADSHEET_ID})...")
    os.system(f"gsheets mutate import-csv '{SPREADSHEET_ID}' '{OUTPUT_CSV}'")
    os.system(f"gsheets mutate autosize '{SPREADSHEET_ID}' --sheet-id 0 --start-col 0 --end-col 8")
    print("✅ Google Sheet refreshed successfully!")


if __name__ == "__main__":
    asyncio.run(process_and_verify())
