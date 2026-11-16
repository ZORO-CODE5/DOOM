"""Context management and workspace file operations for DOOM."""

from pathlib import Path
import re


class ProjectContext:
    """Scans, reads, safely writes, and searches files in the workspace."""

    IGNORED_DIRS = {
        ".venv",
        "venv",
        ".git",
        ".doom",
        "__pycache__",
        ".idea",
        ".vscode",
        "node_modules",
        "dist",
        "build",
    }
    IGNORED_EXTENSIONS = {
        ".pyc",
        ".pyo",
        ".pyd",
        ".png",
        ".jpg",
        ".jpeg",
        ".ico",
    }

    def __init__(self, root_path: str | Path | None = None):
        self.root_path = Path(root_path).resolve() if root_path else Path.cwd()

    def get_project_files(self) -> list[Path]:
        """Returns a list of all relevant project files relative to the project root."""
        project_files = []

        for path in self.root_path.rglob("*"):
            if path.is_dir():
                continue

            if any(part in self.IGNORED_DIRS for part in path.parts):
                continue

            if path.suffix in self.IGNORED_EXTENSIONS:
                continue

            relative_path = path.relative_to(self.root_path)
            project_files.append(relative_path)

        return sorted(project_files)

    def file_exists(self, relative_path_str: str) -> bool:
        """Checks if a file already exists in the project workspace."""
        target_path = (self.root_path / relative_path_str).resolve()
        return target_path.exists() and target_path.is_file()

    def read_file(self, relative_path_str: str) -> tuple[bool, str]:
        """Safely reads the contents of a file within the project directory."""
        try:
            target_path = (self.root_path / relative_path_str).resolve()

            if not target_path.is_relative_to(self.root_path):
                return (
                    False,
                    f"Access denied: '{relative_path_str}' is outside the workspace.",
                )

            if not target_path.exists():
                return False, f"File not found: '{relative_path_str}'"

            if target_path.is_dir():
                return False, f"'{relative_path_str}' is a directory, not a file."

            content = target_path.read_text(encoding="utf-8")
            return True, content

        except UnicodeDecodeError:
            return (
                False,
                f"Cannot read '{relative_path_str}': binary/non-text file.",
            )
        except Exception as e:
            return False, f"Error reading '{relative_path_str}': {e}"

    def write_file(
        self, relative_path_str: str, content: str
    ) -> tuple[bool, str]:
        """Safely writes or updates a file inside the project workspace."""
        try:
            target_path = (self.root_path / relative_path_str).resolve()

            if not target_path.is_relative_to(self.root_path):
                return (
                    False,
                    f"Access denied: '{relative_path_str}' is outside the workspace.",
                )

            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")
            return True, f"Successfully saved to '{relative_path_str}'."

        except Exception as e:
            return False, f"Error writing '{relative_path_str}': {e}"

    def search_codebase(
        self, query: str, max_matches_per_file: int = 5
    ) -> list[dict[str, str | int]]:
        """Searches tracked project files for keywords or regex patterns.

        Returns a list of match entries: {'file': ..., 'line': ..., 'snippet': ...}
        """
        results = []
        files = self.get_project_files()

        # Compile search pattern (case-insensitive)
        try:
            pattern = re.compile(re.escape(query), re.IGNORECASE)
        except Exception:
            return results

        for rel_path in files:
            full_path = self.root_path / rel_path
            try:
                lines = full_path.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue

            matches_in_file = 0
            for idx, line in enumerate(lines, start=1):
                if pattern.search(line):
                    results.append({
                        "file": str(rel_path).replace("\\", "/"),
                        "line": idx,
                        "snippet": line.strip(),
                    })
                    matches_in_file += 1
                    if matches_in_file >= max_matches_per_file:
                        break

        return results