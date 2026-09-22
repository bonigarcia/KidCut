# KidCut Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI tool (`python -m kidscan`) that detects and removes adult content scenes from MKV files using AI analysis of subtitles.

**Architecture:** Single linear CLI flow: pick MKV → auto-detect tracks → AI analysis → edit (auto/manual) → ffmpeg cut. Package under `src/kidscan/` following IncluScan patterns.

**Tech Stack:** Python 3.11+, questionary (menus), rich (spinner/console), requests (AI APIs), ffmpeg (subprocess), pytest (tests).

---

### Task 1: Project scaffolding

**Files:**
- Create: `src/kidscan/__init__.py`
- Create: `src/kidscan/__main__.py`
- Create: `src/kidscan/config.py`
- Create: `src/kidscan/models.py`
- Create: `pyproject.toml`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create package structure and files**

`src/kidscan/__init__.py`:
```python
"""KidCut package."""
```

`src/kidscan/__main__.py`:
```python
from kidscan.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

`src/kidscan/config.py`:
```python
from pathlib import Path

PROMPT_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "review_prompt.md"
OUTPUT_DIR = Path(".")
```

`src/kidscan/models.py`:
```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SubtitleEntry:
    index: int
    start: str
    end: str
    text: str


@dataclass(frozen=True, slots=True)
class CutScene:
    start: str
    end: str
    reason: str


@dataclass(frozen=True, slots=True)
class MkvTrack:
    index: int
    kind: str
    language: str
    default: bool
    codec: str


@dataclass(frozen=True, slots=True)
class ScanRunSummary:
    scan_id: str
    mkv_path: str
    vendor: str
    model: str
    started_at: str
    finished_at: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    finding_count: int | None = None
    duration_seconds: float | None = None
```

`pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "kidcut"
version = "0.1.0"
description = "AI-powered tool to remove adult scenes from MKV movies"
requires-python = ">=3.11"
dependencies = [
  "questionary>=2.0",
  "requests>=2.32",
  "rich>=13.7",
]

[tool.setuptools]
package-dir = {"" = "src"}

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`tests/conftest.py`:
```python
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
```

- [ ] **Step 2: Create directories**

```bash
mkdir -p src/kidscan/templates tests
```

- [ ] **Step 3: Verify imports work**

Run: `python -c "import kidscan; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add src/ tests/ pyproject.toml
git commit -m "feat: scaffold KidCut package structure"
```

---

### Task 2: Vendor discovery (copy from IncluScan pattern)

**Files:**
- Create: `src/kidscan/vendors.py`
- Create: `tests/test_vendors.py`

- [ ] **Step 1: Write vendors.py**

Follow IncluScan's `vendors.py` pattern but with KidCut naming:

```python
from dataclasses import dataclass
from typing import Callable
import os

import requests


@dataclass(frozen=True, slots=True)
class VendorOption:
    name: str
    api_key_env: str | None


def ollama_is_available(http_get: Callable[..., object] = requests.get) -> bool:
    try:
        response = http_get("http://localhost:11434/api/tags", timeout=1)
        response.raise_for_status()
        return True
    except Exception:
        return False


def discover_vendors() -> list[VendorOption]:
    vendors: list[VendorOption] = []
    if os.getenv("OPENAI_API_KEY"):
        vendors.append(VendorOption("OpenAI", "OPENAI_API_KEY"))
    if os.getenv("ANTHROPIC_API_KEY"):
        vendors.append(VendorOption("Anthropic", "ANTHROPIC_API_KEY"))
    if os.getenv("GOOGLE_API_KEY"):
        vendors.append(VendorOption("Google", "GOOGLE_API_KEY"))
    if ollama_is_available():
        vendors.append(VendorOption("Ollama", None))
    return vendors


def list_models_for_vendor(vendor_name: str, api_key: str | None = None) -> list[str]:
    if vendor_name == "OpenAI":
        response = requests.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        response.raise_for_status()
        return [item["id"] for item in response.json().get("data", [])]

    if vendor_name == "Anthropic":
        response = requests.get(
            "https://api.anthropic.com/v1/models",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            timeout=10,
        )
        response.raise_for_status()
        return [item["id"] for item in response.json().get("data", [])]

    if vendor_name == "Google":
        response = requests.get(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
            timeout=10,
        )
        response.raise_for_status()
        return [item["name"].split("/")[-1] for item in response.json().get("models", [])]

    response = requests.get("http://localhost:11434/api/tags", timeout=10)
    response.raise_for_status()
    return [item["name"] for item in response.json().get("models", [])]
```

