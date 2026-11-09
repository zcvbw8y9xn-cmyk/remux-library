"""
Remux Data Processor & Link Health Verifier
Extracts Movie Title, Year, Quality/Size info, and tests whether each link is ALIVE or DEAD.
Exports the cleaned table to remux_library.csv for Google Sheets.
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
        raw_title = re.sub(r'\s*\*[^*]+\*\s*', ' ', raw_title).strip() # clean *4K Restoration*
        year = m1.group(2)
        return raw_title, year

    # Pattern 2: Search throughout entire text if first line was a header
    for line in raw_text.split("\n"):
        line = line.strip()
        m2 = re.search(r'([A-Za-z0-9\s\'\:\,\.\-\!\?*#&]+?)\s*[\(\[](?:[^\)\]]*?\b(19\d{2}|20\d{2})\b[^\)\]]*)[\)\]]', line)
        if m2:
            raw_title = m2.group(1).strip(" -:\t\n*#")
            raw_title = re.sub(r'\s*\*[^*]+\*\s*', ' ', raw_title).strip()
            # Ignore if title looks like just resolution
            if not re.search(r'^(1080p|4k|bluray|uhd|remux)', raw_title, re.I):
                return raw_title, m2.group(2)

    # Fallback: Just year, title unknown
    myear = re.search(r'\b(19\d{2}|20\d{2})\b', raw_text)
    year = myear.group(1) if myear else "Unknown"
    return "Unknown Title", year


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

    # Size (e.g. 32.5 GB)
    msize = re.search(r'(\d+(?:\.\d+)?\s*(?:GB|GiB|MB))', raw_text, re.I)
    if msize:
        tags.append(msize.group(1).upper())

    return " | ".join(tags) if tags else "Remux"


async def check_link_health(link: str, page) -> str:
    """Checks whether the file link is still alive or expired."""
    try:
        if "transfer.it" in link:
            await page.goto(link, wait_until="networkidle", timeout=12000)
            body = (await page.inner_text("body")).lower()
            if "can’t find this transfer" in body or "expired" in body or "removed" in body:
                return "Dead 🔴"
            if "ready to download" in body or "download" in body or "gb" in body:
                return "Alive 🟢"
            return "Alive 🟢"

        elif "gofile.io" in link:
            await page.goto(link, wait_until="networkidle", timeout=12000)
            body = (await page.inner_text("body")).lower()
            if "content does not exist" in body or "not found" in body:
                return "Dead 🔴"
            return "Alive 🟢"

        elif "mega.nz" in link:
            await page.goto(link, wait_until="networkidle", timeout=12000)
            body = (await page.inner_text("body")).lower()
            if "no longer available" in body or "removed" in body or "does not exist" in body:
                return "Dead 🔴"
            return "Alive 🟢"

        return "Alive 🟢"
    except Exception:
        return "Unknown ⚠️"


async def process_and_verify():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ {INPUT_FILE} not found!")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    hits = data.get("hits", [])
    print(f"📊 Processing {len(hits)} scraped posts with file links...")

    # Load existing CSV if available to cache previously checked statuses
    status_cache = {}
    if os.path.exists(OUTPUT_CSV):
        try:
            with open(OUTPUT_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("File Link"):
                        status_cache[row["File Link"]] = (row.get("Status", "Unknown ⚠️"), row.get("Checked Date", ""))
            print(f"📂 Cached status loaded for {len(status_cache)} links.")
        except Exception:
            pass

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
                "Status": status_cache.get(file_link, ("Pending", ""))[0],
                "Checked Date": status_cache.get(file_link, ("Pending", ""))[1] or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "Tweet URL": tweet_url,
            })
            if file_link not in status_cache or status_cache[file_link][0] == "Pending":
                links_to_check.append(file_link)

    print(f"🔍 Need to verify health for {len(links_to_check)} link(s)...")

    if links_to_check:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            for i, link in enumerate(links_to_check, 1):
                print(f"   [{i}/{len(links_to_check)}] Checking {link} ...")
                status = await check_link_health(link, page)
                checked_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                print(f"         Result: {status}")

                for r in rows:
                    if r["File Link"] == link:
                        r["Status"] = status
                        r["Checked Date"] = checked_date

            await browser.close()

    # Sort rows by Title, then Year
    rows.sort(key=lambda x: (x["Title"] == "Unknown Title", x["Title"], x["Year"]))

    # Write to CSV
    fieldnames = ["Title", "Year", "Quality", "File Host", "File Link", "Status", "Checked Date", "Tweet URL"]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n{'=' * 55}")
    print(f"✅ Exported {len(rows)} verified items to {OUTPUT_CSV}")
    alive_count = sum(1 for r in rows if "Alive" in r["Status"])
    dead_count = sum(1 for r in rows if "Dead" in r["Status"])
    print(f"   🟢 Alive: {alive_count} | 🔴 Dead: {dead_count}")


if __name__ == "__main__":
    asyncio.run(process_and_verify())
