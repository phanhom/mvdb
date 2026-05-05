"""
LLM Adapter — auto-detects provider type and creates the right client.
"""

import logging
import json
from pathlib import Path
from typing import Optional

from .providers import BaseProvider, OpenAIProvider, AnthropicProvider, GeminiProvider

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent.parent / "config.json"

_singleton: Optional[BaseProvider] = None


def _detect_provider(url: str, model: str) -> str:
    """
    Auto-detect provider based on url and model name.
    Returns one of: openai, deepseek, ollama, anthropic, gemini.
    """
    combined = (url + model).lower()

    if "deepseek" in combined:
        return "deepseek"
    if "open.bigmodel.cn" in combined or "zhipu" in combined or "glm" in model.lower():
        return "openai"  # Zhipu uses OpenAI-compatible API
    if "localhost" in combined or "127.0.0.1" in combined or ":11434" in combined:
        return "ollama"
    if "anthropic" in combined:
        return "anthropic"
    if "googleapis" in combined or "generativelanguage" in combined or "gemini" in model.lower():
        return "gemini"
    if "moonshot" in combined or "kimi" in model.lower():
        return "openai"
    if "qwen" in combined or "dashscope" in combined:
        return "openai"
    if "siliconflow" in combined:
        return "openai"
    if "together" in combined:
        return "openai"
    if "groq" in combined:
        return "openai"
    if "x.ai" in combined or "grok" in model.lower():
        return "openai"
    if "ollama" in combined:
        return "ollama"

    return "openai"


def load_config() -> dict:
    """Load and return the config."""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"config.json not found at {CONFIG_PATH}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_llm(config: Optional[dict] = None) -> BaseProvider:
    """
    Get or create the LLM provider singleton.
    Auto-detects provider type from config.
    """
    global _singleton

    if _singleton is not None:
        return _singleton

    if config is None:
        config = load_config()

    llm_config = config.get("llm", {})
    url = llm_config.get("url", "")
    model = llm_config.get("model", "gpt-4o")

    provider_type = _detect_provider(url, model)
    logger.info(f"Detected LLM provider: {provider_type} (model={model})")

    if provider_type == "anthropic":
        _singleton = AnthropicProvider(llm_config)
    elif provider_type == "gemini":
        _singleton = GeminiProvider(llm_config)
    else:
        # openai, deepseek, ollama, zhipu, moonshot, etc — all OpenAI-compatible
        _singleton = OpenAIProvider(llm_config)

    return _singleton


def reset_llm():
    """Reset the singleton (for testing or config reload)."""
    global _singleton
    _singleton = None


def chat(messages: list[dict], **kwargs) -> str:
    """Convenience: send messages to the LLM, return response text."""
    llm = get_llm()
    return llm.chat(messages, **kwargs)
