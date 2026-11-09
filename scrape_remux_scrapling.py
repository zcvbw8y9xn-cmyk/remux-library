"""
X.com Remux File Link Scraper — powered by Patchright
Patchright is a patched Playwright that removes all automation fingerprints,
allowing login on bot-protected sites like X.com.

Usage:
    python3 scrape_remux_scrapling.py
"""

import asyncio
import json
import os
import httpx
from datetime import datetime, timezone
from patchright.async_api import async_playwright

SEARCH_URL = "https://x.com/search?q=remux&f=video&src=typed_query"
OUTPUT_FILE = "remux_links.json"
PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".browser_profile")
SCROLL_ROUNDS = 80       # ~80 scrolls for a deep scrape
SCROLL_PAUSE_MS = 2000

FILE_HOSTS = [
    "gofile.io",
    "transfer.sh",
    "transfer.it",
    "wetransfer.com",
    "we.tl",
    "pixeldrain.com",
    "mega.nz",
    "1fichier.com",
    "mediafire.com",
    "buzzheavier.com",
    "anonfiles.com",
    "fileditch.com",
    "filehaus.top",
    "bowfile.com",
    "cyberfile.is",
    "datanodes.to",
    "krakenfiles.com",
    "send.cm",
    "workupload.com",
    "mixdrop.ag",
    "dropbox.com",
    "drive.google.com",
]


def is_file_host(url: str) -> bool:
    return any(host in url for host in FILE_HOSTS)


async def resolve_tco(tco_url: str, client: httpx.AsyncClient) -> str:
    """Follow a t.co short link and return the final destination URL."""
    try:
        resp = await client.head(tco_url, follow_redirects=True, timeout=8)
        return str(resp.url)
    except Exception:
        try:
            resp = await client.get(tco_url, follow_redirects=True, timeout=8)
            return str(resp.url)
        except Exception:
            return tco_url


def load_existing_results():
    if not os.path.exists(OUTPUT_FILE):
        return set(), []
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        hits = data.get("hits", [])
        misses = data.get("no_file_links", [])
        all_entries = hits + misses
        seen_urls = {e["tweet_url"] for e in all_entries if "tweet_url" in e}
        print(f"📂 Loaded {len(all_entries)} previous entries ({len(hits)} hits) from {OUTPUT_FILE}")
        return seen_urls, all_entries
    except Exception as e:
        print(f"⚠️ Could not load existing results: {e}")
        return set(), []


def save_results(results):
    hits = [r for r in results if r.get("file_links")]
    misses = [r for r in results if not r.get("file_links")]
    output = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "query": "remux",
        "total_tweets": len(results),
        "total_with_file_links": len(hits),
        "hits": hits,
        "no_file_links": misses,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


async def scrape():
    print("🕵️  X.com Remux File Link Hunter (Patchright)")
    print("=" * 55)

    seen_tweet_urls, results = load_existing_results()

    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0"},
        follow_redirects=True,
    ) as http:
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=PROFILE_DIR,
                headless=False,
                no_viewport=True,
                args=["--start-maximized"],
            )

            page = await context.new_page()

            # ── Check if already logged in ─────────────────────────────
            print("\n🌐 Checking X.com session...")
            await page.goto("https://x.com/home", wait_until="domcontentloaded")
            await page.wait_for_timeout(3500)

            # Check if login required
            if "login" in page.url or "i/flow" in page.url:
                print("\n👉 Please log into X.com in the browser window.")
                print("   Your session will be saved for future runs.")
                input("   > Press ENTER once you are logged in: ")
            else:
                print("✅ Logged in session detected!")

            # ── Navigate to search ─────────────────────────────────────
            print(f"\n🔍 Navigating to remux search...")
            await page.goto(SEARCH_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(3500)
            print(f"   URL: {page.url}")

            if "login" in page.url:
                print("❌ Redirected to login. Please log in and retry.")
                await context.close()
                return

            print(f"\n🚀 Scraping — {SCROLL_ROUNDS} scroll rounds (current total hits: {sum(1 for r in results if r.get('file_links'))})\n")

            new_hits_this_run = 0

            for round_num in range(1, SCROLL_ROUNDS + 1):
                articles = await page.query_selector_all("article[data-testid='tweet']")
                hits_count = sum(1 for r in results if r.get("file_links"))
                print(f"   📜 Scroll {round_num}/{SCROLL_ROUNDS} — {hits_count} total hits ({new_hits_this_run} new this run)")

                for article in articles:
                    try:
                        tweet_url = None
                        for link in await article.query_selector_all("a[href*='/status/']"):
                            href = await link.get_attribute("href")
                            if href and "/status/" in href:
                                tweet_url = (
                                    f"https://x.com{href}"
                                    if href.startswith("/") else href
                                ).split("?")[0]
                                break

                        if not tweet_url or tweet_url in seen_tweet_urls:
                            continue
                        seen_tweet_urls.add(tweet_url)

                        text_el = await article.query_selector("[data-testid='tweetText']")
                        text = (await text_el.inner_text()).strip() if text_el else ""

                        if "remux" not in text.lower():
                            continue

                        tco_links = []
                        for a in await article.query_selector_all("a[href]"):
                            href = await a.get_attribute("href") or ""
                            if "t.co" in href and href not in tco_links:
                                tco_links.append(href)

                        if not tco_links:
                            continue

                        print(f"   🔗 {len(tco_links)} link(s) in {tweet_url.split('/')[-1]}...")
                        resolved = {}
                        for tco in tco_links:
                            real = await resolve_tco(tco, http)
                            resolved[tco] = real
                            if is_file_host(real):
                                print(f"      ✅ FILE HOST: {real}")
                                new_hits_this_run += 1

                        file_links = [u for u in resolved.values() if is_file_host(u)]
                        other_links = [u for u in resolved.values() if not is_file_host(u)]

                        author_el = await article.query_selector("[data-testid='User-Name'] a")
                        author_href = await author_el.get_attribute("href") if author_el else ""
                        author = f"https://x.com{author_href}" if author_href and author_href.startswith("/") else author_href

                        time_el = await article.query_selector("time[datetime]")
                        timestamp = await time_el.get_attribute("datetime") if time_el else ""

                        results.append({
                            "tweet_url": tweet_url,
                            "author": author,
                            "timestamp": timestamp,
                            "text": text[:300],
                            "file_links": file_links,
                            "other_links": other_links,
                            "raw_tco": resolved,
                        })

                    except Exception:
                        continue

                # Save progress periodically every 5 rounds
                if round_num % 5 == 0:
                    save_results(results)

                await page.evaluate("window.scrollBy(0, 1800)")
                await page.wait_for_timeout(SCROLL_PAUSE_MS)

            save_results(results)
            await context.close()

    total_hits = sum(1 for r in results if r.get("file_links"))
    print(f"\n{'=' * 55}")
    print(f"✅ Finished! Total tweets scanned: {len(results)}")
    print(f"🎯 Total hits with file hosting links: {total_hits}")
    print(f"✨ New file hosting links found this session: {new_hits_this_run}")
    print(f"📄 Saved → {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(scrape())
