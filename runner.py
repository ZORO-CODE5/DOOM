"""Safe subprocess execution engine for DOOM."""

import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any


class CommandResult(dict):
    """Dictionary that also supports attribute-style dot access (.stdout, .stderr, etc.)."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"'CommandResult' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class CommandRunner:
    """Executes local terminal commands safely with approval checks and output capture."""

    # Block destructive or system-altering commands
    BLOCKED_PATTERNS = [
        r"\bformat\s+[a-zA-Z]:",  # Formatting disk drives (e.g., format c:)
        r"\brmdir\s+/[sS]",
        r"\bdel\s+/[sS]",
        r"\bdel\s+/[fF]",
        r"\brd\s+/[sS]",
        r"\bshutdown\b",
        r"\brestart-computer\b",
        r"\bdrop\s+database\b",
        r":\(\)\{\s*:\|:&\s*\};:",  # Fork bomb
    ]

    def __init__(self, working_dir: Path | None = None):
        self.working_dir = Path(working_dir).resolve() if working_dir else Path.cwd()

    def is_safe(self, command: str) -> tuple[bool, str]:
        """Checks if a command contains known destructive patterns."""
        normalized = command.strip().lower()

        for pattern in self.BLOCKED_PATTERNS:
            if re.search(pattern, normalized, re.IGNORECASE):
                return (
                    False,
                    f"Blocked command: matches destructive pattern '{pattern}'.",
                )

        return True, "Command allowed."

    def execute(self, command: str, timeout: int = 60) -> CommandResult:
        """Executes a command via PowerShell inside the workspace directory.

        Returns a CommandResult supporting both dict indexing and dot attributes.
        """
        start_time = time.time()
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"

        try:
            # Execute command using powershell.exe in the workspace folder
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", command],
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                encoding="utf-8",
                errors="replace",
            )
            elapsed = time.time() - start_time

            return CommandResult({
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "elapsed": round(elapsed, 2),
                "timeout": False,
            })

        except subprocess.TimeoutExpired:
            return CommandResult({
                "returncode": -1,
                "stdout": "",
                "stderr": f"Execution timed out after {timeout} seconds.",
                "elapsed": round(time.time() - start_time, 2),
                "timeout": True,
            })
        except Exception as e:
            return CommandResult({
                "returncode": -1,
                "stdout": "",
                "stderr": f"Execution error: {e}",
                "elapsed": round(time.time() - start_time, 2),
                "timeout": False,
            })
