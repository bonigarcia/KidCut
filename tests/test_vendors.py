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