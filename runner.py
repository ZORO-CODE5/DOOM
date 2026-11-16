"""Safe subprocess execution engine for DOOM."""

import subprocess
import time
from pathlib import Path


class CommandRunner:
    """Executes local terminal commands safely with approval checks and output capture."""

    # Block destructive or system-altering commands
    BLOCKED_PATTERNS = [
        "format",
        "rmdir /s",
        "del /s",
        "del /f",
        "rd /s",
        "shutdown",
        "restart-computer",
        "drop database",
        ":(){ :|:& };:",
    ]

    def __init__(self, working_dir: Path | None = None):
        self.working_dir = working_dir if working_dir else Path.cwd()

    def is_safe(self, command: str) -> tuple[bool, str]:
        """Checks if a command contains known destructive patterns."""
        normalized = command.strip().lower()

        for pattern in self.BLOCKED_PATTERNS:
            if pattern in normalized:
                return (
                    False,
                    f"Blocked command: contains potentially destructive pattern '{pattern}'.",
                )

        return True, "Command allowed."

    def execute(self, command: str, timeout: int = 60) -> dict[str, str | int]:
        """Executes a command via PowerShell inside the workspace directory.

        Returns a dictionary with returncode, stdout, stderr, and elapsed_time.
        """
        start_time = time.time()

        try:
            # Execute command using powershell.exe in the workspace folder
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", command],
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            elapsed = time.time() - start_time

            return {
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "elapsed": round(elapsed, 2),
                "timeout": False,
            }

        except subprocess.TimeoutExpired:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": f"Execution timed out after {timeout} seconds.",
                "elapsed": round(time.time() - start_time, 2),
                "timeout": True,
            }
        except Exception as e:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": f"Execution error: {e}",
                "elapsed": round(time.time() - start_time, 2),
                "timeout": False,
            }