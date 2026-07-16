"""
Model providers. Every provider exposes one method: chat(messages) -> str.
`messages` is a plain list of {"role": "system"|"user"|"assistant", "content": str}.

This is deliberately the smallest possible interface. The comparison harness
doesn't care HOW a model produces text, only that every provider looks the
same from the outside -- that's what makes swapping Claude for a local
Ollama model a one-line change instead of a rewrite.
"""

import json
from abc import ABC, abstractmethod


class ModelProvider(ABC):
    name: str

    @abstractmethod
    def chat(self, messages: list[dict]) -> str:
        ...


class ClaudeProvider(ModelProvider):
    def __init__(self, model: str = "claude-sonnet-4-6"):
        import anthropic
        self.client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
        self.model = model
        self.name = f"claude:{model}"

    def chat(self, messages: list[dict]) -> str:
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        convo = [m for m in messages if m["role"] != "system"]
        resp = self.client.messages.create(
            model=self.model, max_tokens=1000, system=system, messages=convo,
        )
        return resp.content[0].text


class GeminiProvider(ModelProvider):
    """Google's Gemini API -- genuinely free tier, no credit card required.
    Get a key at aistudio.google.com. Rate-limited but plenty for this harness."""

    def __init__(self, model: str = "gemini-3-flash"):
        from google import genai
        import os
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        self.model = model
        self.name = f"gemini:{model}"

    def chat(self, messages: list[dict]) -> str:
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        # Gemini uses "model" instead of "assistant" as the role name
        contents = [
            {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
            for m in messages if m["role"] != "system"
        ]
        resp = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config={"system_instruction": system, "max_output_tokens": 1000},
        )
        return resp.text


class OllamaProvider(ModelProvider):
    """Talks to a locally running `ollama serve` (default port 11434).
    Run `ollama pull <model>` once before using this."""

    def __init__(self, model: str = "llama3.1", host: str = "http://localhost:11434"):
        self.model = model
        self.host = host
        self.name = f"ollama:{model}"

    def chat(self, messages: list[dict]) -> str:
        import requests
        resp = requests.post(
            f"{self.host}/api/chat",
            json={"model": self.model, "messages": messages, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]


class MockProvider(ModelProvider):
    """No model at all -- a scripted stand-in so we can test that the AGENT
    LOOP itself works (JSON parsing, tool execution, step limits) before
    spending any real inference time. Never used for the actual comparison."""

    def __init__(self):
        self.name = "mock"
        self._step = 0

    def chat(self, messages: list[dict]) -> str:
        self._step += 1
        if self._step == 1:
            return json.dumps({
                "thought": "I should check available options before deciding.",
                "action": "call_tool",
                "tool": "get_options",
                "args": {}
            })
        return json.dumps({
            "thought": "I have enough information to decide.",
            "action": "final_decision",
            "decision": "Selected the first available option based on mock logic."
        })


def get_provider(kind: str, **kwargs) -> ModelProvider:
    if kind == "claude":
        return ClaudeProvider(**kwargs)
    if kind == "gemini":
        return GeminiProvider(**kwargs)
    if kind == "ollama":
        return OllamaProvider(**kwargs)
    if kind == "mock":
        return MockProvider()
    raise ValueError(f"Unknown provider kind: {kind}")