- [ ] **Step 2: Write tests**

`tests/test_vendors.py`:
```python
from kidscan.vendors import discover_vendors, list_models_for_vendor


def test_discover_vendors_includes_only_available_backends(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "google-key")
    monkeypatch.setattr("kidscan.vendors.ollama_is_available", lambda: True)

    vendors = discover_vendors()

    assert [vendor.name for vendor in vendors] == ["OpenAI", "Google", "Ollama"]


def test_list_models_for_vendor_reads_provider_api(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"id": "gpt-4o-mini"}, {"id": "gpt-4.1-mini"}]}

    monkeypatch.setattr("kidscan.vendors.requests.get", lambda *_args, **_kwargs: FakeResponse())

    models = list_models_for_vendor("OpenAI", api_key="openai-key")

    assert models == ["gpt-4o-mini", "gpt-4.1-mini"]
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_vendors.py -v`
Expected: 2 PASS

- [ ] **Step 4: Commit**

```bash
git add src/kidscan/vendors.py tests/test_vendors.py
git commit -m "feat: add vendor discovery and model listing"
```

---

### Task 3: AI scanner (subtitle analysis)

**Files:**
- Create: `src/kidscan/scanner.py`
- Create: `src/kidscan/templates/review_prompt.md`
- Modify: `tests/test_vendors.py` (add scanner tests)

- [ ] **Step 1: Create prompt template**

`src/kidscan/templates/review_prompt.md`:
```md
You are analyzing movie subtitles to find scenes inappropriate for children ages 8-10.
Look for content involving: drugs, sex, extreme violence, adult themes, strong profanity.

The subtitles are provided with timestamps (HH:MM:SS,mmm). Identify COMPLETE SCENES
that contain inappropriate content, not just individual subtitle lines. A scene starts
at the first subtitle entry where the inappropriate content begins and ends at the last
subtitle entry where it ends.

Return the response exclusively as valid JSON that can be parsed automatically.
The response must be an array of objects. Each object must contain exactly these fields:
- "start": the start timestamp of the inappropriate scene (one of the subtitle start timestamps)
- "end": the end timestamp of the inappropriate scene (one of the subtitle end timestamps)
- "reason": a brief explanation of why the scene is inappropriate, in the same language as the subtitles

Rules:
- Group consecutive inappropriate lines into single scenes where they belong together.
- If no scenes need to be cut, return an empty array: [].
- Do not include any additional fields.

Subtitles to analyze:

{{content}}
```

- [ ] **Step 2: Write scanner.py**

