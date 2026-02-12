# IDX News Scraper 🚀

Automated news scraper for Indonesian Stock Exchange (IDX) listed companies. Fetches news from multiple Indonesian financial news sources using stock ticker tags.

> **Newly Updated:** Now features **Machine Learning-based Filter** to remove irrelevant news! 🧠✨

## Features

- 🧠 **ML Keyword Filtering** - Smart analysis of news content to distinguish between relevant stock news and noise (e.g., distinguishing "Gempa Bumi" from $BUMI stock). Uses context-aware positive/negative keyword scoring.
- 🔄 **Tiered scraping** - Hot/Active/Cold stock classification for efficient fetching
- 📰 **5 News Sources** - Kontan, CNBC Indonesia, Investor.id, IDX Channel, Kompas
- 🕒 **Smart Time Parsing** - Accurately parses relative times (e.g., "5 minutes ago") into precise timestamps.
- 🖼️ **Real Image Extraction** - Handles lazy-loading images and filters out placeholders automatically.
- 🔗 **Playwright-based** - Connects to existing browser to avoid anti-bot detection
- 💾 **Deduplication** - Hash-based detection to avoid duplicate articles
- ⏰ **Scheduled runs** - Configurable timing for different stock tiers

## Machine Learning Filtering 🧠

The scraper uses a `keywords.json` dictionary to filter noise for "Risky Stocks" (stocks with common words as names like `BUMI`, `BUKA`, `GOTO`, `DEWA`).

**Logic:**
1. **Negative Check**: If an article contains a "negative" word (e.g., *gempa, warung*)...
2. **Context Check**: It looks for "positive" financial context words (e.g., *saham, investor, capital*).
3. **Decision**:
   - ❌ **No Context?** -> Skipped (Irrelevant noise)
   - ✅ **Has Context?** -> Kept (Relevant news)

## News Sources

| Source | URL Pattern |
|--------|-------------|
| Kontan | `https://www.kontan.co.id/tag/{symbol}` |
| CNBC Indonesia | `https://www.cnbcindonesia.com/tag/{symbol}` |
| Investor.id | `https://investor.id/tag/{symbol}` |
| IDX Channel | `https://www.idxchannel.com/tag/{symbol}` |
| Kompas | `https://www.kompas.com/tag/{symbol}` |

## Requirements

- Python 3.10+
- Chromium-based browser (Brave, Chrome, Edge, Chromium)
- PostgreSQL database

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/nvn01/idx-news-scraper.git
cd idx-news-scraper
```

### 2. Create Python virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate   # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env with your database credentials
```

## Browser Setup

The scraper connects to an existing browser instance via Chrome DevTools Protocol (CDP). This helps avoid anti-bot detection.

### Option 1: Brave Browser (Recommended)

```bash
# Start Brave with remote debugging enabled
brave-browser --remote-debugging-port=9222

# Or run in background with tmux
tmux new -s browser
brave-browser --remote-debugging-port=9222
# Press Ctrl+B, then D to detach
```

## Configuration

### Environment Variables (.env)

```env
# Database connection
DATABASE_URL=postgresql://user:password@localhost:5432/idx_news

# Browser CDP endpoint
BROWSER_CDP_URL=http://localhost:9222

# Scraping settings
RATE_LIMIT_SECONDS=2
MAX_ARTICLES_PER_PAGE=20
```

### Stock Tiers

Stocks are categorized into tiers based on trading activity:

| Tier | Stocks | Fetch Interval | Description |
|------|--------|----------------|-------------|
| HOT | LQ45 index | Every 2 hours | Most liquid, high news volume |
| ACTIVE | IDX80, recently active | Every 6 hours | Moderate activity |
| COLD | All others | Once daily | Low volume stocks |

## Usage

### Run scraper manually

```bash
# Activate virtual environment
source venv/bin/activate

# Run specific tier
python news_scraper.py --tier hot
python news_scraper.py --tier active

# Run specific stock
python news_scraper.py --symbol BBCA

# Test single source
python news_scraper.py --symbol BBCA --source kontan
```

### Run with scheduler

```bash
python news_scraper.py --daemon
```

This will run the scraper on schedule:
- Hot tier: Every 2 hours (07:00, 09:00, 11:00, 13:00, 15:00, 17:00, 21:00)
- Active tier: Every 6 hours (07:00, 13:00, 19:00)
- Cold tier: Once daily (17:00)

## Database Schema

```sql
CREATE TABLE market_news (
    id SERIAL PRIMARY KEY,
    hash VARCHAR(64) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    source VARCHAR(50) NOT NULL,
    published_at TIMESTAMP,
    summary TEXT,
    stock_symbols TEXT[],
    image_url TEXT,
    scraped_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_news_symbols ON market_news USING GIN(stock_symbols);
CREATE INDEX idx_news_published ON market_news(published_at DESC);
CREATE INDEX idx_news_source ON market_news(source);
```

## License

MIT
