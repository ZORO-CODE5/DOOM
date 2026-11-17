import re
from typing import Any, List, Dict

class TokenContextManager:
    def __init__(self, max_context_tokens: int = 4096, reserve_tokens: int = 1024):
        self.max_context_tokens = max_context_tokens
        self.reserve_tokens = reserve_tokens
        self.usable_limit = max_context_tokens - reserve_tokens

    def estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        words = len(re.findall(r"\w+|[^\w\s]", text))
        return int(words * 1.3)

    def count_messages_tokens(self, messages: List[Dict[str, Any]]) -> int:
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += self.estimate_tokens(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and "text" in part:
                        total += self.estimate_tokens(part["text"])
            total += 4
        return total

    def get_usage_stats(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        used = self.count_messages_tokens(messages)
        pct = min(100.0, (used / self.max_context_tokens) * 100)
        return {
            "used": used,
            "max": self.max_context_tokens,
            "percent": round(pct, 1),
            "remaining": max(0, self.max_context_tokens - used)
        }

    def compact_history(
        self,
        messages: List[Dict[str, Any]],
        ollama_client: Any
    ) -> List[Dict[str, Any]]:
        current_tokens = self.count_messages_tokens(messages)
        if current_tokens <= self.usable_limit:
            return messages

        system_messages = [m for m in messages if m.get("role") == "system"]
        conversation = [m for m in messages if m.get("role") != "system"]

        if len(conversation) <= 4:
            return messages

        keep_recent = 4
        to_summarize = conversation[:-keep_recent]
        to_keep = conversation[-keep_recent:]

        transcript_parts = []
        for msg in to_summarize:
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")
            transcript_parts.append(f"{role}: {content[:300]}")
        transcript = "\n".join(transcript_parts)

        summary_prompt = [
            {
                "role": "system",
                "content": "You are a concise summarizer. Extract key facts, decisions, file paths, and instructions."
            },
            {
                "role": "user",
                "content": f"Summarize the essence of this conversation concisely in bullet points:\n\n{transcript}"
            }
        ]

        try:
            summary_text = ollama_client.chat(summary_prompt)
            if hasattr(summary_text, "message"):
                summary_content = getattr(summary_text.message, "content", "")
            elif isinstance(summary_text, dict):
                summary_content = summary_text.get("message", {}).get("content", "")
            else:
                summary_content = str(summary_text)
        except Exception:
            summary_content = "Previous conversation compacted to preserve memory."

        compacted = list(system_messages)
        compacted.append({
            "role": "system",
            "content": f"[LATVERIAN ARCHIVE SUMMARY OF PRIOR TURNS]:\n{summary_content}"
        })
        compacted.extend(to_keep)
        return compacted