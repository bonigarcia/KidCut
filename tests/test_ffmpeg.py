import json
import subprocess

from kidscan.ffmpeg import check_binary, get_timestamp_seconds, format_timestamp


def test_check_binary_passes_when_ffmpeg_found():
    check_binary()


def test_check_binary_raises_when_ffmpeg_missing(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError()))
    import pytest
    with pytest.raises(RuntimeError, match="ffmpeg not found"):
        check_binary()


def test_get_timestamp_seconds():
    assert get_timestamp_seconds("00:01:30,500") == 90.5


def test_format_timestamp():
    assert format_timestamp(90.5) == "00:01:30,500"


def test_format_timestamp_hours():
    assert format_timestamp(3661.0) == "01:01:01,000"