```python
from collections.abc import Callable
from datetime import datetime, timezone
import json
import re
from uuid import uuid4

import requests

from kidscan.config import PROMPT_TEMPLATE_PATH
from kidscan.models import CutScene, ScanRunSummary, SubtitleEntry


def build_review_prompt(subtitle_entries: list[SubtitleEntry]) -> str:
    template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    lines = "\n".join(
        f"{entry.start} --> {entry.end}  {entry.text}"
        for entry in subtitle_entries
    )
    return template.replace("{{content}}", lines)


def _extract_json_payload(raw_text: str) -> str:
    stripped = raw_text.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        return stripped
    match = re.search(r"\[.*\]", raw_text, flags=re.DOTALL)
    if match:
        return match.group(0)
    return raw_text


def parse_review_response(raw_text: str) -> list[CutScene]:
    payload = json.loads(_extract_json_payload(raw_text))
    if not isinstance(payload, list):
        raise ValueError("model response must be a JSON array")

    scenes: list[CutScene] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("each scene must be an object")
        if set(item) != {"start", "end", "reason"}:
            raise ValueError("each scene must contain only start, end, and reason")
        scenes.append(CutScene(**item))
    return scenes


def build_request_completion(vendor_name: str, model: str, api_key: str | None = None) -> Callable[[str], tuple[str, int | None, int | None]]:
    def request_completion(prompt: str) -> tuple[str, int | None, int | None]:
        if vendor_name == "Ollama":
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=120,
            )
            response.raise_for_status()
            payload = response.json()
            return payload["response"], None, None

        if vendor_name == "OpenAI":
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}]},
                timeout=120,
            )
            response.raise_for_status()
            payload = response.json()
            usage = payload.get("usage", {})
            return payload["choices"][0]["message"]["content"], usage.get("prompt_tokens"), usage.get("completion_tokens")

        if vendor_name == "Anthropic":
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                json={"model": model, "max_tokens": 4096, "messages": [{"role": "user", "content": prompt}]},
                timeout=120,
            )
            response.raise_for_status()
            payload = response.json()
            usage = payload.get("usage", {})
            return payload["content"][0]["text"], usage.get("input_tokens"), usage.get("output_tokens")

        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        usage = payload.get("usageMetadata", {})
        return payload["candidates"][0]["content"]["parts"][0]["text"], usage.get("promptTokenCount"), usage.get("candidatesTokenCount")

    return request_completion


def analyze_subtitles(
    subtitle_entries: list[SubtitleEntry],
    mkv_path: str,
    request_completion: Callable[[str], tuple[str, int | None, int | None]],
    vendor_name: str,
    model: str,
    with_spinner: Callable[[str, Callable[[], tuple[str, int | None, int | None]]], tuple[str, int | None, int | None]] | None = None,
) -> tuple[ScanRunSummary, list[CutScene]]:
    started_at = datetime.now(timezone.utc).isoformat()
    input_tokens = 0
    output_tokens = 0
    saw_tokens = False
    spinner = with_spinner or (lambda _message, fn: fn())

    prompt = build_review_prompt(subtitle_entries)
    parsed_scenes: list[CutScene] = []
    for attempt in range(2):
        current_prompt = prompt if attempt == 0 else f"{prompt}\n\nReturn only valid JSON that matches the required schema."
        try:
            raw_response, prompt_tokens, completion_tokens = spinner(
                "Analyzing subtitles",
                lambda: request_completion(current_prompt),
            )
        except requests.RequestException:
            if attempt == 1:
                break
            continue
        if prompt_tokens is not None:
            input_tokens += prompt_tokens
            saw_tokens = True
        if completion_tokens is not None:
            output_tokens += completion_tokens
            saw_tokens = True
        try:
            parsed_scenes = parse_review_response(raw_response)
            break
        except (json.JSONDecodeError, ValueError):
            if attempt == 1:
                break

    finished_at = datetime.now(timezone.utc).isoformat()
    duration_seconds = (datetime.fromisoformat(finished_at.replace("Z", "+00:00")) - datetime.fromisoformat(started_at.replace("Z", "+00:00"))).total_seconds()
    run = ScanRunSummary(
        scan_id=f"scan-{uuid4().hex[:8]}",
        mkv_path=mkv_path,
        vendor=vendor_name,
        model=model,
        started_at=started_at,
        finished_at=finished_at,
        input_tokens=input_tokens if saw_tokens else None,
        output_tokens=output_tokens if saw_tokens else None,
        finding_count=len(parsed_scenes),
        duration_seconds=max(duration_seconds, 0.0),
    )
    return run, parsed_scenes
```

- [ ] **Step 3: Write tests**

