"""Render the digest as Markdown (committed to the repo) and HTML (emailed)."""

import html
from datetime import datetime, timezone

from .config import STALE_AFTER_DAYS

DEGRADED_BANNER_MD = (
    "> **⚠ Summarization degraded** — the Claude call failed ({reason}), so today's "
    "digest is raw headlines instead of analysis. The pipeline itself is healthy; "
    "see the footer for per-source status."
)


def _age_days(iso: str, now: datetime) -> int:
    return (now - datetime.fromisoformat(iso)).days


def source_status_lines(results, newest_published, new_counts, now) -> list[dict]:
    """One health row per source, consumed by both renderers."""
    rows = []
    for res in results:
        newest = newest_published.get(res.source)
        stale = bool(newest and _age_days(newest, now) >= STALE_AFTER_DAYS)
        rows.append(
            {
                "source": res.source,
                "ok": res.ok,
                "error": res.error,
                "in_feed": res.feed_item_count,
                "new_today": new_counts.get(res.source, 0),
                "newest": newest,
                "newest_age_days": _age_days(newest, now) if newest else None,
                "stale": stale,
            }
        )
    return rows


def _row_md(row) -> str:
    if not row["ok"]:
        return f"| {row['source']} | ✗ fetch failed: {row['error']} | — | — | — |"
    newest = row["newest"][:10] if row["newest"] else "never"
    status = "⚠ stale" if row["stale"] else "✓ ok"
    return (
        f"| {row['source']} | {status} | {row['in_feed']} | "
        f"{row['new_today']} | {newest} |"
    )


def _stale_notes(rows) -> list[str]:
    notes = []
    for row in rows:
        if row["stale"]:
            notes.append(
                f"⚠ **{row['source']}** — newest item is {row['newest_age_days']} days old "
                "(source quiet — possible feed change or shutdown)."
            )
    return notes


def render_markdown(date_str, digest, degraded, degraded_reason, rows, item_count) -> str:
    lines = [f"# SectorPulse digest — {date_str}", ""]
    if degraded:
        lines += [DEGRADED_BANNER_MD.format(reason=degraded_reason), ""]

    if item_count == 0:
        lines += ["No new items across monitored sources in the last 24 hours.", ""]
    elif degraded:
        lines += ["## Headlines (unsummarized)", ""]
        for source, items in digest["by_source"].items():
            lines.append(f"### {source}")
            for r in items:
                lines.append(f"- [{r['title']}]({r['url']})")
            lines.append("")
    else:
        lines += ["## What mattered", ""]
        for b in digest["bullets"]:
            links = " ".join(
                f"[[{i + 1}]]({u})" for i, u in enumerate(b["source_urls"])
            )
            lines.append(f"- **{b['theme']}: {b['headline']}**")
            lines.append(f"  *Why it matters:* {b['why_it_matters']} {links}")
        lines += ["", f"**Watch list:** {digest['watch_list']}", ""]

    lines += [
        "---",
        "",
        "## Pipeline health",
        "",
        "| Source | Status | Items in feed | New today | Newest item |",
        "|---|---|---|---|---|",
    ]
    lines += [_row_md(row) for row in rows]
    notes = _stale_notes(rows)
    if notes:
        lines += [""] + notes
    lines += [
        "",
        f"_{item_count} item(s) in today's digest window. Zero new items from a "
        "weekday publisher is normal on weekends; staleness is only flagged after "
        f"{STALE_AFTER_DAYS}+ quiet days._",
        "",
    ]
    return "\n".join(lines)


