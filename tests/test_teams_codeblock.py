from apx_curve_watch.teams_codeblock import build_card


def test_build_card_wraps_text_in_a_codeblock():
    card = build_card("hello\nworld")
    assert card["type"] == "AdaptiveCard"
    [code] = [item for item in card["body"] if item["type"] == "CodeBlock"]
    assert code["codeSnippet"].startswith("hello\nworld")


def test_build_card_appends_padding_lines_by_default():
    card = build_card("hello")
    [code] = [item for item in card["body"] if item["type"] == "CodeBlock"]
    assert code["codeSnippet"] == "hello" + "\n" * 4


def test_pad_lines_is_configurable():
    card = build_card("hello", pad_lines=0)
    [code] = [item for item in card["body"] if item["type"] == "CodeBlock"]
    assert code["codeSnippet"] == "hello"


def test_build_card_includes_a_title_textblock_when_given():
    card = build_card("hello", title="Test")
    texts = [item["text"] for item in card["body"] if item["type"] == "TextBlock"]
    assert texts == ["Test"]


def test_build_card_without_a_title_has_no_textblock():
    card = build_card("hello")
    assert all(item["type"] != "TextBlock" for item in card["body"])
