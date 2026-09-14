"""Build a Teams Adaptive Card ``CodeBlock`` element for a monospace table.

``CodeBlock`` (Adaptive Cards 1.5+, Teams web/desktop only -- not mobile)
preserves line breaks and full row width properly, unlike a ``TextBlock``
(wraps, and a single multi-line one collapses its own newlines) or a real
``Table`` element (columns squeeze unreadably thin in Teams' narrow card
pane) -- both confirmed live and ruled out for exactly that reason.

Microsoft's own docs confirm the collapsed card previews only the first 10
lines of a ``codeSnippet``; expanding it reveals the rest via a real scroll,
confirmed live -- so nothing is silently lost, it just needs a click. A few
trailing blank lines pad past that preview boundary so the collapsed peek
lands on padding rather than a real row.

Known cosmetic bug, not fixable from here: past ~9 lines the line-number
gutter (there's no schema property to turn it off -- only ``codeSnippet``,
``language``, ``startLineNumber`` exist) doesn't reserve enough width for
double-digit numbers, so the second digit overlaps the row content. Confirmed
live to be bad enough to obscure real text, not just look messy.
"""

from __future__ import annotations

_CARD_SCHEMA = "http://adaptivecards.io/schemas/adaptive-card.json"
_CARD_VERSION = "1.5"
_PAD_LINES = 4


def build_card(text: str, title: str = "", *, pad_lines: int = _PAD_LINES) -> dict:
    body: list[dict] = []
    if title:
        body.append({"type": "TextBlock", "text": title, "weight": "Bolder", "wrap": True})
    body.append({"type": "CodeBlock", "codeSnippet": text + "\n" * pad_lines})
    return {"type": "AdaptiveCard", "$schema": _CARD_SCHEMA, "version": _CARD_VERSION, "body": body}
