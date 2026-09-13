"""Post a curve-change notice to a Teams incoming webhook.

No-op until a URL is actually configured, so turning this on later is an env var,
not a code change. The "Post to a channel when a webhook request is received"
Workflows template posts an Adaptive Card straight from the request body -- it
is NOT a `{"text": ...}` envelope, it errors on anything that isn't itself a
valid card (``Property 'type' must be 'AdaptiveCard'``), confirmed against a
live flow. One ``TextBlock`` per line, since a card's ``TextBlock.text`` doesn't
reliably keep bare single newlines as separate lines across renderers.
"""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger("apx_curve_watch")

_TIMEOUT_SECONDS = 15
_CARD_SCHEMA = "http://adaptivecards.io/schemas/adaptive-card.json"


def _adaptive_card(text: str) -> dict:
    return {
        "type": "AdaptiveCard",
        "$schema": _CARD_SCHEMA,
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": line or " ", "wrap": True, "fontType": "Monospace"}
            for line in text.split("\n")
        ],
    }


def post(webhook_url: str | None, text: str) -> None:
    if not webhook_url:
        return
    try:
        resp = requests.post(webhook_url, json=_adaptive_card(text), timeout=_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.RequestException:
        logger.exception("Teams webhook post failed")
