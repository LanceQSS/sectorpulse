"""Per-feed fetching. One source failing must never kill the run."""

import calendar
import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser
import httpx

from .config import FETCH_TIMEOUT_SECONDS, USER_AGENT

TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid"}
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


@dataclass
class FetchResult:
    source: str
    ok: bool
    error: str | None = None
    feed_item_count: int = 0
    items: list[dict] = field(default_factory=list)


def canonicalize(url: str) -> str:
    """Normalize a URL for dedupe: lowercase host, drop tracking params and fragment."""
    p = urlsplit(url.strip())
    query = urlencode(
        [
            (k, v)
            for k, v in parse_qsl(p.query, keep_blank_values=True)
            if not k.lower().startswith("utm_") and k.lower() not in TRACKING_PARAMS
        ]
    )
    path = p.path.rstrip("/") or "/"
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), path, query, ""))


def _clean_text(raw: str, limit: int = 800) -> str:
    text = WS_RE.sub(" ", html.unescape(TAG_RE.sub(" ", raw))).strip()
    return text[:limit]


def _published_iso(entry) -> str | None:
    # feedparser normalizes *_parsed to UTC struct_time; timegm, not mktime.
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if not t:
        return None
    return datetime.fromtimestamp(calendar.timegm(t), tz=timezone.utc).isoformat(
        timespec="seconds"
    )


def fetch_feed(source: dict) -> FetchResult:
    name = source["name"]
    try:
        resp = httpx.get(
            source["url"],
            headers={"User-Agent": USER_AGENT},
            timeout=FETCH_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            return FetchResult(name, ok=False, error=f"HTTP {resp.status_code}")
        parsed = feedparser.parse(resp.content)
        if parsed.bozo and not parsed.entries:
            reason = str(getattr(parsed, "bozo_exception", "unparseable feed"))[:120]
            return FetchResult(name, ok=False, error=f"parse error: {reason}")

        items = []
        for entry in parsed.entries:
            link = entry.get("link")
            title = _clean_text(entry.get("title", ""), 300)
            if not link or not title:
                continue
            summary = ""
            if entry.get("content"):
                summary = _clean_text(entry.content[0].get("value", ""))
            if not summary and entry.get("summary"):
                summary = _clean_text(entry.summary)
            items.append(
                {
                    "url": link,
                    "canonical_url": canonicalize(link),
                    "title": title,
                    "source": name,
                    "published": _published_iso(entry),
                    "summary": summary,
                }
            )
        return FetchResult(name, ok=True, feed_item_count=len(parsed.entries), items=items)
    except Exception as e:  # noqa: BLE001 — isolation is the contract here
        return FetchResult(name, ok=False, error=f"{type(e).__name__}: {e}")
