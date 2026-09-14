"""Post an already-built Adaptive Card to a Teams incoming webhook.

No-op until a URL is actually configured, so turning this on later is an env
var, not a code change. The "Post to a channel when a webhook request is
received" Workflows template posts an Adaptive Card straight from the request
body -- it errors on anything that isn't itself a valid card
(``Property 'type' must be 'AdaptiveCard'``), confirmed against a live flow.
Card-building lives in ``teams_codeblock`` (and elsewhere); this module only
moves bytes.
"""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger("apx_curve_watch")

_TIMEOUT_SECONDS = 15


def post_card(webhook_url: str | None, card: dict) -> None:
    if not webhook_url:
        return
    try:
        resp = requests.post(webhook_url, json=card, timeout=_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.RequestException:
        logger.exception("Teams webhook post failed")
