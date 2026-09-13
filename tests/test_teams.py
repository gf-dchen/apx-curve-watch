from apx_curve_watch import teams


def test_post_is_a_noop_without_a_url(monkeypatch):
    calls = []
    monkeypatch.setattr(teams.requests, "post", lambda *a, **k: calls.append((a, k)))
    teams.post(None, "hello")
    assert calls == []


def test_post_sends_a_valid_adaptive_card(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

    def fake_post(url, json, timeout):
        calls.append((url, json, timeout))
        return FakeResponse()

    monkeypatch.setattr(teams.requests, "post", fake_post)
    teams.post("https://example.invalid/webhook", "curve moved")

    [(url, card, timeout)] = calls
    assert url == "https://example.invalid/webhook"
    assert timeout == 15
    assert card["type"] == "AdaptiveCard"
    assert card["body"] == [
        {"type": "TextBlock", "text": "curve moved", "wrap": True, "fontType": "Monospace"}
    ]


def test_post_splits_multiline_text_into_one_textblock_per_line(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

    def fake_post(url, json, timeout):
        calls.append(json)
        return FakeResponse()

    monkeypatch.setattr(teams.requests, "post", fake_post)
    teams.post("https://example.invalid/webhook", "line one\nline two")
    [card] = calls
    assert [block["text"] for block in card["body"]] == ["line one", "line two"]


def test_post_swallows_request_errors(monkeypatch):
    import requests

    def fake_post(*args, **kwargs):
        raise requests.ConnectionError("no route to host")

    monkeypatch.setattr(teams.requests, "post", fake_post)
    teams.post("https://example.invalid/webhook", "curve moved")  # must not raise
