#!/usr/bin/env python3
"""
IDX News Scraper
Fetches news from Indonesian financial news sources for IDX listed stocks
Features: Keyword filtering for risky stocks, lazy-load image extraction,
          relative time parsing, IDX Channel scroll-to-load
"""

import os
import re
import sys
import json
import time
import hashlib
import argparse
import logging
from datetime import datetime, timedelta
from typing import Optional

import psycopg2
from psycopg2.extras import execute_values
from playwright.sync_api import sync_playwright, Page
from dotenv import load_dotenv
import schedule

from config import (
    HOT_STOCKS, ACTIVE_STOCKS, NEWS_SOURCES, SCHEDULE,
    DEFAULT_RATE_LIMIT, MAX_ARTICLES_PER_PAGE, EARLY_EXIT_THRESHOLD
)

load_dotenv()

# Setup logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database
DATABASE_URL = os.getenv("DATABASE_URL")
BROWSER_CDP_URL = os.getenv("BROWSER_CDP_URL", "http://localhost:9222")
RATE_LIMIT = int(os.getenv("RATE_LIMIT_SECONDS", DEFAULT_RATE_LIMIT))

# Load Keywords for Filtering
KEYWORDS = {"positive": [], "negative": []}
try:
    with open(os.path.join(os.path.dirname(__file__), "keywords.json"), "r") as f:
        KEYWORDS = json.load(f)
    logger.info(f"Loaded {len(KEYWORDS['positive'])} positive and {len(KEYWORDS['negative'])} negative keywords.")
except Exception as e:
    logger.warning(f"Could not load keywords.json: {e}")

# Stocks that require strict filtering due to common words
RISKY_STOCKS = {"BUMI", "BUKA", "DEWA", "GOTO", "BBHI"}


def get_db():
    """Get database connection"""
    return psycopg2.connect(DATABASE_URL)


def hash_url(url: str) -> str:
    """Generate MD5 hash of URL for deduplication"""
    return hashlib.md5(url.encode()).hexdigest()


MONTHS_ID = {
    'januari': '01', 'februari': '02', 'maret': '03', 'april': '04', 'mei': '05', 'juni': '06',
    'juli': '07', 'agustus': '08', 'september': '09', 'oktober': '10', 'november': '11', 'desember': '12',
    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
    'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
    'agu': '08', 'okt': '10', 'nop': '11', 'des': '12'
}


def parse_relative_time(text: str) -> datetime:
    """Parse relative time strings like '5 menit yang lalu', '1 jam yang lalu'"""
    text = text.lower().strip()
    now = datetime.now()
    
    try:
        # Check for "yang lalu" or "ago"
        if "yang lalu" in text or "ago" in text:
            num_match = re.search(r'(\d+)', text)
            if not num_match:
                return None
            val = int(num_match.group(1))
            
            if "menit" in text or "minute" in text:
                return now - timedelta(minutes=val)
            elif "jam" in text or "hour" in text:
                return now - timedelta(hours=val)
            elif "hari" in text or "day" in text:
                return now - timedelta(days=val)
            elif "detik" in text or "second" in text:
                return now - timedelta(seconds=val)
                
        # Special case: "Baru saja" (Just now)
        if "baru saja" in text or "just now" in text:
            return now
            
    except Exception as e:
        logger.debug(f"Relative parse error '{text}': {e}")
        
    return None


def parse_date(date_text: str) -> datetime:
    """Parse Indonesian date string to datetime object (supports relative + absolute)"""
    if not date_text:
        return datetime.now()
    
    try:
        # Clean up
        text = date_text.lower().replace('|', '').replace('wib', '').replace('wita', '').replace('wit', '').strip()
        
        # Try relative time first
        relative_dt = parse_relative_time(text)
        if relative_dt:
            return relative_dt
            
        # Handle specific formats like "Senin, 10 Februari 2026 14:30"
        days = ['senin', 'selasa', 'rabu', 'kamis', 'jumat', 'sabtu', 'minggu']
        for day in days:
            text = text.replace(day + ',', '').replace(day, '').strip()
            
        parts = text.split()
        
        # Expected format: "10 februari 2026 14:30"
        if len(parts) >= 3:
            day = parts[0].zfill(2)
            month_str = parts[1]
            year = parts[2]
            
            # Retrieve month number
            month = MONTHS_ID.get(month_str, '01')
            
            time_str = "00:00"
            if len(parts) > 3 and ':' in parts[3]:
                time_str = parts[3]
                
            iso_str = f"{year}-{month}-{day}T{time_str}:00"
            return datetime.fromisoformat(iso_str)
            
    except Exception as e:
        logger.debug(f"Date parse error '{date_text}': {e}")
    
    return datetime.now()


def check_exists(conn, url_hash: str) -> bool:
    """Check if article already exists in database"""
    with conn.cursor() as cur:
        # Check if table exists first (in case of new setup)
        cur.execute("SELECT to_regclass('public.market_news')")
        if not cur.fetchone()[0]:
            return False
            
        cur.execute("SELECT 1 FROM market_news WHERE hash = %s", (url_hash,))
        return cur.fetchone() is not None