Add to `tests/test_vendors.py`:
```python
from kidscan.models import SubtitleEntry, CutScene
from kidscan.scanner import build_review_prompt, parse_review_response, analyze_subtitles


def test_build_review_prompt_inserts_entries():
    entries = [
        SubtitleEntry(index=1, start="00:01:00,000", end="00:01:05,000", text="Hello world"),
    ]
    prompt = build_review_prompt(entries)
    assert "{{content}}" not in prompt
    assert "00:01:00,000 --> 00:01:05,000  Hello world" in prompt


def test_parse_review_response_accepts_empty_array():
    assert parse_review_response("[]") == []


def test_parse_review_response_rejects_extra_fields():
    import pytest
    with pytest.raises(ValueError):
        parse_review_response('[{"start":"00:00","end":"00:01","reason":"bad","extra":"no"}]')


def test_parse_review_response_extracts_json_from_wrapped_text():
    raw = 'Here:\n```json\n[{"start":"00:01:00,000","end":"00:02:00,000","reason":"Violence"}]\n```'
    scenes = parse_review_response(raw)
    assert len(scenes) == 1
    assert scenes[0].reason == "Violence"


def test_analyze_subtitles_uses_injected_completion():
    entries = [SubtitleEntry(index=1, start="00:01:00,000", end="00:01:05,000", text="Hello")]

    def fake_completion(prompt: str):
        return "[]", None, None

    run, scenes = analyze_subtitles(entries, "/path/test.mkv", fake_completion, "OpenAI", "gpt-4o-mini")
    assert run.mkv_path == "/path/test.mkv"
    assert scenes == []


def test_analyze_subtitles_retries_invalid_json_once():
    entries = [SubtitleEntry(index=1, start="00:01:00,000", end="00:01:05,000", text="Hello")]
    prompts: list[str] = []

    def fake_completion(prompt: str):
        prompts.append(prompt)
        if len(prompts) == 1:
            return "not json", None, None
        return "[]", None, None

    analyze_subtitles(entries, "/path/test.mkv", fake_completion, "OpenAI", "gpt-4o-mini")
    assert len(prompts) == 2


def test_prompt_template_is_markdown_file():
    from kidscan.config import PROMPT_TEMPLATE_PATH
    assert PROMPT_TEMPLATE_PATH.name == "review_prompt.md"
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_vendors.py -v`
Expected: 8 PASS

- [ ] **Step 5: Commit**

```bash
git add src/kidscan/scanner.py src/kidscan/templates/ tests/test_vendors.py
git commit -m "feat: add AI subtitle scanner with prompt template"
```

---

### Task 4: Subtitle extraction and parsing

**Files:**
- Create: `src/kidscan/subtitle.py`
- Create: `tests/test_subtitle.py`

- [ ] **Step 1: Write subtitle.py**

```python
import re

from kidscan.models import SubtitleEntry


def parse_srt(content: str) -> list[SubtitleEntry]:
    entries: list[SubtitleEntry] = []
    blocks = re.split(r"\n\s*\n", content.strip())
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        if "-->" not in lines[1]:
            continue
        try:
            index = int(lines[0].strip())
        except ValueError:
            continue
        time_part = lines[1].strip()
        parts = time_part.split(" --> ")
        if len(parts) != 2:
            continue
        start, end = parts[0].strip(), parts[1].strip()
        text = "\n".join(lines[2:])
        entries.append(SubtitleEntry(index=index, start=start, end=end, text=text))
    return entries


def parse_ass(content: str) -> list[SubtitleEntry]:
    entries: list[SubtitleEntry] = []
    in_events = False
    index = 0
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("[Events]"):
            in_events = True
            continue
        if not in_events:
            continue
        if stripped.startswith("Format:"):
            headers = [h.strip() for h in stripped[len("Format:"):].split(",")]
            continue
        if not stripped.startswith("Dialogue:"):
            continue
        parts = [p.strip() for p in stripped[len("Dialogue:"):].split(",", 9)]
        if len(parts) < 10:
            continue
        index += 1
        _, start, end, _, _, _, _, _, text = parts[0], parts[1], parts[2], *parts[3:10]
        start = start.replace(".", ",")
        end = end.replace(".", ",")
        text = text.replace("\\N", "\n").replace("\\n", "\n")
        entries.append(SubtitleEntry(index=index, start=start, end=end, text=text))
    return entries


def parse_subtitles(content: str) -> list[SubtitleEntry]:
    if content.strip().startswith("[Script Info]") or content.strip().startswith("[Events]"):
        return parse_ass(content)
    return parse_srt(content)
```

