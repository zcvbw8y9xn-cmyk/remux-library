"""
X.com Remux Video Scraper
Searches X.com for posts containing 'remux' with the video filter,
collects tweet URLs and video sources, saves to remux_results.json
"""

import asyncio
import json
import re
from datetime import datetime
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

SEARCH_URL = "https://x.com/search?q=remux&f=video&src=typed_query"
OUTPUT_FILE = "remux_results.json"
SCROLL_ROUNDS = 15       # how many times to scroll down
SCROLL_PAUSE_MS = 2500   # wait between scrolls (ms)


async def scrape():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,  # visible so you can log in
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()
        await stealth_async(page)

        # ── Step 1: Login ──────────────────────────────────────────────
        print("🌐 Opening X.com login page...")
        await page.goto("https://x.com/login", wait_until="domcontentloaded")
        print("\n👉 Please log in to X.com in the browser window.")
        print("   Press ENTER here once you're logged in and see your home feed.\n")
        input("   > Press ENTER to continue: ")

        # ── Step 2: Navigate to search ─────────────────────────────────
        print("\n🔍 Searching for 'remux' video posts...")
        await page.goto(SEARCH_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        seen_urls = set()
        results = []

        # ── Step 3: Scroll and collect ─────────────────────────────────
        for round_num in range(1, SCROLL_ROUNDS + 1):
            print(f"   Scroll {round_num}/{SCROLL_ROUNDS} — {len(results)} found so far...")

            articles = await page.query_selector_all("article[data-testid='tweet']")

            for article in articles:
                try:
                    # Tweet URL
                    tweet_url = None
                    links = await article.query_selector_all("a[href*='/status/']")
                    for link in links:
                        href = await link.get_attribute("href")
                        if href and "/status/" in href:
                            tweet_url = (
                                f"https://x.com{href}"
                                if href.startswith("/") else href
                            )
                            # Strip query params
                            tweet_url = tweet_url.split("?")[0]
                            break

                    if not tweet_url or tweet_url in seen_urls:
                        continue
                    seen_urls.add(tweet_url)

                    # Tweet text
                    text_el = await article.query_selector("[data-testid='tweetText']")
                    text = (await text_el.inner_text()).strip() if text_el else ""

                    # Only keep posts that actually mention remux
                    if "remux" not in text.lower():
                        continue

                    # Video src (may be HLS blob or direct URL)
                    video_srcs = []
                    for video in await article.query_selector_all("video"):
                        src = await video.get_attribute("src")
                        if src:
                            video_srcs.append(src)

                    # Card / external links (e.g. magnet or file hosters)
                    card_links = []
                    for a in await article.query_selector_all("a[href]"):
                        href = await a.get_attribute("href")
                        if href and any(
                            kw in href for kw in
                            ["t.co", "magnet:", "1fichier", "mega.nz",
                             "gofile", "pixeldrain", "drive.google", "mediafire"]
                        ):
                            card_links.append(href)

                    # Author
                    author_el = await article.query_selector("[data-testid='User-Name'] a")
                    author = await author_el.get_attribute("href") if author_el else ""

                    # Timestamp
                    time_el = await article.query_selector("time")
                    timestamp = await time_el.get_attribute("datetime") if time_el else ""

                    entry = {
                        "tweet_url": tweet_url,
                        "author": f"https://x.com{author}" if author else "",
                        "timestamp": timestamp,
                        "text": text[:300],
                        "video_srcs": video_srcs,
                        "external_links": list(set(card_links)),
                    }
                    results.append(entry)
                    print(f"   ✅ {tweet_url}")

                except Exception as e:
                    pass  # skip malformed articles silently

            # Scroll down
            await page.evaluate("window.scrollBy(0, 1800)")
            await page.wait_for_timeout(SCROLL_PAUSE_MS)

        # ── Step 4: Save ───────────────────────────────────────────────
        output = {
            "scraped_at": datetime.utcnow().isoformat() + "Z",
            "query": "remux",
            "total": len(results),
            "results": results,
        }
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Done! Found {len(results)} remux posts.")
        print(f"📄 Saved to: {OUTPUT_FILE}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(scrape())
