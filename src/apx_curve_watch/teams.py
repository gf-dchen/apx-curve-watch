"""Post a curve-change notice to a Teams incoming webhook.

No-op until a URL is actually configured, so turning this on later is an env var,
not a code change. The payload is a bare ``{"text": ...}`` body -- the generic
shape a Power Automate "when a webhook request is received" flow can read off its
trigger; adjust the key(s) here once there's a real flow to match.
"""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger("apx_curve_watch")

_TIMEOUT_SECONDS = 15


def post(webhook_url: str | None, text: str) -> None:
    if not webhook_url:
        return
    try:
        resp = requests.post(webhook_url, json={"text": text}, timeout=_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.RequestException:
        logger.exception("Teams webhook post failed")