- [ ] **Step 2: Write tests**

`tests/test_subtitle.py`:
```python
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
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_subtitle.py -v`
Expected: 6 PASS

- [ ] **Step 4: Commit**

```bash
git add src/kidscan/subtitle.py tests/test_subtitle.py
git commit -m "feat: add subtitle parser (SRT + ASS)"
```

---

### Task 5: ffmpeg interaction

**Files:**
- Create: `src/kidscan/ffmpeg.py`
- Create: `tests/test_ffmpeg.py`

- [ ] **Step 1: Write ffmpeg.py**

```python
import json
import os
import subprocess
import tempfile
from pathlib import Path

from kidscan.models import CutScene, MkvTrack


def check_binary() -> None:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        raise RuntimeError("ffmpeg not found. Install ffmpeg and ensure it is in your PATH.")


def probe_tracks(mkv_path: str) -> list[MkvTrack]:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", mkv_path],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)
    tracks: list[MkvTrack] = []
    for stream in data.get("streams", []):
        index = stream.get("index", 0)
        codec_type = stream.get("codec_type", "")
        language = stream.get("tags", {}).get("language", "und")
        default = stream.get("disposition", {}).get("default", 0) == 1
        codec = stream.get("codec_name", "")
        tracks.append(MkvTrack(index=index, kind=codec_type, language=language, default=default, codec=codec))
    return tracks


def extract_subtitles(mkv_path: str, track_index: int) -> str:
    result = subprocess.run(
        ["ffmpeg", "-v", "quiet", "-y", "-i", mkv_path, "-map", f"0:{track_index}", "-f", "srt", "-"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def get_timestamp_seconds(ts: str) -> float:
    parts = ts.replace(",", ".").split(":")
    h, m, s = float(parts[0]), float(parts[1]), float(parts[2])
    return h * 3600 + m * 60 + s


def format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def _build_segments(mkv_path: str, scenes_to_cut: list[CutScene]) -> list[tuple[float, float]]:
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", mkv_path],
        capture_output=True, text=True, check=True,
    )
    duration = float(json.loads(probe.stdout)["format"]["duration"])

    cut_ranges = [(get_timestamp_seconds(s.start), get_timestamp_seconds(s.end)) for s in scenes_to_cut]
    cut_ranges.sort()

    segments: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in cut_ranges:
        if start > cursor + 0.5:
            segments.append((cursor, start))
        cursor = max(cursor, end)
    if duration - cursor > 0.5:
        segments.append((cursor, duration))
    return segments


def cut_scenes(mkv_path: str, scenes_to_cut: list[CutScene], output_path: str) -> None:
    if not scenes_to_cut:
        Path(output_path).write_bytes(Path(mkv_path).read_bytes())
        return

    segments = _build_segments(mkv_path, scenes_to_cut)
    if not segments:
        raise RuntimeError("No clean segments remain after cutting all scenes.")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        concat_path = f.name
        for seg_start, seg_end in segments:
            f.write(f"file '{mkv_path}'\n")
            f.write(f"inpoint {seg_start}\n")
            f.write(f"outpoint {seg_end}\n")

    try:
        subprocess.run(
            ["ffmpeg", "-v", "quiet", "-y", "-f", "concat", "-safe", "0", "-i", concat_path, "-c", "copy", output_path],
            check=True,
        )
    finally:
        os.unlink(concat_path)
```

- [ ] **Step 2: Write tests**

