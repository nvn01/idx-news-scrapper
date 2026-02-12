"""
Configuration for IDX News Scraper
Stock tiers based on IDX indices for efficient scraping
"""

# LQ45 - Most liquid 45 stocks (HOT tier - every 2 hours)
HOT_STOCKS = [
    "AADI", "ACES", "ADMR", "ADRO", "AKRA", "AMMN", "AMRT", "ANTM", "ASII",
    "BBCA", "BBNI", "BBRI", "BBTN", "BMRI", "BRPT", "BUMI", "CPIN", "CTRA",
    "DSSA", "EMTK", "EXCL", "GOTO", "HEAL", "ICBP", "INCO", "INDF", "INKP",
    "ISAT", "ITMG", "JPFA", "KLBF", "MAPI", "MBMA", "MDKA", "MEDC", "NCKL",
    "PGAS", "PGEO", "PTBA", "SCMA", "SMGR", "TLKM", "TOWR", "UNTR", "UNVR"
]

# IDX80 minus LQ45 - Active stocks (ACTIVE tier - every 6 hours)
ACTIVE_STOCKS = [
    "ARTO", "AVIA", "BRMS", "BSDE", "BTPS", "BUKA", "CMRY", "DSNG", "ELSA",
    "ENRG", "ERAA", "ESSA", "INDY", "KIJA", "KPIG", "LSIP", "MAPA", "MARK",
    "MTEL", "MYOR", "PANI", "RATU", "SIDO", "SMRA", "SRTG", "SSIA", "TAPG",
    "TCPI", "TKIM", "TPIA", "BRIS", "PWON", "MIKA", "JSMR"
]

# News sources with their tag URL patterns (verified via browser inspection)
NEWS_SOURCES = {
    "kontan": {
        "name": "Kontan",
        "url_pattern": "https://www.kontan.co.id/tag/{symbol}",
        "article_selector": "#load_berita > li",
        "title_selector": ".sp-hl h1 a",
        "link_selector": ".sp-hl h1 a",
        "date_selector": ".font-gray",
        "summary_selector": None,  # No summary on tag page
        "image_selector": "div.pic img",  # Uses data-src for lazy loading
    },
    "cnbc": {
        "name": "CNBC Indonesia",
        "url_pattern": "https://www.cnbcindonesia.com/tag/{symbol}",
        "article_selector": "article",
        "title_selector": "h2",
        "link_selector": "a",
        "date_selector": "span > span:last-child",
        "summary_selector": None,  # No summary on tag page
        "image_selector": "img",  # Uses src directly
    },
    "investor": {
        "name": "Investor.id",
        "url_pattern": "https://investor.id/tag/{symbol}",
        "article_selector": ".row.mb-4.position-relative",
        "title_selector": "h4.my-3",
        "link_selector": "a.stretched-link",
        "date_selector": "span.text-muted.small",
        "summary_selector": "span.text-muted.text-truncate-2-lines",
        "image_selector": ".col-4 img",  # Uses src directly
    },
    "idxchannel": {
        "name": "IDX Channel",
        "url_pattern": "https://www.idxchannel.com/tag/{symbol}",
        "article_selector": ".bt-con",
        "title_selector": "h2.list-berita-baru a",
        "link_selector": "h2.list-berita-baru a",
        "date_selector": ".mh-clock",
        "summary_selector": None,  # No summary on tag page
        "image_selector": "img",  # Uses data-src for lazy loading
    },
    "kompas": {
        "name": "Kompas",
        "url_pattern": "https://www.kompas.com/tag/{symbol}",
        "article_selector": "a.article-link",
        "title_selector": "h2.articleTitle",
        "link_selector": None,  # Container itself is the link
        "date_selector": ".articlePost-date",
        "summary_selector": None,  # No summary on tag page
        "image_selector": ".articleItem-img img",  # Uses src directly
    }
}


# Scraping schedule (24h format, WIB timezone)
SCHEDULE = {
    "hot": ["07:00", "09:00", "11:00", "13:00", "15:00", "17:00", "21:00"],
    "active": ["07:00", "13:00", "19:00"],
    "cold": ["17:00"]  # Once daily
}

# Rate limiting
DEFAULT_RATE_LIMIT = 2  # seconds between requests
MAX_ARTICLES_PER_PAGE = 20  # Stop after this many articles per source
EARLY_EXIT_THRESHOLD = 3  # Stop if first N articles are duplicates
