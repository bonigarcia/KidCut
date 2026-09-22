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
    if os.getenv("OPENROUTER_API_KEY"):
        vendors.append(VendorOption("OpenRouter", "OPENROUTER_API_KEY"))
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
        return sorted([item["id"] for item in response.json().get("data", [])])

    if vendor_name == "Anthropic":
        response = requests.get(
            "https://api.anthropic.com/v1/models",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            timeout=10,
        )
        response.raise_for_status()
        return sorted([item["id"] for item in response.json().get("data", [])])

    if vendor_name == "Google":
        response = requests.get(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
            timeout=10,
        )
        response.raise_for_status()
        return sorted([item["name"].split("/")[-1] for item in response.json().get("models", [])])

    if vendor_name == "OpenRouter":
        response = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        response.raise_for_status()
        return sorted([item["id"] for item in response.json().get("data", [])])

    response = requests.get("http://localhost:11434/api/tags", timeout=10)
    response.raise_for_status()
    return sorted([item["name"] for item in response.json().get("models", [])])