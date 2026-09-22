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

        if vendor_name == "OpenRouter":
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "HTTP-Referer": "https://github.com/bonigarcia/kidcut"},
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
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "safetySettings": [
                      {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                      {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                      {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                      {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                  ]},
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        usage = payload.get("usageMetadata", {})
        candidates = payload.get("candidates")
        if not candidates:
            raise RuntimeError(f"Google API response missing 'candidates': {payload}")
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        if not parts:
            raise RuntimeError(f"Google API response missing parts: {payload}")
        return parts[0].get("text", ""), usage.get("promptTokenCount"), usage.get("candidatesTokenCount")

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