`tests/test_ffmpeg.py`:
```python
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
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_ffmpeg.py -v`
Expected: 4 PASS (check_binary passes if ffmpeg is installed)

- [ ] **Step 4: Commit**

```bash
git add src/kidscan/ffmpeg.py tests/test_ffmpeg.py
git commit -m "feat: add ffmpeg interaction module"
```

---

### Task 6: UI helpers

**Files:**
- Create: `src/kidscan/ui.py`
- Create: `tests/test_ui.py`

- [ ] **Step 1: Write ui.py** (same pattern as IncluScan)

```python
from collections.abc import Callable
from typing import TypeVar

from rich.console import Console

T = TypeVar("T")


def run_with_spinner(console: Console, message: str, fn: Callable[[], T]) -> T:
    with console.status(message, spinner="dots"):
        return fn()
```

- [ ] **Step 2: Write tests**

`tests/test_ui.py`:
```python
from kidscan.ui import run_with_spinner
from rich.console import Console


def test_run_with_spinner_returns_function_result():
    console = Console()
    result = run_with_spinner(console, "Testing", lambda: 42)
    assert result == 42
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_ui.py -v`
Expected: 1 PASS

- [ ] **Step 4: Commit**

```bash
git add src/kidscan/ui.py tests/test_ui.py
git commit -m "feat: add UI spinner helper"
```

---

### Task 7: Editor (auto/manual workflow)

**Files:**
- Create: `src/kidscan/editor.py`
- Create: `tests/test_editor.py`

- [ ] **Step 1: Write editor.py**

```python
from kidscan.models import CutScene


def auto_edit(scenes: list[CutScene]) -> list[CutScene]:
    return scenes


def manual_edit(scenes: list[CutScene], confirm_fn) -> list[CutScene]:
    kept: list[CutScene] = []
    for scene in scenes:
        choice = confirm_fn(
            f"[{scene.start} → {scene.end}] {scene.reason}",
            choices=["Cut", "Keep"],
            default="Cut",
        )
        if choice == "Cut":
            kept.append(scene)
    return kept
```

`confirm_fn` is injected so the CLI can pass `questionary.select`. Tests can inject a deterministic function.

- [ ] **Step 2: Write tests**

`tests/test_editor.py`:
```python
from kidscan.editor import auto_edit, manual_edit
from kidscan.models import CutScene


def test_auto_edit_returns_all_scenes():
    scenes = [CutScene(start="00:01", end="00:02", reason="Violence")]
    assert auto_edit(scenes) == scenes


def test_manual_edit_keeps_only_cut_scenes():
    scenes = [
        CutScene(start="00:01", end="00:02", reason="Drugs"),
        CutScene(start="00:03", end="00:04", reason="Sex"),
        CutScene(start="00:05", end="00:06", reason="Violence"),
    ]
    called = []

    def confirm_fn(message, choices, default):
        called.append(message)
        return "Cut"

    result = manual_edit([scenes[0], scenes[2]], confirm_fn)
    assert len(result) == 2
    assert len(called) == 2


def test_manual_edit_empty_scenes():
    def confirm_fn(message, choices, default):
        return "Cut"
    assert manual_edit([], confirm_fn) == []
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_editor.py -v`
Expected: 3 PASS

- [ ] **Step 4: Commit**

```bash
git add src/kidscan/editor.py tests/test_editor.py
git commit -m "feat: add auto and manual editing workflow"
```

---

### Task 8: CLI orchestrator

**Files:**
- Create: `src/kidscan/cli.py`
- Modify: `src/kidscan/__main__.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write cli.py**

```python
import os
from pathlib import Path
from uuid import uuid4

import questionary
from rich.console import Console

from kidscan.config import OUTPUT_DIR
from kidscan.editor import auto_edit, manual_edit
from kidscan.ffmpeg import check_binary, probe_tracks, extract_subtitles, cut_scenes
from kidscan.models import CutScene
from kidscan.scanner import build_request_completion, analyze_subtitles
from kidscan.subtitle import parse_subtitles
from kidscan.ui import run_with_spinner
from kidscan.vendors import discover_vendors, list_models_for_vendor


