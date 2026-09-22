import subprocess

from kidcut.ffmpeg import check_binary, get_timestamp_seconds


def test_check_binary_passes_when_ffmpeg_found():
    check_binary()


def test_check_binary_raises_when_ffmpeg_missing(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError()))
    import pytest
    with pytest.raises(RuntimeError, match="ffmpeg not found"):
        check_binary()


def test_get_timestamp_seconds():
    assert get_timestamp_seconds("00:01:30,500") == 90.5
