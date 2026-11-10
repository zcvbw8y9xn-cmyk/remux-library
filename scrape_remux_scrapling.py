"""
X.com Remux File Link Scraper — powered by Patchright
Scrapes X.com for file hosting links (transfer.it, gofile.io, mega.nz, pixeldrain, etc.)
Runs headless in the background with persistent authenticated context.

Usage:
    python3 scrape_remux_scrapling.py
"""

import asyncio
import json
import os
import httpx
from datetime import datetime, timezone
from patchright.async_api import async_playwright

SEARCH_QUERIES = [
    "remux filter:links",
    "transfer.it remux",
    "gofile.io remux",
    "pixeldrain remux",
    "1080p remux filter:links",
    "4k remux filter:links"
]

OUTPUT_FILE = "remux_links.json"
PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".browser_profile")
MAX_SCROLL_ROUNDS = 200       # Per-query scroll ceiling
MAX_CONSECUTIVE_EMPTY = 6     # Stop query if 6 scrolls return 0 new tweets
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
        "query": "remux-multi-query",
        "total_tweets": len(results),
        "total_with_file_links": len(hits),
        "hits": hits,
        "no_file_links": misses,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


async def scrape():
    print("🕵️  X.com Remux File Link Hunter (Multi-Query Headless)")
    print("=" * 60)

    seen_tweet_urls, results = load_existing_results()
    total_new_hits = 0

    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0"},
        follow_redirects=True,
    ) as http:
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=PROFILE_DIR,
                headless=True,
                args=["--headless=new"],
            )

            page = await context.new_page()

            # Verify session
            print("\n🌐 Checking X.com session...")
            await page.goto("https://x.com/home", wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            if "login" in page.url or "i/flow" in page.url:
                print("❌ Session expired or not logged in.")
                await context.close()
                return

            print("✅ Authenticated session confirmed!")

            for query_idx, query in enumerate(SEARCH_QUERIES, 1):
                query_url = f"https://x.com/search?q={httpx.URL('', params={'q': query}).params['q']}&f=live&src=typed_query"
                print(f"\n🔍 [{query_idx}/{len(SEARCH_QUERIES)}] Query: '{query}'")
                print(f"   URL: {query_url}")

                try:
                    await page.goto(query_url, wait_until="domcontentloaded")
                    await page.wait_for_timeout(3500)
                except Exception as e:
                    print(f"   ⚠️ Navigation error: {e}")
                    continue

                new_hits_query = 0
                consecutive_empty = 0

                for round_num in range(1, MAX_SCROLL_ROUNDS + 1):
                    articles = await page.query_selector_all("article[data-testid='tweet']")
                    new_in_scroll = 0

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
                            new_in_scroll += 1

                            text_el = await article.query_selector("[data-testid='tweetText']")
                            text = (await text_el.inner_text()).strip() if text_el else ""

                            tco_links = []
                            for a in await article.query_selector_all("a[href]"):
                                href = await a.get_attribute("href") or ""
                                if "t.co" in href and href not in tco_links:
                                    tco_links.append(href)

                            if not tco_links:
                                continue

                            resolved = {}
                            for tco in tco_links:
                                real = await resolve_tco(tco, http)
                                resolved[tco] = real
                                if is_file_host(real):
                                    print(f"      ✅ FILE HOST: {real}")
                                    new_hits_query += 1
                                    total_new_hits += 1

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
                                "text": text[:350],
                                "file_links": file_links,
                                "other_links": other_links,
                                "raw_tco": resolved,
                            })

                        except Exception:
                            continue

                    if new_in_scroll == 0:
                        consecutive_empty += 1
                        if consecutive_empty >= MAX_CONSECUTIVE_EMPTY:
                            print(f"   🛑 Auto-Stop: No new tweets for query '{query}' after {round_num} scrolls.")
                            break
                    else:
                        consecutive_empty = 0

                    if round_num % 5 == 0:
                        save_results(results)

                    await page.evaluate("window.scrollBy(0, 1800)")
                    await page.wait_for_timeout(SCROLL_PAUSE_MS)

                print(f"   ✨ Query '{query}' added {new_hits_query} new hits.")
                save_results(results)

            await context.close()

    total_hits = sum(1 for r in results if r.get("file_links"))
    print(f"\n{'=' * 60}")
    print(f"✅ Scraping pass complete! Total tweets recorded: {len(results)}")
    print(f"🎯 Total hits with active file links: {total_hits}")
    print(f"✨ Total new links uncovered: {total_new_hits}")
    save_results(results)


if __name__ == "__main__":
    asyncio.run(scrape())