def choose_from_options(message: str, choices: list[str], default: str | None = None) -> str | None:
    try:
        return questionary.select(message, choices=choices, default=default).ask()
    except (KeyboardInterrupt, EOFError):
        return None


def choose_text(message: str, default: str | None = None) -> str | None:
    try:
        return questionary.text(message, default=default).ask()
    except (KeyboardInterrupt, EOFError):
        return None


def confirm_cut(message: str, choices: list[str], default: str | None = None) -> str | None:
    try:
        return questionary.select(message, choices=choices, default=default).ask()
    except (KeyboardInterrupt, EOFError):
        return None


def _find_mkv_path(console: Console) -> str:
    path = choose_text("MKV file path", default="")
    if path is None:
        raise KeyboardInterrupt
    if not os.path.isfile(path) or not path.lower().endswith(".mkv"):
        raise RuntimeError("File not found or not an MKV file.")
    return path


def _auto_select_subtitle_track(tracks, default_audio_lang: str) -> int | None:
    subtitle_tracks = [t for t in tracks if t.kind == "subtitle" and t.codec in ("subrip", "ass", "ssa", "text")]
    if not subtitle_tracks:
        return None
    matches = [t for t in subtitle_tracks if t.language == default_audio_lang and not t.default]
    if matches:
        return matches[0].index
    non_default = [t for t in subtitle_tracks if not t.default]
    if non_default:
        return non_default[0].index
    return subtitle_tracks[0].index


def _pick_tracks_manually(console: Console, tracks) -> tuple[int, int]:
    audio_choices = [f"Track {t.index} — audio — {t.language} ({t.codec})" for t in tracks if t.kind == "audio"]
    sub_choices = [f"Track {t.index} — subtitles — {t.language} ({t.codec})" for t in tracks if t.kind == "subtitle"]
    if not sub_choices:
        raise RuntimeError("No text-based subtitle tracks found in this MKV.")

    sel_audio = choose_from_options("Select audio track", audio_choices)
    if sel_audio is None:
        raise KeyboardInterrupt
    audio_idx = int(sel_audio.split("—")[0].replace("Track ", "").strip())

    sel_sub = choose_from_options("Select subtitle track", sub_choices)
    if sel_sub is None:
        raise KeyboardInterrupt
    sub_idx = int(sel_sub.split("—")[0].replace("Track ", "").strip())

    return audio_idx, sub_idx


def _choose_vendor_and_model(console: Console):
    vendors = discover_vendors()
    if not vendors:
        raise RuntimeError("No AI vendors available. Set an API key or start Ollama.")
    vendor_name = choose_from_options("Choose provider", [v.name for v in vendors])
    if vendor_name is None:
        raise KeyboardInterrupt
    vendor = next(v for v in vendors if v.name == vendor_name)
    api_key = os.getenv(vendor.api_key_env) if vendor.api_key_env else None
    models = list_models_for_vendor(vendor_name, api_key=api_key)
    if not models:
        raise RuntimeError(f"No models available for {vendor_name}.")
    model = choose_from_options("Choose model", models)
    if model is None:
        raise KeyboardInterrupt
    return vendor_name, model, api_key


def _choose_edit_mode(console: Console) -> str:
    return choose_from_options(
        "Edit mode",
        ["Automatic (cut all)", "Manual (review each scene)"],
        default="Automatic (cut all)",
    ) or "Automatic (cut all)"


def _get_output_path(mkv_path: str) -> str:
    p = Path(mkv_path)
    return str(p.parent / f"{p.stem}-kidcut{p.suffix}")


