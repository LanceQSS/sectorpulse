"""Append-only JSONL archive. The committed file is the source of truth;
every run rebuilds its in-memory index from it, so fresh checkouts just work."""

import json
from pathlib import Path


def load_archive(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def append_new(path: Path, records: list[dict], items: list[dict], now_iso: str) -> list[dict]:
    """Dedupe items against the archive by canonical URL, append survivors."""
    known = {r["canonical_url"] for r in records}
    new = []
    for item in items:
        if item["canonical_url"] in known:
            continue
        known.add(item["canonical_url"])
        new.append({**item, "first_seen": now_iso})
    if new:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            for record in new:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return new


def newest_published_by_source(records: list[dict]) -> dict[str, str]:
    """Newest published timestamp per source across the whole archive.

    Based on publication dates, not fetch dates: a dead feed that keeps
    serving its old items still reads as stale."""
    newest: dict[str, str] = {}
    for r in records:
        published = r.get("published")
        if published and published > newest.get(r["source"], ""):
            newest[r["source"]] = published
    return newest