def render_html(date_str, digest, degraded, degraded_reason, rows, item_count) -> str:
    e = html.escape
    parts = [
        '<div style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;'
        'max-width:640px;margin:0 auto;padding:24px 16px;color:#1a1a1a;line-height:1.5">',
        f'<h1 style="font-size:20px;margin:0 0 4px">SectorPulse</h1>',
        f'<p style="color:#666;margin:0 0 20px">EV-charging industry digest — {e(date_str)}</p>',
    ]
    if degraded:
        parts.append(
            '<div style="background:#fff3cd;border:1px solid #e0a800;border-radius:6px;'
            'padding:12px 14px;margin:0 0 20px;font-size:14px">'
            "<strong>⚠ Summarization degraded</strong> — the Claude call failed "
            f"({e(degraded_reason)}), so today's digest is raw headlines instead of "
            "analysis. The pipeline itself is healthy; see the footer.</div>"
        )

    if item_count == 0:
        parts.append(
            '<p style="font-size:15px">No new items across monitored sources in the '
            "last 24 hours.</p>"
        )
    elif degraded:
        for source, items in digest["by_source"].items():
            parts.append(f'<h3 style="font-size:15px;margin:18px 0 6px">{e(source)}</h3>')
            parts.append('<ul style="margin:0;padding-left:20px;font-size:14px">')
            for r in items:
                parts.append(
                    f'<li style="margin:4px 0"><a href="{e(r["url"])}" '
                    f'style="color:#0b57d0">{e(r["title"])}</a></li>'
                )
            parts.append("</ul>")
    else:
        parts.append('<h2 style="font-size:16px;margin:0 0 10px">What mattered</h2>')
        for b in digest["bullets"]:
            links = " · ".join(
                f'<a href="{e(u)}" style="color:#0b57d0">source {i + 1}</a>'
                for i, u in enumerate(b["source_urls"])
            )
            parts.append(
                '<div style="margin:0 0 16px">'
                f'<div style="font-size:11px;text-transform:uppercase;letter-spacing:.05em;'
                f'color:#0b57d0;font-weight:600">{e(b["theme"])}</div>'
                f'<div style="font-size:15px;font-weight:600;margin:2px 0">{e(b["headline"])}</div>'
                f'<div style="font-size:14px;color:#444">{e(b["why_it_matters"])}</div>'
                f'<div style="font-size:12px;margin-top:2px">{links}</div></div>'
            )
        parts.append(
            '<div style="background:#f1f3f4;border-radius:6px;padding:10px 14px;'
            f'font-size:13px;margin:4px 0 8px"><strong>Watch list:</strong> '
            f'{e(digest["watch_list"])}</div>'
        )

    # Footer: the pipeline's health is part of the product.
    parts.append(
        '<hr style="border:none;border-top:1px solid #ddd;margin:24px 0 12px">'
        '<h3 style="font-size:13px;color:#666;margin:0 0 8px">PIPELINE HEALTH</h3>'
        '<table style="width:100%;border-collapse:collapse;font-size:12px;color:#444">'
        "<tr><td style='padding:3px 0'><strong>Source</strong></td><td><strong>Status</strong>"
        "</td><td><strong>In feed</strong></td><td><strong>New</strong></td>"
        "<td><strong>Newest</strong></td></tr>"
    )
    for row in rows:
        if not row["ok"]:
            status, in_feed, new, newest = f"✗ {e(row['error'] or 'failed')}", "—", "—", "—"
        else:
            status = "⚠ stale" if row["stale"] else "✓ ok"
            in_feed, new = str(row["in_feed"]), str(row["new_today"])
            newest = row["newest"][:10] if row["newest"] else "never"
        parts.append(
            f"<tr><td style='padding:3px 0'>{e(row['source'])}</td><td>{status}</td>"
            f"<td>{in_feed}</td><td>{new}</td><td>{newest}</td></tr>"
        )
    parts.append("</table>")
    for note in _stale_notes(rows):
        parts.append(
            f'<p style="font-size:12px;color:#8a6d00;margin:8px 0 0">'
            f'{e(note.replace("**", ""))}</p>'
        )
    parts.append(
        f'<p style="font-size:11px;color:#999;margin:12px 0 0">{item_count} item(s) in '
        "today's window. Zero new items from a weekday publisher is normal on weekends; "
        f"staleness is flagged after {STALE_AFTER_DAYS}+ quiet days.</p></div>"
    )
    return "".join(parts)


def render_alert_html(date_str, rows) -> str:
    e = html.escape
    parts = [
        '<div style="font-family:sans-serif;max-width:640px;margin:0 auto;padding:24px 16px">',
        '<div style="background:#f8d7da;border:1px solid #d9534f;border-radius:6px;'
        'padding:14px"><strong>🚨 SectorPulse alert</strong> — every monitored source '
        f"failed on {e(date_str)}. No digest could be produced.</div><ul>",
    ]
    for row in rows:
        parts.append(f"<li><strong>{e(row['source'])}</strong>: {e(row['error'] or '?')}</li>")
    parts.append("</ul><p>Likely causes: network outage in the runner, or a dependency "
                 "break. Check the Actions log for this run.</p></div>")
    return "".join(parts)
