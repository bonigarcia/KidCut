# KidCut ![](https://bonigarcia.dev/img/kidcut.png)

AI-powered CLI tool that detects and removes adult scenes from MKV movies, creating kid-friendly versions. Uses AI models to analyze subtitles and ffmpeg to trim inappropriate scenes (drugs, sex, extreme violence, adult content).


## Quickstart

KidCut is a Python CLI tool run as:

```bash
pip install -e .
python -m kidscan
```

### Interactive workflow

1. **Select MKV** — browse the filesystem to pick your movie file
2. **Track detection** — auto-detects subtitle track matching the default audio language (or lets you pick manually)
3. **Subtitle extraction** — extracts and parses SRT/ASS text subtitles
4. **Choose AI provider** — supports OpenAI, Anthropic, Google, OpenRouter, and Ollama (when running locally)
5. **AI analysis** — model identifies complete scenes with inappropriate content
6. **Edit mode** — choose **Automatic** (cut all flagged scenes) or **Manual** (review each scene one by one)
7. **Output** — ffmpeg produces `input-kidcut.mkv` with flagged scenes removed (stream copy, no re-encode)

### Requirements

- **Python 3.11+**
- **ffmpeg** installed and available in your PATH

### AI providers

| Provider | Env variable |
|----------|-------------|
| OpenAI   | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| Google   | `GOOGLE_API_KEY` |
| OpenRouter   | `OPENROUTER_API_KEY` |
| Ollama   | Local at `http://localhost:11434` |

## Architecture

```
src/kidscan/
  cli.py             — orchestrator (full interactive workflow)
  vendors.py         — vendor discovery and model listing
  scanner.py         — AI analysis of subtitles
  subtitle.py        — SRT and ASS subtitle parser
  ffmpeg.py          — ffmpeg binary check, track probing, scene cutting
  editor.py          — auto and manual edit modes
  models.py          — data classes
  ui.py              — spinner helper
  templates/
    review_prompt.md — AI prompt (editable)
```

## About

KidCut is an open-source project, licensed under Apache 2.0.