def get_all_stocks() -> list:
    """Get all stocks from database for cold tier"""
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute("SELECT kode_emiten FROM stocks")
            stocks = [row[0] for row in cur.fetchall()]
        conn.close()
        return stocks
    except Exception as e:
        logger.error(f"Failed to get stocks from database: {e}")
        return []


def is_relevant_article(title: str, summary: str, symbol: str) -> bool:
    """
    Filter out irrelevant news for risky stocks (e.g. 'gempa bumi' for BUMI).
    Logic:
    1. If symbol is not risky, keep it.
    2. If text contains NEGATIVE words:
       - Check if it ALSO contains POSITIVE words (context).
       - If YES (Negative + Positive) -> KEEP (Context saves it).
       - If NO (Negative only) -> DISCARD (Noise).
    3. If no Negative words -> KEEP.
    """
    if symbol not in RISKY_STOCKS:
        return True
        
    text = (title + " " + (summary or "")).lower()
    
    # Check for Negative (Noise) words
    has_negative = any(w in text for w in KEYWORDS["negative"])
    
    if has_negative:
        # If noise found, check for saving context (Positive words)
        has_positive = any(w in text for w in KEYWORDS["positive"])
        if has_positive:
            return True  # Saved by context
        return False  # Noise confirmed
        
    return True


def scrape_source(page: Page, symbol: str, source_key: str, conn) -> list:
    """Scrape news from a single source for a symbol"""
    source = NEWS_SOURCES[source_key]
    url = source["url_pattern"].format(symbol=symbol.lower())
    records = []
    duplicate_count = 0
    
    try:
        page.goto(url, timeout=30000)
        page.wait_for_load_state("networkidle", timeout=15000)
        time.sleep(1)  # Extra wait for JS rendering
        
        # IDX Channel requires scrolling to trigger lazy loading of images
        if source_key == "idxchannel":
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(0.5)
            page.evaluate("window.scrollTo(0, 0)")  # Scroll back to top
            time.sleep(0.5)
        
        # Find all articles
        articles = page.locator(source["article_selector"]).all()
        
        if not articles:
            logger.debug(f"  No articles found for {symbol} on {source['name']}")
            return records
        
        for i, article in enumerate(articles[:MAX_ARTICLES_PER_PAGE]):
            try:
                # Get title
                title_elem = article.locator(source["title_selector"]).first
                if not title_elem.count():
                    continue
                    
                title = title_elem.text_content().strip()
                
                # Get link - handle case where container itself is the link (Kompas)
                if source["link_selector"]:
                    link_elem = article.locator(source["link_selector"]).first
                    if link_elem.count():
                        link = link_elem.get_attribute("href")
                    else:
                        continue
                else:
                    # Container is the link (e.g., Kompas: a.article-link)
                    link = article.get_attribute("href")
                
                if not title or not link:
                    continue
                
                # Extract summary early for filtering
                summary = None
                if source["summary_selector"]:
                    summary_elem = article.locator(source["summary_selector"]).first
                    if summary_elem.count():
                        summary = summary_elem.text_content().strip()[:500]
                
                # Keyword Filtering for Risky Stocks
                if not is_relevant_article(title, summary, symbol):
                    logger.info(f"  Skipped irrelevant: {symbol} - {title[:30]}...")
                    continue
                
                # Ensure absolute URL
                if link.startswith("/"):
                    base_url = url.split("/tag/")[0]
                    
                    # Fix for Kontan (subdomain issue)
                    if "kontan.co.id" in url and "kontan.co.id" not in base_url:
                        base_url = "https://www.kontan.co.id"
                    elif "investor.id" in url and link.startswith("/"):
                        base_url = "https://investor.id"
                        
                    if not link.startswith("http"):
                        link = base_url.rstrip('/') + '/' + link.lstrip('/')
                
                # Check for duplicate
                url_hash = hash_url(link)
                if check_exists(conn, url_hash):
                    duplicate_count += 1
                    if duplicate_count >= EARLY_EXIT_THRESHOLD:
                        logger.debug(f"  Early exit: {EARLY_EXIT_THRESHOLD} duplicates found")
                        break
                    continue
                
                # Get date
                published_at = datetime.now()
                if source["date_selector"]:
                    date_elem = article.locator(source["date_selector"]).first
                    if date_elem.count():
                        date_text = date_elem.text_content().strip()
                        published_at = parse_date(date_text)
                
                # Extract image URL (with lazy-load support)
                image_url = None
                if source.get("image_selector"):
                    img_elem = article.locator(source["image_selector"]).first
                    if img_elem.count():
                        # Try multiple lazy-load attributes before falling back to src
                        image_url = (
                            img_elem.get_attribute("data-src") or
                            img_elem.get_attribute("data-lazy") or
                            img_elem.get_attribute("data-original") or
                            img_elem.get_attribute("src")
                        )
                        # Filter out placeholder images
                        if image_url and ("placeholder" in image_url.lower() or "blank" in image_url.lower()):
                            image_url = None
                
                records.append({
                    "hash": url_hash,
                    "title": title[:500],
                    "url": link,
                    "source": source_key,
                    "published_at": published_at,
                    "summary": summary,
                    "stock_symbols": [symbol],
                    "image_url": image_url
                })
                
            except Exception as e:
                logger.debug(f"  Failed to parse article: {e}")
                continue
        
        if records:
            logger.info(f"  {symbol} @ {source['name']}: {len(records)} new articles")
        
    except Exception as e:
        logger.warning(f"  Failed to scrape {symbol} from {source['name']}: {e}")
    
    return records


