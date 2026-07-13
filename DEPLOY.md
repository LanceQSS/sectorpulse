# Deploying your own SectorPulse

## 1. Fork or clone this repo

The archive (`data/articles.jsonl`) and digests are committed, so you may want to
delete both directories' contents in your fork to start with a clean history.

## 2. Configure sources

Edit the `SOURCES` list in [`sectorpulse/config.py`](sectorpulse/config.py) —
name + feed URL per source. Tunables (staleness threshold, digest windows, model)
are at the top of the same file.

## 3. Set secrets and variables

In your repo: **Settings → Secrets and variables → Actions**.

| Kind | Name | Value |
|---|---|---|
| Secret | `ANTHROPIC_API_KEY` | From [platform.claude.com](https://platform.claude.com) — the digest uses `claude-haiku-4-5`, so a day's run costs a fraction of a cent |
| Secret | `RESEND_API_KEY` | From [resend.com](https://resend.com) (free tier is fine) |
| Variable | `DIGEST_EMAIL_TO` | The recipient address |

Secrets never appear in code, logs, or committed files; the pipeline reads them from
the environment only. The workflow is written for a public repo.

**Resend note:** the default sender `onboarding@resend.dev` can only deliver to the
email address that owns the Resend account. To send to anyone else, verify a domain
in Resend and set the repo variable `DIGEST_EMAIL_FROM` (e.g.
`SectorPulse <digest@yourdomain.com>`) — or just make `DIGEST_EMAIL_TO` your own
account address.

## 4. Enable and test the workflow

1. **Actions** tab → enable workflows for the fork.
2. Open **daily-digest** → **Run workflow** (manual dispatch).
3. A green run = digest emailed + `digests/YYYY-MM-DD.md` and the updated archive
   committed back to the repo.

The schedule is `0 12 * * *` (12:00 UTC daily) — edit
[`.github/workflows/digest.yml`](.github/workflows/digest.yml) to taste.

## Failure behavior (by design)

| Situation | What happens | Run status |
|---|---|---|
| One or more feeds fail | Run completes; failures shown in the digest footer | green |
| Claude call fails | Headline digest sent with a "summarization degraded" banner | green |
| Every feed fails | Alert email + alert file committed | red |
| Email delivery fails | Digest file still written and committed | red |

Red runs are intentional signal: if delivery breaks, you find out from GitHub's
workflow-failure notification instead of from silence.

## Local development

```bash
pip install -r requirements.txt

# No secrets needed — writes the digest file, skips email.
# Without ANTHROPIC_API_KEY the digest degrades to headlines (by design).
python -m sectorpulse.run --no-email

# Full run:
export ANTHROPIC_API_KEY=... RESEND_API_KEY=... DIGEST_EMAIL_TO=you@example.com
python -m sectorpulse.run
```
