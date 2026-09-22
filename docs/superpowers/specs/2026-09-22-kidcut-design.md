# KidCut — Design Spec

## Overview

KidCut is a Python CLI tool (run as `python -m kidscan`) that converts 18+ movies
to kid-friendly versions by detecting and removing inappropriate scenes (drugs,
sex, extreme violence, adult content). It uses AI models to analyze subtitles and
ffmpeg to trim the identified scenes.

## Architecture

```
src/kidscan/
  __init__.py          — package marker (license header)
  __main__.py          — calls cli.main()
  cli.py               — orchestrator: file pick → track select → AI scan → edit → output
  config.py            — paths (prompt template, output dir)
  models.py            — dataclasses (SubtitleEntry, CutScene, MkvTrack, ScanRunSummary)
  vendors.py           — vendor discovery (env vars + Ollama) + model listing via API
  scanner.py           — AI analysis of subtitles, returns CutScene[]
  ffmpeg.py            — check binary, probe MKV, extract subtitles, cut scenes
  subtitle.py          — parse extracted SRT/ASS into SubtitleEntry[]
  editor.py            — auto/manual editing workflow (confirm/cut per scene)
  ui.py                — spinner helper (rich status)
  templates/
    review_prompt.md   — AI prompt ({{content}} placeholder)
```

## User Flow

1. CLI starts → ffmpeg availability check → raise error if not found
2. User browses filesystem to select input MKV (via questionary path input)
3. Script probes MKV → identifies default audio track → finds matching subtitle track
4. If no matching subtitle track → user picks audio + subtitle tracks via menus
5. Text-based subtitles (SRT, ASS) extracted and parsed into timestamped entries
6. User picks AI provider + model (same vendor model as IncluScan)
7. Subtitle content sent to AI → returns time ranges of inappropriate scenes
8. User chooses Automatic (cut all) or Manual (traverse one by one)
9. ffmpeg concatenates only clean segments → outputs `input-kidcut.mkv`

## Data Models

```python
@dataclass
class SubtitleEntry:
    index: int
    start: str      # "00:01:23,456"
    end: str        # "00:01:27,890"
    text: str

@dataclass
class CutScene:
    start: str      # start timestamp
    end: str        # end timestamp
    reason: str     # why inappropriate

@dataclass
class MkvTrack:
    index: int
    type: str       # "video", "audio", "subtitles"
    language: str
    default: bool
    codec: str
```

## ffmpeg Cutting Strategy

Use stream copy (no re-encode) with concat demuxer:
1. Determine clean segments (inverse of flagged scenes)
2. Build concat file listing each clean segment with timestamps
3. Run `ffmpeg -f concat -i concat.txt -c copy output.mkv`

## Prompt Template

File: `templates/review_prompt.md` (editable)
- Instructs AI to find scenes with drugs, sex, extreme violence, adult content
- Expects JSON array of `{start, end, reason}`
- Returns `[]` if content is clean

## Logo

SVG icon (80×80 px): scissors cutting a section out of a film strip.
Placed at project root as `KidCut.svg`.