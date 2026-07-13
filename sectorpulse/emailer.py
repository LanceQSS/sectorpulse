"""Delivery via the Resend API. Secrets come from the environment only."""

import os

import httpx

RESEND_URL = "https://api.resend.com/emails"


def send_email(subject: str, html: str) -> str:
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not set")
    to = os.environ.get("DIGEST_EMAIL_TO")
    if not to:
        raise RuntimeError("DIGEST_EMAIL_TO is not set")
    sender = os.environ.get("DIGEST_EMAIL_FROM", "SectorPulse <onboarding@resend.dev>")

    resp = httpx.post(
        RESEND_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={"from": sender, "to": [to], "subject": subject, "html": html},
        timeout=30,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"Resend API error {resp.status_code}: {resp.text[:300]}")
    return resp.json().get("id", "?")
