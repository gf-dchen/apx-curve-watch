from apx_curve_watch import teams


def test_post_card_is_a_noop_without_a_url(monkeypatch):
    calls = []
    monkeypatch.setattr(teams.requests, "post", lambda *a, **k: calls.append((a, k)))
    teams.post_card(None, {"type": "AdaptiveCard"})
    assert calls == []


def test_post_card_sends_the_card_verbatim(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

    def fake_post(url, json, timeout):
        calls.append((url, json, timeout))
        return FakeResponse()

    monkeypatch.setattr(teams.requests, "post", fake_post)
    card = {"type": "AdaptiveCard", "body": [{"type": "Image", "url": "data:image/png;base64,"}]}
    teams.post_card("https://example.invalid/webhook", card)
    assert calls == [("https://example.invalid/webhook", card, 15)]


def test_post_card_swallows_request_errors(monkeypatch):
    import requests

    def fake_post(*args, **kwargs):
        raise requests.ConnectionError("no route to host")

    monkeypatch.setattr(teams.requests, "post", fake_post)
    teams.post_card("https://example.invalid/webhook", {"type": "AdaptiveCard"})  # must not raise
