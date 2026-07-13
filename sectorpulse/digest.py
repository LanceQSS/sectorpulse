"""Digest content: Claude summarization with a headline fallback that needs no API."""

import json
from datetime import datetime, timedelta

from .config import (
    FIRST_SEEN_WINDOW_HOURS,
    MAX_DIGEST_ITEMS,
    MODEL,
    PUBLISHED_WINDOW_HOURS,
)

SYSTEM_PROMPT = """You write SectorPulse, a daily digest for a strategy team tracking the \
EV-charging industry. Your reader is an executive who has 90 seconds. You are an analyst, \
not an aggregator: identify what actually mattered and say why it matters strategically — \
never produce a summary of summaries.

Rules:
- At most 5 bullets. Group related items into one bullet.
- Each bullet: a short theme label (e.g. "Charging infrastructure", "Policy", "OEM strategy"),
  a concrete one-sentence headline of what happened, a one-line why_it_matters written for a
  strategy audience, and the source URLs it draws on (from the provided items only).
- Prioritize charging-industry relevance: infrastructure, networks, hardware, grid, policy,
  standards, major OEM/battery moves. Skip reviews, deals-of-the-week, and fluff.
- Digest length must scale honestly with the material. A thin news day produces a short
  digest — 1 or 2 bullets is a fine answer. Never pad, never inflate minor news.
- watch_list: one line naming 2-4 developing threads worth watching."""

DIGEST_SCHEMA = {
    "type": "object",
    "properties": {
        "bullets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "theme": {"type": "string"},
                    "headline": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                    "source_urls": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["theme", "headline", "why_it_matters", "source_urls"],
                "additionalProperties": False,
            },
        },
        "watch_list": {"type": "string"},
    },
    "required": ["bullets", "watch_list"],
    "additionalProperties": False,
}


def select_digest_items(records: list[dict], now: datetime) -> list[dict]:
    first_seen_cut = (now - timedelta(hours=FIRST_SEEN_WINDOW_HOURS)).isoformat(
        timespec="seconds"
    )
    published_cut = (now - timedelta(hours=PUBLISHED_WINDOW_HOURS)).isoformat(
        timespec="seconds"
    )
    items = [
        r
        for r in records
        if r.get("first_seen", "") >= first_seen_cut
        and (r.get("published") or "") >= published_cut
    ]
    items.sort(key=lambda r: r["published"], reverse=True)
    return items[:MAX_DIGEST_ITEMS]


def summarize(items: list[dict]) -> dict:
    """One Claude call -> {"bullets": [...], "watch_list": str}. Raises on any failure;
    the caller degrades to the headline fallback."""
    import anthropic  # deferred so a missing/broken SDK also lands in the fallback path

    payload = [
        {
            "source": r["source"],
            "published": r["published"],
            "title": r["title"],
            "summary": (r.get("summary") or "")[:600],
            "url": r["url"],
        }
        for r in items
    ]
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": DIGEST_SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": (
                    "Items from the last 24 hours of monitored feeds, newest first, "
                    "as a JSON array:\n\n" + json.dumps(payload, ensure_ascii=False)
                ),
            }
        ],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("model refused the summarization request")
    text = next(b.text for b in response.content if b.type == "text")
    data = json.loads(text)
    if not isinstance(data.get("bullets"), list) or "watch_list" not in data:
        raise ValueError("digest response did not match the expected shape")
    return data


def headline_fallback(items: list[dict]) -> dict:
    """Raw headlines grouped by source — the never-silent degraded digest."""
    by_source: dict[str, list[dict]] = {}
    for r in items:
        by_source.setdefault(r["source"], []).append(r)
    return {"by_source": by_source}
