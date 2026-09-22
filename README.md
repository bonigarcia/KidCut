# KidCut ![](https://bonigarcia.dev/img/kidcut.png)

AI-powered CLI tool that detects and removes adult scenes from MKV movies, creating kid-friendly versions. Uses AI models to analyze subtitles and [ffmpeg](https://ffmpeg.org/) to trim inappropriate scenes (adult content).


## Quickstart

KidCut is a Python CLI tool run as:

```bash
python -m kidcut
```

### Interactive workflow

1. **Select MKV** — browse the filesystem to pick your movie file
2. **Track detection** — auto-detects subtitle track matching the default audio language (or lets you pick manually)
3. **Subtitle extraction** — extracts and parses SRT/ASS text subtitles
4. **Choose AI provider** — supports OpenAI, Anthropic, Google, OpenRouter, and Ollama (when running locally)
5. **AI analysis** — model flags individual subtitle entries with inappropriate language
6. **Edit mode** — choose *Automatic* (cut all flagged entries) or *Manual* (review each one by one)
7. **Output** — ffmpeg re-encodes the video to produce `input-kidcut.mkv` with flagged frames removed (frame-accurate cuts)

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

KidCut (Copyright &copy; 2026) is an open-source project created and maintained by [Boni Garcia](https://bonigarcia.dev/), licensed under the terms of [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0).