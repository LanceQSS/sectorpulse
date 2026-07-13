"""Source list and pipeline tunables."""

import os

SOURCES = [
    {"name": "Charged EVs", "url": "https://chargedevs.com/feed/"},
    {"name": "electrive", "url": "https://www.electrive.com/feed/"},
    {"name": "Electrek", "url": "https://electrek.co/feed/"},
    {"name": "InsideEVs", "url": "https://insideevs.com/rss/articles/all/"},
    # Kept deliberately: this feed returns HTTP 200 with valid XML but has not
    # published since April 2025. A naive pipeline would report it healthy
    # forever. Its permanent staleness flag in every digest footer is a live
    # demonstration of the monitoring rules — see README.
    {"name": "Green Car Reports", "url": "https://www.greencarreports.com/rss"},
]

# A source whose newest item is older than this is flagged in the digest.
# Weekday-only publishers go quiet on weekends; 7 days avoids false alarms.
STALE_AFTER_DAYS = 7

# Digest input: items first seen within the last 24h (i.e. new since the last
# daily run), but only if actually published within the last 72h — so the
# first run's archive backfill doesn't flood the digest with week-old news.
FIRST_SEEN_WINDOW_HOURS = 24
PUBLISHED_WINDOW_HOURS = 72
MAX_DIGEST_ITEMS = 60

FETCH_TIMEOUT_SECONDS = 20
USER_AGENT = "SectorPulse/0.1 (+https://github.com/LanceQSS/sectorpulse)"

MODEL = os.environ.get("SECTORPULSE_MODEL", "claude-haiku-4-5")

ARCHIVE_PATH = "data/articles.jsonl"
DIGEST_DIR = "digests"
