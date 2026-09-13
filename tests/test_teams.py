from apx_curve_watch import teams


def test_post_is_a_noop_without_a_url(monkeypatch):
    calls = []
    monkeypatch.setattr(teams.requests, "post", lambda *a, **k: calls.append((a, k)))
    teams.post(None, "hello")
    assert calls == []


def test_post_sends_text_as_json_body(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

    def fake_post(url, json, timeout):
        calls.append((url, json, timeout))
        return FakeResponse()

    monkeypatch.setattr(teams.requests, "post", fake_post)
    teams.post("https://example.invalid/webhook", "curve moved")
    assert calls == [("https://example.invalid/webhook", {"text": "curve moved"}, 15)]


def test_post_swallows_request_errors(monkeypatch):
    import requests

    def fake_post(*args, **kwargs):
        raise requests.ConnectionError("no route to host")

    monkeypatch.setattr(teams.requests, "post", fake_post)
    teams.post("https://example.invalid/webhook", "curve moved")  # must not raise
