"""Pipeline orchestrator: fetch -> dedupe/archive -> digest -> deliver.

Reliability contract (never fail silently):
- one source failing never kills the run; its status appears in the footer
- Claude failure  -> headline digest with a visible "summarization degraded" banner
- all sources down -> alert email + alert digest file, exit 1
- email failure    -> digest file is still written/committed, exit 1
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import ARCHIVE_PATH, DIGEST_DIR, SOURCES
from .digest import headline_fallback, select_digest_items, summarize
from .emailer import send_email
from .fetching import fetch_feed
from .render import (
    render_alert_html,
    render_html,
    render_markdown,
    source_status_lines,
)
from .store import append_new, load_archive, newest_published_by_source


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="sectorpulse")
    parser.add_argument(
        "--no-email",
        action="store_true",
        help="local development: skip delivery, still write the digest file",
    )
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc)
    date_str = now.date().isoformat()
    now_iso = now.isoformat(timespec="seconds")

    # 1. Fetch each source independently.
    results = [fetch_feed(s) for s in SOURCES]
    for res in results:
        mark = "ok " if res.ok else "FAIL"
        detail = f"{res.feed_item_count} items" if res.ok else res.error
        print(f"[{mark}] {res.source}: {detail}")

    digest_path = Path(DIGEST_DIR) / f"{date_str}.md"
    digest_path.parent.mkdir(parents=True, exist_ok=True)

    # 2a. Total blackout: alert, don't go quiet.
    if not any(res.ok for res in results):
        print("ALERT: all sources failed")
        rows = source_status_lines(results, {}, {}, now)
        digest_path.write_text(
            f"# SectorPulse — {date_str}\n\n🚨 **ALERT: all sources failed.** "
            "No digest could be produced.\n\n"
            + "\n".join(f"- **{r['source']}**: {r['error']}" for r in rows)
            + "\n",
            encoding="utf-8",
        )
        exit_code = 1
        if not args.no_email:
            try:
                send_email(
                    f"[SectorPulse] ALERT — all sources failed ({date_str})",
                    render_alert_html(date_str, rows),
                )
                print("alert email sent")
            except Exception as e:  # noqa: BLE001
                print(f"alert email FAILED: {e}")
        return exit_code

    # 2b. Dedupe and append to the archive.
    archive_path = Path(ARCHIVE_PATH)
    records = load_archive(archive_path)
    fetched = [item for res in results for item in res.items]
    new_records = append_new(archive_path, records, fetched, now_iso)
    records += new_records
    new_counts: dict[str, int] = {}
    for r in new_records:
        new_counts[r["source"]] = new_counts.get(r["source"], 0) + 1
    print(f"archive: {len(new_records)} new, {len(records)} total")

    # 3. Digest.
    items = select_digest_items(records, now)
    degraded, degraded_reason = False, ""
    if items:
        try:
            digest = summarize(items)
        except Exception as e:  # noqa: BLE001 — degrade, never go silent
            degraded, degraded_reason = True, type(e).__name__
            digest = headline_fallback(items)
            print(f"summarization degraded ({type(e).__name__}: {e})")
    else:
        digest = {}

    rows = source_status_lines(results, newest_published_by_source(records), new_counts, now)
    markdown = render_markdown(date_str, digest, degraded, degraded_reason, rows, len(items))
    digest_path.write_text(markdown, encoding="utf-8")
    print(f"digest written: {digest_path}")

    # 4. Deliver.
    failed_count = sum(1 for res in results if not res.ok)
    subject = f"SectorPulse digest — {date_str}"
    if degraded:
        subject += " [summarization degraded]"
    elif failed_count:
        subject += f" [{failed_count} source(s) down]"

    if args.no_email:
        print("email skipped (--no-email)")
        return 0
    try:
        email_id = send_email(
            subject, render_html(date_str, digest, degraded, degraded_reason, rows, len(items))
        )
        print(f"email sent: {email_id}")
    except Exception as e:  # noqa: BLE001
        # The digest file is already written (and gets committed by the Action);
        # exit non-zero so the failed delivery is visible in the run status.
        print(f"email FAILED: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
