"""Ollama API client with streaming and tool calling support."""

from typing import Any, Generator
import ollama


class OllamaClient:
    """Manages chat completion, streaming, and tool execution with Ollama."""

    def __init__(self, model_name: str = "qwen2.5-coder:3b"):
        self.model_name = model_name

    def get_installed_models(self) -> list[str]:
        """Queries the local ollama server for all downloaded model tags."""
        try:
            response = ollama.list()
            models = response.get("models", [])
            names = []
            for m in models:
                if isinstance(m, dict):
                    names.append(m.get("name") or m.get("model", ""))
                elif hasattr(m, "model"):
                    names.append(m.model)
            return [n for n in names if n]
        except Exception:
            return []

    def stream_chat(self, messages: list[dict[str, Any]]) -> Generator[str, None, None]:
        """Streams plain chat responses from the model."""
        try:
            stream = ollama.chat(
                model=self.model_name,
                messages=messages,
                stream=True,
            )
            for chunk in stream:
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content
        except Exception as e:
            yield f"\n[Error communicating with Ollama: {e}]"

    def chat_with_tools(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Performs a non-streaming chat turn that can return tool calls."""
        try:
            return ollama.chat(
                model=self.model_name,
                messages=messages,
                tools=tools,
                stream=False,
            )
        except Exception as e:
            return {"message": {"role": "assistant", "content": f"Ollama error: {e}"}}