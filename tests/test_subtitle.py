from kidscan.subtitle import parse_subtitles, parse_srt, parse_ass


def test_parse_srt_returns_entries():
    content = """1
00:00:01,000 --> 00:00:04,000
Hello, how are you?

2
00:00:05,000 --> 00:00:08,000
I'm fine, thanks.
"""
    entries = parse_subtitles(content)
    assert len(entries) == 2
    assert entries[0].start == "00:00:01,000"
    assert entries[0].end == "00:00:04,000"
    assert entries[0].text == "Hello, how are you?"
    assert entries[1].text == "I'm fine, thanks."


def test_parse_srt_multiline_text():
    content = """1
00:00:01,000 --> 00:00:04,000
Line one
Line two
"""
    entries = parse_subtitles(content)
    assert len(entries) == 1
    assert "Line one" in entries[0].text
    assert "Line two" in entries[0].text


def test_parse_ass_returns_entries():
    content = """[Script Info]
Title: Example

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:04.00,Default,,0,0,0,,Hello, how are you?
Dialogue: 0,0:00:05.00,0:00:08.00,Default,,0,0,0,,I'm fine, thanks.
"""
    entries = parse_subtitles(content)
    assert len(entries) == 2
    assert entries[0].start == "0:00:01,00"
    assert entries[0].text == "Hello, how are you?"


def test_parse_empty_content():
    assert parse_subtitles("") == []


def test_parse_srt_auto_detection():
    srt = """1
00:00:01,000 --> 00:00:04,000
Test"""
    entries = parse_subtitles(srt)
    assert len(entries) == 1


def test_parse_ass_auto_detection():
    ass = """[Script Info]
Title: Test

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:04.00,Default,,0,0,0,,Test"""
    entries = parse_subtitles(ass)
    assert len(entries) == 1