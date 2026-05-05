"""
LLM Provider implementations — OpenAI-compatible, Anthropic, Gemini.
Each provider exposes a unified interface: chat(messages, **kwargs) -> str
"""

import logging

logger = logging.getLogger(__name__)


class BaseProvider:
    """Abstract base for all LLM providers."""

    def __init__(self, config: dict):
        self.url = config.get("url", "")
        self.apikey = config.get("apikey", "")
        self.model = config.get("model", "")

    def chat(self, messages: list[dict], **kwargs) -> str:
        raise NotImplementedError


class OpenAIProvider(BaseProvider):
    """OpenAI / OpenAI-compatible (DeepSeek, Ollama, vLLM, Zhipu, Qwen, etc.)."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI
            kwargs = {"api_key": self.apikey}
            if self.url:
                kwargs["base_url"] = self.url.rstrip("/")
            self._client = OpenAI(**kwargs)
        return self._client

    def chat(self, messages: list[dict], **kwargs) -> str:
        max_tokens = kwargs.pop("max_tokens", 4096)
        temperature = kwargs.pop("temperature", 0.7)
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )
        return resp.choices[0].message.content or ""


class AnthropicProvider(BaseProvider):
    """Anthropic Claude provider."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import anthropic
            kwargs = {"api_key": self.apikey}
            if self.url:
                kwargs["base_url"] = self.url.rstrip("/")
            self._client = anthropic.Anthropic(**kwargs)
        return self._client

    def chat(self, messages: list[dict], **kwargs) -> str:
        system_msg = ""
        chat_messages = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                chat_messages.append(m)

        max_tokens = kwargs.pop("max_tokens", 4096)
        temperature = kwargs.pop("temperature", 0.7)
        resp = self.client.messages.create(
            model=self.model,
            system=system_msg if system_msg else anthropic.NOT_GIVEN,
            messages=chat_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )
        if resp.content and len(resp.content) > 0:
            return resp.content[0].text
        return ""


class GeminiProvider(BaseProvider):
    """Google Gemini provider."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import google.generativeai as genai
            genai.configure(api_key=self.apikey)
            self._client = genai
        return self._client

    def chat(self, messages: list[dict], **kwargs) -> str:
        generation_config = {
            "max_output_tokens": kwargs.pop("max_tokens", 4096),
            "temperature": kwargs.pop("temperature", 0.7),
        }
        model = self.client.GenerativeModel(
            model_name=self.model,
            generation_config=generation_config,
        )
        chat = model.start_chat(history=[])
        # Gemini uses a flat message format
        parts = []
        for m in messages:
            parts.append({"role": "user" if m["role"] != "assistant" else "model",
                          "parts": [m["content"]]})
        # Send last user message and get response
        last_msg = messages[-1]["content"]
        history = parts[:-1] if len(parts) > 1 else []
        resp = model.generate_content(
            contents=last_msg,
            generation_config=generation_config,
        )
        return resp.text or ""
