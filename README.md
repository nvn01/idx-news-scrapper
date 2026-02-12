# IDX News Scraper

Automated news scraper for Indonesian Stock Exchange (IDX) listed companies. Fetches news from multiple Indonesian financial news sources using stock ticker tags.

## Features

- 🔄 **Tiered scraping** - Hot/Active/Cold stock classification for efficient fetching
- 📰 **5 News Sources** - Kontan, CNBC Indonesia, Investor.id, IDX Channel, Kompas
- 🔗 **Playwright-based** - Connects to existing browser to avoid anti-bot detection
- 💾 **Deduplication** - Hash-based detection to avoid duplicate articles
- ⏰ **Scheduled runs** - Configurable timing for different stock tiers

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
git clone https://github.com/yourusername/idx-news-scraper.git
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

### Option 2: Google Chrome

```bash
google-chrome --remote-debugging-port=9222
```

### Option 3: Chromium

```bash
chromium --remote-debugging-port=9222
```

### Option 4: Microsoft Edge

```bash
msedge --remote-debugging-port=9222
```

### Verify Connection

After starting browser, verify debugging endpoint is accessible:

```bash
curl http://localhost:9222/json/version
```

You should see JSON output with browser info.

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
python news_scraper.py --tier cold
python news_scraper.py --tier all

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

### Run as systemd service

```bash
# Copy service file
sudo cp idx-news-scraper.service /etc/systemd/system/

# Enable and start
sudo systemctl enable idx-news-scraper
sudo systemctl start idx-news-scraper

# Check status
sudo systemctl status idx-news-scraper
```

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
    scraped_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_news_symbols ON market_news USING GIN(stock_symbols);
CREATE INDEX idx_news_published ON market_news(published_at DESC);
CREATE INDEX idx_news_source ON market_news(source);
```

## Project Structure

```
idx-news-scraper/
├── news_scraper.py      # Main scraper script
├── config.py            # Configuration and stock tiers
├── sources/             # News source parsers
│   ├── __init__.py
│   ├── kontan.py
│   ├── cnbc.py
│   ├── investor.py
│   ├── idxchannel.py
│   └── kompas.py
├── requirements.txt
├── .env.example
├── README.md
└── idx-news-scraper.service
```

## Troubleshooting

### Browser connection failed

```
Failed to connect to browser at http://localhost:9222
```

**Solution:** Make sure browser is running with `--remote-debugging-port=9222` flag.

### Anti-bot detection

If you encounter CAPTCHA or blocking:
1. Use the browser manually to solve CAPTCHA once
2. The session will persist since we use existing browser
3. Consider adding longer delays between requests

### Rate limiting

Increase `RATE_LIMIT_SECONDS` in `.env` if you get blocked:

```env
RATE_LIMIT_SECONDS=5
```

## License

MIT
