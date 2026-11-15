"""Session persistence and local state storage for NEXUS using Pydantic."""

from datetime import datetime
import json
from pathlib import Path
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Schema for individual conversation turns."""

    role: str
    content: str


class SessionData(BaseModel):
    """Schema for a saved NEXUS session."""

    session_name: str
    created_at: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    model: str
    messages: list[ChatMessage]


class SessionStorage:
    """Manages reading and writing saved session files in .nexus/sessions/."""

    def __init__(self, workspace_root: Path):
        self.sessions_dir = workspace_root / ".nexus" / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def save_session(
        self,
        name: str,
        model_name: str,
        history: list[dict[str, str]],
    ) -> tuple[bool, str]:
        """Serializes active conversation history to a JSON file."""
        try:
            # Sanitize session name
            clean_name = "".join(
                c for c in name if c.isalnum() or c in ("-", "_")
            ).strip()
            if not clean_name:
                return False, "Invalid session name. Use letters, numbers, hyphens, or underscores."

            session_file = self.sessions_dir / f"{clean_name}.json"

            pydantic_messages = [
                ChatMessage(role=msg["role"], content=msg["content"])
                for msg in history
            ]

            session = SessionData(
                session_name=clean_name,
                model=model_name,
                messages=pydantic_messages,
            )

            session_file.write_text(
                session.model_dump_json(indent=2), encoding="utf-8"
            )
            return True, f"Session saved to '.nexus/sessions/{clean_name}.json'."

        except Exception as e:
            return False, f"Failed to save session: {e}"

    def load_session(
        self, name: str
    ) -> tuple[bool, list[dict[str, str]] | str]:
        """Loads a session from JSON and returns the messages list."""
        try:
            clean_name = name.strip()
            session_file = self.sessions_dir / f"{clean_name}.json"

            if not session_file.exists():
                return False, f"Session '{clean_name}' does not exist."

            data = json.loads(session_file.read_text(encoding="utf-8"))
            session = SessionData(**data)

            # Convert back to standard dictionaries for Ollama
            restored_messages = [
                {"role": m.role, "content": m.content} for m in session.messages
            ]
            return True, restored_messages

        except Exception as e:
            return False, f"Failed to load session: {e}"

    def list_sessions(self) -> list[dict[str, str]]:
        """Returns metadata for all saved sessions."""
        sessions = []
        for file in sorted(
            self.sessions_dir.glob("*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        ):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                sessions.append({
                    "name": file.stem,
                    "date": data.get("created_at", "Unknown"),
                    "turns": str(len(data.get("messages", []))),
                })
            except Exception:
                continue
        return sessions