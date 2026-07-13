# SectorPulse

**An automated daily industry digest that never fails silently.**

SectorPulse watches a set of industry news sources, archives everything it sees, has
Claude write a short executive digest each morning, and delivers it by email — while
committing every digest to this repo so there's a permanent, browsable record in
[`/digests`](digests/).

This instance is configured for a strategy team tracking the **EV-charging industry**,
but the sources are a five-line config list — point it at any industry.

## How it works

```mermaid
flowchart LR
    A[RSS/Atom feeds] -->|fetched independently| B[Dedupe vs archive]
    B --> C[data/articles.jsonl<br/>append-only archive]
    C --> D{Claude<br/>claude-haiku-4-5}
    D -->|ok| E[Executive digest]
    D -->|failure| F[Headline digest +<br/>degraded banner]
    E --> G[Email via Resend]
    F --> G
    E --> H[digests/YYYY-MM-DD.md<br/>committed by the Action]
    F --> H
```

- **GitHub Actions** runs the pipeline daily (12:00 UTC) plus on manual dispatch.
- **No database to babysit**: the archive is a committed, diffable JSONL file
  ([`data/articles.jsonl`](data/articles.jsonl)). Every run rebuilds its index from it,
  so a fresh checkout is all the state the pipeline needs.
- The digest prompt is written for an **executive audience** — what mattered and why,
  grouped by theme, plus a watch list — not a summary of summaries.

## The reliability rules (the actual product)

Most monitoring pipelines fail by going quiet. SectorPulse's contract is
**"watch these sources, tell me what matters, never fail silently"**:

1. **One source failing never kills the run.** Each feed is fetched independently and
   its status is recorded.
2. **Summarization degrades, it doesn't disappear.** If the Claude call fails for any
   reason, you still get the raw headlines — with a visible **"summarization degraded"**
   banner, never a silent gap.
3. **A total blackout sends an alert, not nothing.** If every source fails, you get an
   alert email and the run goes red.
4. **Staleness detection catches quietly-dead feeds.** A source whose newest item is
   7+ days old is flagged inside the digest. Zero new items on a given day is rendered
   neutrally — weekday publishers go quiet on weekends, and that's normal.
5. **The pipeline's health is part of the product.** Every digest ends with a
   per-source status footer, so the reader can see the machinery working (or not)
   without ever opening a log.

### A live demonstration: the dead feed we keep on purpose

One of the five monitored sources — **Green Car Reports** — is deliberately included as
a working exhibit. Its feed still returns HTTP 200 with valid, parseable XML, but it
hasn't published a new item since spring 2025. A naive pipeline would report it
"healthy" forever. SectorPulse flags it in every single digest footer:

> ⚠ **Green Car Reports** — newest item is 468 days old (source quiet — possible feed change or shutdown).

That line is the whole pitch in one sentence: the failure modes you don't see are the
ones that cost you.

## Sample digest

*Example of the summarized format, built from real items the pipeline collected
(live digests are in [`/digests`](digests/); when summarization is degraded the body
is headlines-by-source instead):*

> # SectorPulse digest — 2026-07-13
>
> ## What mattered
>
> - **Charging infrastructure: Eviny and Mer merge into Northern Europe's largest fast-charging provider.**
>   *Why it matters:* consolidation among European CPOs is accelerating — scale is becoming the price of entry in fast charging. [[1]](https://www.electrive.com/2026/07/10/eviny-and-mer-merge-to-become-northern-europes-largest-fast-charging-provider/)
> - **Policy: The European Commission's Battery Booster will put €1.5B into the European battery industry.**
>   *Why it matters:* a direct subsidy signal for localized cell supply chains that charging and storage vendors can plan against. [[1]](https://chargedevs.com/newswire/european-commissions-battery-booster-to-invest-e1-5-billion-in-the-european-battery-industry/)
> - **Fleet & V2G: Port of Long Beach commits $58.2M to electrification; California school-bus fleet goes live with managed charging and V2G.**
>   *Why it matters:* public-fleet money keeps arriving ahead of consumer demand — depot charging remains the near-term revenue pool. [[1]](https://chargedevs.com/newswire/port-of-long-beach-invests-58-2-million-to-expand-vehicle-and-equipment-electrification/) [[2]](https://chargedevs.com/newswire/the-mobility-house-enables-smart-charging-and-v2g-for-california-electric-school-bus-fleet/)
>
> **Watch list:** European CPO consolidation · US EV sales rebound post-tax-credit · sodium-ion moves (UNIGRID home storage, Alsym/ERITY) · Grab's 15× charging expansion in Vietnam.
>
> ---
>
> ## Pipeline health
>
> | Source | Status | Items in feed | New today | Newest item |
> |---|---|---|---|---|
> | Charged EVs | ✓ ok | 10 | 6 | 2026-07-10 |
> | electrive | ✓ ok | 30 | 10 | 2026-07-11 |
> | Electrek | ✓ ok | 100 | 17 | 2026-07-13 |
> | InsideEVs | ✓ ok | 20 | 14 | 2026-07-12 |
> | Green Car Reports | ⚠ stale | 15 | 0 | 2025-03-31 |
>
> ⚠ **Green Car Reports** — newest item is 468 days old (source quiet — possible feed change or shutdown).

## Stack

Python 3.12 · `feedparser` + `httpx` + `anthropic` (that's the whole dependency list) ·
Claude Haiku 4.5 for summarization · Resend for email · GitHub Actions for scheduling
and auto-commit.

## Run your own

See [DEPLOY.md](DEPLOY.md) — it's a fork, two secrets, and one repo variable.