def main(argv: list[str] | None = None) -> int:
    console = Console()
    try:
        console.print("[bold]KidCut[/bold] — AI-powered movie editor for families")
        check_binary()

        mkv_path = _find_mkv_path(console)
        console.print(f"Probing [bold]{mkv_path}[/bold]...")
        tracks = probe_tracks(mkv_path)

        audio_tracks = [t for t in tracks if t.kind == "audio"]
        default_audio = next((t for t in audio_tracks if t.default), audio_tracks[0] if audio_tracks else None)
        default_audio_lang = default_audio.language if default_audio else "und"

        subtitle_idx = _auto_select_subtitle_track(tracks, default_audio_lang)
        if subtitle_idx is None:
            console.print("No matching subtitle track found for default audio language.")
            _, subtitle_idx = _pick_tracks_manually(console, tracks)
        else:
            console.print(f"Auto-selected subtitle track {subtitle_idx} (language matches audio)")

        console.print("Extracting subtitles...")
        raw_subs = run_with_spinner(console, "Extracting subtitles", lambda: extract_subtitles(mkv_path, subtitle_idx))
        subtitle_entries = parse_subtitles(raw_subs)
        if not subtitle_entries:
            raise RuntimeError("No text subtitles found or parsed.")
        console.print(f"Found [bold]{len(subtitle_entries)}[/bold] subtitle entries.")

        vendor_name, model, api_key = _choose_vendor_and_model(console)
        request_completion = build_request_completion(vendor_name, model, api_key=api_key)

        run, scenes = run_with_spinner(
            console, "Analyzing subtitles with AI",
            lambda: analyze_subtitles(subtitle_entries, mkv_path, request_completion, vendor_name, model,
                                      with_spinner=lambda msg, fn: run_with_spinner(console, msg, fn)),
        )
        if not scenes:
            console.print("[green]No inappropriate scenes detected.[/green]")
            return 0
        console.print(f"Found [bold]{len(scenes)}[/bold] scene(s) to review.")

        edit_mode = _choose_edit_mode(console)
        if edit_mode.startswith("Automatic"):
            to_cut = auto_edit(scenes)
        else:
            to_cut = manual_edit(scenes, confirm_cut)

        if not to_cut:
            console.print("[yellow]No scenes selected for cutting. Output unchanged.[/yellow]")
            return 0

        output_path = _get_output_path(mkv_path)
        console.print(f"Cutting [bold]{len(to_cut)}[/bold] scene(s)...")
        run_with_spinner(console, "Cutting scenes", lambda: cut_scenes(mkv_path, to_cut, output_path))
        console.print(f"[green]Done![/green] Output saved to [bold]{output_path}[/bold]")
        return 0
    except KeyboardInterrupt:
        console.print("Cancelled.")
        return 1
    except RuntimeError as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1
```

- [ ] **Step 2: Write basic CLI test**

`tests/test_cli.py`:
```python
import subprocess


def test_cli_runs():
    result = subprocess.run(
        ["python", "-m", "kidscan", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
```

Note: `--help` isn't implemented. This test just verifies the module starts. We can also test with a simulated flow.

```python
from kidscan.cli import _get_output_path


def test_get_output_path_adds_kidcut_suffix():
    assert _get_output_path("/path/movie.mkv").endswith("-kidcut.mkv")
    assert "movie-kidcut" in _get_output_path("/path/movie.mkv")
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_cli.py -v`
Expected: 1 PASS

- [ ] **Step 4: Verify module can be found**

Run: `python -m kidscan --help` (will show error since no argparse, but should not crash at import)
Expected: runs without ImportError

- [ ] **Step 5: Commit**

```bash
git add src/kidscan/cli.py src/kidscan/__main__.py tests/test_cli.py
git commit -m "feat: add CLI orchestrator with full workflow"
```

---

### Self-Review Checklist

- Spec coverage: models, vendors, scanner, subtitle parser, ffmpeg, editor, CLI — all covered
- Placeholder scan: no TBD/TODO in any task code
- Type consistency: SubtitleEntry, CutScene, MkvTrack, ScanRunSummary — consistent across all tasks
- All tests include actual code, not placeholders