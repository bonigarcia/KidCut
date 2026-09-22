from kidscan.vendors import discover_vendors, list_models_for_vendor


def test_discover_vendors_includes_only_available_backends(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "google-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.setattr("kidscan.vendors.ollama_is_available", lambda: True)

    vendors = discover_vendors()

    assert [vendor.name for vendor in vendors] == ["OpenAI", "Google", "OpenRouter", "Ollama"]


def test_list_models_for_vendor_reads_provider_api(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"id": "gpt-4o-mini"}, {"id": "gpt-4.1-mini"}]}

    monkeypatch.setattr("kidscan.vendors.requests.get", lambda *_args, **_kwargs: FakeResponse())

    models = list_models_for_vendor("OpenAI", api_key="openai-key")

    assert models == ["gpt-4.1-mini", "gpt-4o-mini"]


def test_list_models_for_openrouter(monkeypatch):
    urls_called: list[str] = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"id": "openai/gpt-4o"}, {"id": "anthropic/claude-3"}]}

    def fake_get(url, **kwargs):
        urls_called.append(url)
        return FakeResponse()

    monkeypatch.setattr("kidscan.vendors.requests.get", fake_get)

    models = list_models_for_vendor("OpenRouter", api_key="or-key")

    assert models == ["anthropic/claude-3", "openai/gpt-4o"]
    assert urls_called[0].startswith("https://openrouter.ai")


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