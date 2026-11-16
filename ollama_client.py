"""Ollama communication layer for DOOM."""

from typing import Generator
import ollama


class OllamaClient:

    def __init__(self, model_name: str = "qwen2.5-coder:3b"):
        self.model_name = model_name

    def get_installed_models(self) -> list[str]:
        """Queries the local Ollama server for all downloaded model tags."""
        try:
            response = ollama.list()
            return [m.model for m in response.models]
        except Exception:
            return []

    def verify_connection(self) -> tuple[bool, str]:
        """Checks if the local Ollama server is running and the active model exists."""
        try:
            available_models = self.get_installed_models()
            model_installed = any(
                self.model_name in name for name in available_models
            )
            if not model_installed:
                return (
                    False,
                    f"Model '{self.model_name}' is not downloaded. Run 'ollama pull {self.model_name}'.",
                )
            return True, "Connected successfully."

        except Exception as e:
            return (
                False,
                f"Cannot reach Ollama service. Is Ollama running? (Details: {e})",
            )

    def switch_model(self, new_model_name: str) -> tuple[bool, str]:
        """Switches the active model to another locally installed Ollama model."""
        clean_name = new_model_name.strip()
        available_models = self.get_installed_models()

        # Check if the requested model matches any local model tag
        matched = next((m for m in available_models if clean_name == m or clean_name in m), None)
        if not matched:
            return False, f"Model '{clean_name}' is not installed locally. Run 'ollama pull {clean_name}' first."

        self.model_name = matched
        return True, matched

    def stream_chat(
        self, messages: list[dict[str, str]]
    ) -> Generator[str, None, None]:
        """Sends conversation history to Ollama and yields response tokens in real time."""
        stream = ollama.chat(
            model=self.model_name,
            messages=messages,
            stream=True,
        )
        for chunk in stream:
            yield chunk["message"]["content"]