def scrape_stock(page: Page, symbol: str, conn, sources: list = None) -> int:
    """Scrape all sources for a single stock"""
    if sources is None:
        sources = list(NEWS_SOURCES.keys())
    
    total_records = []
    
    for source_key in sources:
        records = scrape_source(page, symbol, source_key, conn)
        total_records.extend(records)
        time.sleep(RATE_LIMIT)
    
    # Save to database
    if total_records:
        save_records(conn, total_records)
    
    return len(total_records)


def save_records(conn, records: list):
    """Save news records to database"""
    values = [
        (
            r["hash"],
            r["title"],
            r["url"],
            r["source"],
            r["published_at"],
            r["summary"],
            r["stock_symbols"],
            r.get("image_url")
        )
        for r in records
    ]
    
    with conn.cursor() as cur:
        execute_values(cur, """
            INSERT INTO market_news (hash, title, url, source, published_at, summary, stock_symbols, image_url)
            VALUES %s
            ON CONFLICT (hash) DO NOTHING
        """, values)
    conn.commit()


def run_tier(tier: str, page: Page, conn):
    """Run scraping for a specific tier"""
    if tier == "hot":
        stocks = HOT_STOCKS
    elif tier == "active":
        stocks = ACTIVE_STOCKS
    elif tier == "cold":
        # Cold tier = all stocks minus hot and active
        all_stocks = get_all_stocks()
        hot_active = set(HOT_STOCKS + ACTIVE_STOCKS)
        stocks = [s for s in all_stocks if s not in hot_active]
    elif tier == "all":
        stocks = get_all_stocks()
    else:
        logger.error(f"Unknown tier: {tier}")
        return
    
    logger.info(f"Starting {tier.upper()} tier: {len(stocks)} stocks")
    
    total_new = 0
    for i, symbol in enumerate(stocks):
        logger.info(f"[{i+1}/{len(stocks)}] Scraping {symbol}...")
        new_count = scrape_stock(page, symbol, conn)
        total_new += new_count
    
    logger.info(f"Completed {tier.upper()} tier: {total_new} new articles")


def run_single_stock(symbol: str, page: Page, conn, source: str = None):
    """Run scraping for a single stock"""
    logger.info(f"Scraping single stock: {symbol}")
    sources = [source] if source else None
    new_count = scrape_stock(page, symbol, conn, sources)
    logger.info(f"Completed: {new_count} new articles for {symbol}")


def connect_browser():
    """Connect to existing browser via CDP"""
    p = sync_playwright().start()
    try:
        browser = p.chromium.connect_over_cdp(BROWSER_CDP_URL)
        logger.info("Connected to browser")
        return p, browser
    except Exception as e:
        logger.error(f"Failed to connect to browser: {e}")
        logger.error(f"Make sure browser is running with: brave-browser --remote-debugging-port=9222")
        p.stop()
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="IDX News Scraper")
    parser.add_argument("--tier", choices=["hot", "active", "cold", "all"],
                        help="Scrape specific tier")
    parser.add_argument("--symbol", type=str, help="Scrape single stock symbol")
    parser.add_argument("--source", type=str, choices=list(NEWS_SOURCES.keys()),
                        help="Use specific news source only")
    parser.add_argument("--daemon", action="store_true",
                        help="Run as daemon with scheduler")
    
    args = parser.parse_args()
    
    # Connect to browser
    playwright, browser = connect_browser()
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    page = context.new_page()
    conn = get_db()
    
    try:
        if args.daemon:
            logger.info("Starting daemon mode with scheduler...")
            
            # Setup schedules
            for time_str in SCHEDULE["hot"]:
                schedule.every().day.at(time_str).do(run_tier, "hot", page, conn)
            for time_str in SCHEDULE["active"]:
                schedule.every().day.at(time_str).do(run_tier, "active", page, conn)
            for time_str in SCHEDULE["cold"]:
                schedule.every().day.at(time_str).do(run_tier, "cold", page, conn)
            
            logger.info("Scheduler running. Press Ctrl+C to stop.")
            while True:
                schedule.run_pending()
                time.sleep(60)
        
        elif args.symbol:
            run_single_stock(args.symbol.upper(), page, conn, args.source)
        
        elif args.tier:
            run_tier(args.tier, page, conn)
        
        else:
            parser.print_help()
    
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    
    finally:
        page.close()
        conn.close()
        playwright.stop()


if __name__ == "__main__":
    main()
