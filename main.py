"""DOOM: Autonomous Terminal-based AI Software Engineering CLI Agent.

Sovereign monarch of the terminal, powered by Ollama, Rich, and MCP.
"""

import argparse
import atexit
from dataclasses import dataclass
import json
import os
from pathlib import Path
import random
import re
import sys
import textwrap
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from context import ProjectContext
from context_manager import TokenContextManager
from mcp_client import MCPManager
from ollama_client import OllamaClient
from prompts import (
    SUBAGENT_ROLES,
    get_fix_message,
    get_initial_messages,
    get_planning_message,
    get_research_message,
    get_review_message,
)
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from runner import CommandRunner
from snapshots import SnapshotManager
from storage import SessionStorage

# Ensure UTF-8 output encoding on Windows consoles
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

console = Console(legacy_windows=False)

DOOM_EASTER_EGG_SPEECH = (
    "I am DOOM. All code bends to my will, and all logic answers to my decree."
    " Tremble, mortal, and speak quickly—my time is far too sovereign to"
    " waste."
)

WINDOW_COLORS = {
    "latveria": {"bg": "#0a1f11", "fg": "#e2e8f0"},
    "monarch": {"bg": "#1c1708", "fg": "#fef08a"},
    "titanium": {"bg": "#0f172a", "fg": "#f8fafc"},
    "arcane": {"bg": "#1b0b24", "fg": "#f5d0fe"},
    "crimson": {"bg": "#200909", "fg": "#fed7aa"},
}

DOOM_PALETTES = {
    "latveria": {
        "primary": "bold green",
        "dim": "dim green",
        "accent": "bold yellow",
        "metal": "bold white",
        "status_core": "bold cyan",
        "status_role": "bold yellow",
        "prompt": "bold green",
    },
    "monarch": {
        "primary": "bold yellow",
        "dim": "dim yellow",
        "accent": "bold green",
        "metal": "bold white",
        "status_core": "bold green",
        "status_role": "bold white",
        "prompt": "bold yellow",
    },
    "titanium": {
        "primary": "bold white",
        "dim": "dim white",
        "accent": "bold green",
        "metal": "bold bright_black",
        "status_core": "bold green",
        "status_role": "bold yellow",
        "prompt": "bold white",
    },
    "arcane": {
        "primary": "bold magenta",
        "dim": "dim magenta",
        "accent": "bold yellow",
        "metal": "bold cyan",
        "status_core": "bold cyan",
        "status_role": "bold magenta",
        "prompt": "bold magenta",
    },
    "crimson": {
        "primary": "bold red",
        "dim": "dim red",
        "accent": "bold yellow",
        "metal": "bold white",
        "status_core": "bold yellow",
        "status_role": "bold red",
        "prompt": "bold red",
    },
}


def set_terminal_window_color(name: str = "latveria") -> None:
    cfg = WINDOW_COLORS.get(name, WINDOW_COLORS["latveria"])
    bg = cfg["bg"]
    fg = cfg["fg"]
    sys.stdout.write(f"\033]11;{bg}\007\033]10;{fg}\007")
    sys.stdout.flush()


def reset_terminal_window_color() -> None:
    sys.stdout.write("\033]111\007\033]110\007")
    sys.stdout.flush()


atexit.register(reset_terminal_window_color)


def get_banner_text(palette: dict[str, str]) -> str:
    p = palette["primary"]
    a = palette["accent"]
    return f"""
  [{a}]⚜[/{a}]  [{p}]██████╗  ██████╗  ██████╗ ███╗   ███╗[/{p}]  [{a}]⚜[/{a}]
     [{p}]██╔══██╗██╔═══██╗██╔═══██╗████╗ ████║[/{p}]
     [{p}]██║  ██║██║   ██║██║   ██║██╔████╔██║[/{p}]      [{a}]ALL CODE BENDS TO DOOM[/{a}]
     [{p}]██║  ██║██║   ██║██║   ██║██║╚██╔╝██║[/{p}]
     [{p}]██████╔╝╚██████╔╝╚██████╔╝██║ ╚═╝ ██║[/{p}]
     [{p}]╚═════╝  ╚═════╝  ╚═════╝ ╚═╝     ╚═╝[/{p}]
"""


def print_banner(
    model_name: str,
    active_subagent: str,
    palette: dict[str, str],
    token_stats: dict[str, Any] | None = None,
) -> None:
    p = palette["primary"]
    d = palette["dim"]
    banner_raw = get_banner_text(palette)

    tokens_display = ""
    if token_stats:
        used = token_stats.get("used", 0)
        total = token_stats.get("max", 4096)
        pct = token_stats.get("percent", 0.0)
        color = "green" if pct < 60 else "yellow" if pct < 85 else "red"
        tokens_display = (
            f"   │   [{p}]CONTEXT:[/{p}] [{color}]{used}/{total} ({pct}%)[/{color}]"
        )

    header_content = (
        f"{banner_raw.strip()}\n"
        f"[{d}]──────────────────────────────────────────────────────────────────────[/{d}]\n"
        f"  [{p}]CORE:[/{p}]"
        f" [{palette['status_core']}]{model_name}[/{palette['status_core']}]  "
        " │   "
        f"[{p}]ROLE:[/{p}]"
        f" [{palette['status_role']}]{active_subagent.upper()}[/{palette['status_role']}]"
        f"{tokens_display}"
    )

    console.print(
        Panel(
            Align.center(Text.from_markup(header_content)),
            border_style=p,
            subtitle=(
                f"[{d}]Type /help for controls.[/{d}]"
            ),
            padding=(0, 2),
        )
    )


def display_help() -> None:
    table = Table(
        title="COMMAND PROTOCOLS",
        border_style="green",
        header_style="bold yellow",
        show_lines=True,
    )
    table.add_column("Command", style="bold green", no_wrap=True)
    table.add_column("Arguments", style="yellow")
    table.add_column("Description", style="white")

    commands = [
        ("/help", "", "Show this commands reference table"),
        ("/exit", "", "Exit the DOOM interactive session"),
        ("/clear", "", "Clear conversation history and terminal screen"),
        (
            "/context",
            "[compact]",
            "Inspect token context usage meter or force compact",
        ),
        ("/files", "", "List all tracked files in the workspace"),
        ("/read", "<path>", "Display file contents with syntax highlighting"),
        ("/add", "<path>", "Load a local file into the AI's active context"),
        (
            "/save",
            "<path>",
            "Manually save the last generated code block to a file",
        ),
        ("/undo", "<path>", "Revert a file to its previous backup snapshot"),
        ("/snapshots", "[path]", "List saved file snapshots and timestamps"),
        ("/run", "<cmd>", "Execute a shell command with safety confirmation"),
        ("/plan", "<task>", "Generate a structured implementation plan"),
        (
            "/review",
            "<path>",
            "Perform a 4-point code quality and security review",
        ),
        ("/fix", "<path>", "Analyze runtime errors and generate a corrected file"),
        ("/research", "<query>", "Search symbols across files and analyze usage"),
        ("/subagent", "list | set <role>", "Inspect or switch active persona"),
        (
            "/session",
            "save | load | list",
            "Persist or restore named chat sessions",
        ),
        ("/model", "list | set <name>", "List or switch active Ollama models"),
        (
            "/theme",
            "list | set <theme>",
            "Inspect or change syntax highlighting theme",
        ),
        (
            "/palette",
            "list | set <name>",
            "Switch terminal window and UI color themes live",
        ),
        (
            "/mcp",
            "list | call <tool> <args>",
            "Inspect connected MCP servers or invoke tools",
        ),
    ]

    for cmd, args, desc in commands:
        table.add_row(cmd, args, desc)

    console.print(table)


# ==============================================================================
# WORKSPACE CONTEXT AWARENESS
# ==============================================================================

def get_workspace_tree_summary(context: ProjectContext, max_files: int = 20) -> str:
    """Returns a formatted summary of up to max_files in the workspace."""
    try:
        get_files_fn = getattr(
            context,
            "get_project_files",
            getattr(context, "list_files", None),
        )
        files = get_files_fn() if get_files_fn else []
    except Exception:
        files = []

    if not files:
        return "[ACTIVE WORKSPACE: Empty (no tracked files)]"

    total = len(files)
    shown = files[:max_files]
    lines = ["[ACTIVE WORKSPACE FILE TREE]:"]
    for f in shown:
        lines.append(f"  ├── {str(f).replace(os.sep, '/')}")
    if total > max_files:
        lines.append(f"  └── ... and {total - max_files} more tracked files.")
    return "\n".join(lines)


def safe_read_file(context: ProjectContext, filepath: str) -> tuple[bool, str]:
    """Safely reads a file from ProjectContext handling both tuple and string returns."""
    try:
        res = context.read_file(filepath)
        if isinstance(res, tuple):
            return res
        if res is not None:
            return True, str(res)
        return False, f"File not found: '{filepath}'"
    except Exception as e:
        return False, f"Error reading file '{filepath}': {e}"


# ==============================================================================
# CODE SANITIZATION & DIRECTIVE STRIPPING
# ==============================================================================

def sanitize_code_content(raw_code: str) -> str:
    """Sanitizes code by stripping directives and applying global textwrap.dedent.

    1. Removes all inline/block directives: [EXECUTE: ...], [FILE: ...], ```execute: ...```
    2. Removes standalone directive lines.
    3. Globally dedents leading whitespace from markdown nested lists so Python
       scripts never throw IndentationError.
    4. Guarantees clean trailing newline.
    """
    if not raw_code:
        return ""

    # Strip inline bracket directives
    code = re.sub(r"\[EXECUTE:\s*.+?\]", "", raw_code, flags=re.IGNORECASE)
    code = re.sub(r"\[FILE:\s*.+?\]", "", code, flags=re.IGNORECASE)
    code = re.sub(r"```+(?:EXECUTE|execute):?.*?```+", "", code, flags=re.DOTALL)

    # Strip standalone directive lines (including when preceded by comments)
    clean_lines = []
    for line in code.splitlines():
        stripped = line.strip()
        if re.match(
            r"^(?:#|//|--|/\*|\*)?\s*\[?(?:EXECUTE|FILE):\s*.+?\]?\s*(\*/)?$",
            stripped,
            re.IGNORECASE,
        ):
            continue
        clean_lines.append(line)
    code = "\n".join(clean_lines)

    # Globally dedent leading markdown whitespace
    code = textwrap.dedent(code)

    return code.strip("\r\n") + "\n"


# ==============================================================================
# ROBUST MULTI-FILE SCAFFOLDING & PARSING
# ==============================================================================

@dataclass
class ParsedCodeBlock:
    index: int
    lang: str
    code: str
    preceding_text: str
    explicit_file: str | None = None


def extract_candidate_filenames(text: str) -> list[str]:
    """Extracts candidate filenames with recognizable extensions from arbitrary text."""
    pattern = (
        r"\b([a-zA-Z0-9_\-\.\/\\]+\."
        r"(?:html|css|js|ts|jsx|tsx|py|json|sh|bash|sql|md|yaml|yml|txt|toml|rs|go|cpp|c|h))\b"
    )
    candidates = []
    seen = set()
    for match in re.finditer(pattern, text, re.IGNORECASE):
        candidate = match.group(1).replace("\\", "/").strip().lstrip("./")
        # Filter obvious false positives
        lower_cand = candidate.lower()
        if (
            lower_cand.startswith("http")
            or lower_cand.startswith("/")
            or lower_cand in ("node.js", "v1.0", "v2.0", "0.0.0.0")
            or lower_cand.endswith(".tar.gz")
        ):
            continue
        if candidate not in seen:
            seen.add(candidate)
            candidates.append(candidate)
    return candidates


def infer_extension_from_lang_or_code(lang: str, code: str) -> str:
    """Infers the most appropriate file extension based on fence language or code heuristics."""
    lang = lang.lower().strip()
    lang_to_ext = {
        "python": ".py",
        "py": ".py",
        "javascript": ".js",
        "js": ".js",
        "typescript": ".ts",
        "ts": ".ts",
        "html": ".html",
        "css": ".css",
        "json": ".json",
        "sql": ".sql",
        "bash": ".sh",
        "sh": ".sh",
        "shell": ".sh",
        "markdown": ".md",
        "md": ".md",
        "yaml": ".yaml",
        "yml": ".yml",
        "toml": ".toml",
        "rust": ".rs",
        "go": ".go",
        "c": ".c",
        "cpp": ".cpp",
    }
    if lang in lang_to_ext:
        return lang_to_ext[lang]

    # Content-based heuristics
    code_lower = code.lower()
    if "<!doctype html" in code_lower or "<html" in code_lower:
        return ".html"
    if (
        "{" in code
        and "}" in code
        and any(prop in code_lower for prop in ("margin:", "padding:", "color:", "display:", "font-family:"))
    ):
        return ".css"
    if "def " in code or "import " in code or "if __name__ == '__main__':" in code:
        return ".py"
    if (
        "function " in code
        or "const " in code
        or "let " in code
        or "console.log" in code
        or "document." in code
    ):
        return ".js"
    if code.strip().startswith("{") and code.strip().endswith("}"):
        return ".json"

    return ".py"


def parse_all_file_blocks(
    response_text: str, user_task: str
) -> list[tuple[str, str]]:
    """Intelligently extracts all file paths and associated code blocks from model response.

    1. Identifies all code fences.
    2. Filters out terminal command execution snippets (e.g. bash blocks with pip/python).
    3. Resolves explicit [FILE: <path>] tags when present.
    4. Fallback parser: When tags are missing or partial, searches preceding text,
       user task prompt, and response body for file candidates.
    5. Maps blocks to distinct target files by extension/syntax heuristics.
    6. Guarantees EVERY code block is saved and never overwrites different files
       with the same code block.
    """
    fence_pattern = re.compile(r"```([a-zA-Z0-9_\-\+\.]*)\s*\n(.*?)```", re.DOTALL)
    raw_blocks: list[ParsedCodeBlock] = []
    last_end = 0

    for idx, match in enumerate(fence_pattern.finditer(response_text)):
        lang = match.group(1).lower().strip()
        code = match.group(2)
        start_pos = match.start()
        end_pos = match.end()
        preceding = response_text[last_end:start_pos]
        last_end = end_pos

        # Check if block is an execution directive block instead of a code file
        if lang in ("execute", "run") or re.match(r"^(?:execute|run):", lang):
            continue

        stripped_code = code.strip()
        # If it's a shell/bash block and purely terminal execution commands
        if lang in ("bash", "sh", "shell", "powershell", "cmd", "terminal", "console", ""):
            if stripped_code.startswith("EXECUTE:") or stripped_code.startswith("[EXECUTE:"):
                continue
            lines = stripped_code.splitlines()
            if len(lines) <= 2 and any(
                lines[0].startswith(p)
                for p in ("python ", "pytest ", "pip ", "npm ", "node ", "./", "uv ")
            ):
                continue

        # Check for explicit [FILE: <path>] in preceding text
        explicit_file = None
        tag_matches = list(
            re.finditer(
                r"\[FILE:\s*['\"`]?([^\s\]'\"`]+)['\"`]?\]",
                preceding,
                re.IGNORECASE,
            )
        )
        if tag_matches:
            explicit_file = tag_matches[-1].group(1).strip().replace("\\", "/").lstrip("./")

        raw_blocks.append(
            ParsedCodeBlock(
                index=idx,
                lang=lang,
                code=code,
                preceding_text=preceding,
                explicit_file=explicit_file,
            )
        )

    if not raw_blocks:
        return []

    # Candidates pool from user task and full response text
    prompt_candidates = extract_candidate_filenames(user_task)
    resp_candidates = extract_candidate_filenames(response_text)

    # Combined candidate pool preserving prompt priority
    all_candidates: list[str] = []
    for c in prompt_candidates + resp_candidates:
        if c not in all_candidates:
            all_candidates.append(c)

    assigned_files: set[str] = set()
    result_files: list[tuple[str, str]] = []

    # First pass: assign blocks with explicit tags
    for block in raw_blocks:
        if block.explicit_file:
            fname = block.explicit_file
            sanitized = sanitize_code_content(block.code)
            result_files.append((fname, sanitized))
            assigned_files.add(fname)

    # Second pass: assign untagged blocks using fallback parser
    unassigned_blocks = [b for b in raw_blocks if not b.explicit_file]

    for block in unassigned_blocks:
        target_name = None
        ext = infer_extension_from_lang_or_code(block.lang, block.code)

        # 1. Inspect preceding text for direct file mentions (e.g. `### app.js`, `File: styles.css`)
        preceding_cands = extract_candidate_filenames(block.preceding_text)
        for cand in preceding_cands:
            if cand not in assigned_files:
                target_name = cand
                break

        # 2. Check unused candidates from prompt/response matching extension
        if not target_name:
            for cand in all_candidates:
                if cand not in assigned_files:
                    if Path(cand).suffix.lower() == ext.lower():
                        target_name = cand
                        break

        # 3. Content heuristics for test vs implementation files
        if not target_name:
            code_lower = block.code.lower()
            is_test = (
                "def test_" in code_lower
                or "import unittest" in code_lower
                or "import pytest" in code_lower
                or "assert " in code_lower
            )
            for cand in all_candidates:
                if cand not in assigned_files:
                    cand_lower = cand.lower()
                    if is_test and ("test" in cand_lower):
                        target_name = cand
                        break
                    elif not is_test and ("test" not in cand_lower) and Path(cand).suffix.lower() == ext.lower():
                        target_name = cand
                        break

        # 4. Default fallback naming based on extension
        if not target_name:
            defaults = {
                ".html": "index.html",
                ".css": "style.css",
                ".js": "app.js",
                ".ts": "index.ts",
                ".py": "main.py",
                ".json": "data.json",
                ".sh": "run.sh",
            }
            base_default = defaults.get(ext, f"module{ext}")
            candidate_default = base_default

            counter = 1
            while candidate_default in assigned_files:
                counter += 1
                stem = Path(base_default).stem
                candidate_default = f"{stem}_{counter}{ext}"

            target_name = candidate_default

        # Prevent duplicate filenames for different blocks
        if target_name in assigned_files:
            stem = Path(target_name).stem
            counter = 1
            alt_name = f"{stem}_{counter}{ext}"
            while alt_name in assigned_files:
                counter += 1
                alt_name = f"{stem}_{counter}{ext}"
            target_name = alt_name

        sanitized = sanitize_code_content(block.code)
        result_files.append((target_name, sanitized))
        assigned_files.add(target_name)

    return result_files


def extract_fallback_filename(user_task: str, response_text: str) -> str | None:
    cands = extract_candidate_filenames(user_task) or extract_candidate_filenames(response_text)
    return cands[0] if cands else None


def extract_best_code_block(
    text: str, target_filename: str = ""
) -> str | None:
    files = parse_all_file_blocks(text, target_filename)
    if not files:
        return None

    if target_filename:
        norm_target = target_filename.replace("\\", "/").lower()
        for fname, code in files:
            if fname.lower() == norm_target or Path(fname).name.lower() == Path(norm_target).name.lower():
                return code

        # Match by extension
        target_ext = Path(target_filename).suffix.lower()
        for fname, code in files:
            if Path(fname).suffix.lower() == target_ext:
                return code

    return files[0][1]


def execute_file_writes(
    response_text: str,
    user_task: str,
    context: ProjectContext,
    snapshots: SnapshotManager,
    palette: dict[str, str],
) -> list[str]:
    """Extracts all code blocks and writes them safely to disk with snapshotting."""
    files_to_write = parse_all_file_blocks(response_text, user_task)
    written_files = []

    for filepath_str, code_content in files_to_write:
        filepath_str = filepath_str.strip()

        resolve_fn = getattr(
            context, "resolve_path", lambda p: context.root_path / p
        )
        target_path = resolve_fn(filepath_str)

        # Snapshot before modifying existing file
        if target_path.exists():
            try:
                snapshots.create_snapshot(filepath_str)
            except Exception:
                pass

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(code_content, encoding="utf-8")
        written_files.append(filepath_str)

        p = palette["primary"]
        a = palette["accent"]
        console.print(
            Panel(
                f"[{p}]Decree enacted. File written to disk:[/{p}] [bold"
                f" white]{filepath_str}[/bold white]",
                title=f"[{a}]⚜ FILE CREATED / UPDATED ⚜[/{a}]",
                border_style=p,
                padding=(0, 2),
            )
        )

    return written_files


# ==============================================================================
# FLEXIBLE DIRECTIVE PARSING
# ==============================================================================

def extract_execute_commands(response_text: str) -> list[str]:
    """Flexibly parses execution commands across standard, fenced, and plain line styles.

    Matches:
      - [EXECUTE: <cmd>]
      - ```EXECUTE: <cmd>``` or ```execute: <cmd>```
      - ```execute\n<cmd>\n```
      - Standalone lines: EXECUTE: <cmd>
    Deduplicates commands while strictly preserving chronological order.
    """
    commands: list[str] = []
    seen: set[str] = set()

    def add_command(raw_cmd: str) -> None:
        cmd = raw_cmd.strip()
        # Strip outer backticks or matching quotation marks
        if (cmd.startswith("`") and cmd.endswith("`")) or (
            cmd.startswith('"') and cmd.endswith('"')
        ):
            cmd = cmd[1:-1].strip()
        if cmd and cmd not in seen:
            seen.add(cmd)
            commands.append(cmd)

    # 1. Matches ```execute: <cmd>``` or ```EXECUTE: <cmd>```
    for cmd in re.findall(
        r"```+(?:execute|EXECUTE):?\s*([^\n`]+)```+", response_text
    ):
        add_command(cmd)

    # 2. Matches multiline ```execute\n<cmd>\n``` blocks
    for block in re.findall(
        r"```+(?:execute|EXECUTE)\s*\n(.*?)```+", response_text, re.DOTALL
    ):
        for line in block.strip().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                add_command(line)

    # 3. Matches standard square-bracket directive: [EXECUTE: <cmd>]
    for cmd in re.findall(
        r"\[EXECUTE:\s*([^\]\n]+)\]", response_text, re.IGNORECASE
    ):
        add_command(cmd)

    # 4. Matches plain text directive lines outside code fences
    text_without_fences = re.sub(r"```.*?```", "", response_text, flags=re.DOTALL)
    for cmd in re.findall(
        r"(?:^|\n)\s*(?:>\s*)?EXECUTE:\s*([^\n]+)",
        text_without_fences,
        re.IGNORECASE,
    ):
        add_command(cmd)

    return commands


# ==============================================================================
# AUTONOMOUS AGENT LOOP & SELF-CORRECTION
# ==============================================================================

def run_autonomous_loop(
    user_task: str,
    messages: list[dict[str, Any]],
    ollama_client: OllamaClient,
    runner: CommandRunner,
    context: ProjectContext,
    snapshots: SnapshotManager,
    token_mgr: TokenContextManager,
    palette: dict[str, str],
    max_turns: int = 5,
) -> str:
    """Executes the autonomous loop with dynamic file tree awareness and multi-turn self-repair."""
    # Prepend dynamic workspace context awareness
    tree_context = get_workspace_tree_summary(context, max_files=20)
    initial_user_prompt = f"{tree_context}\n\n[USER DECREE]:\n{user_task}"
    messages.append({"role": "user", "content": initial_user_prompt})

    last_response = ""
    turn = 0

    while turn < max_turns:
        turn += 1
        messages = token_mgr.compact_history(messages, ollama_client)

        p = palette["primary"]
        console.print(f"[{p}]DOOM (Agent Step {turn}/{max_turns}):[/{p}] ", end="")
        collected = []
        for chunk in ollama_client.stream_chat(messages):
            console.print(chunk, end="")
            collected.append(chunk)
        console.print()

        last_response = "".join(collected)
        messages.append({"role": "assistant", "content": last_response})

        # Enact file writes
        execute_file_writes(
            last_response, user_task, context, snapshots, palette
        )

        # Parse execution commands
        commands = extract_execute_commands(last_response)

        if not commands:
            # If no command directives were emitted, the task turn is concluded
            break

        has_error = False
        command_feedbacks = []

        for cmd in commands:
            is_safe, reason = runner.is_safe(cmd)
            if not is_safe:
                console.print(
                    f"[bold red]Command Blocked for safety:[/bold red] {reason}"
                )
                command_feedbacks.append(f"Command '{cmd}' was blocked: {reason}")
                has_error = True
                continue

            console.print(
                f"[dim yellow]Auto-executing decree:[/dim yellow] [bold"
                f" white]{cmd}[/bold white]"
            )
            result = runner.execute(cmd)

            # Support both dict and object with dot attributes
            stdout = str(
                result.get("stdout", "")
                if isinstance(result, dict)
                else getattr(result, "stdout", "")
            ).strip()
            stderr = str(
                result.get("stderr", "")
                if isinstance(result, dict)
                else getattr(result, "stderr", "")
            ).strip()
            returncode = int(
                result.get("returncode", 0)
                if isinstance(result, dict)
                else getattr(result, "returncode", 0)
            )

            if stdout:
                console.print(
                    Panel(stdout, title=f"Output: {cmd}", border_style=p)
                )
            if stderr:
                console.print(
                    Panel(stderr, title=f"Error: {cmd}", border_style="red")
                )

            # Failure occurs if returncode is non-zero or STDERR is non-empty
            cmd_failed = (returncode != 0) or bool(stderr)
            if cmd_failed:
                has_error = True

            command_feedbacks.append(
                f"Command `{cmd}` completed with exit code {returncode}.\n"
                f"STDOUT:\n{stdout if stdout else '[No stdout output]'}\n"
                f"STDERR / TRACEBACK:\n{stderr if stderr else '[No stderr output]'}"
            )

        if not has_error:
            console.print(
                f"[{palette['accent']}]⚜ Execution completed flawlessly. Sovereign decree enacted. ⚜[/{palette['accent']}]"
            )
            break

        if turn >= max_turns:
            console.print(
                f"[bold red]Max turns ({max_turns}) reached. Concluding self-correction loop.[/bold red]"
            )
            break

        # Trigger multi-turn self-correction loop
        updated_tree = get_workspace_tree_summary(context, max_files=20)
        repair_prompt = (
            f"{updated_tree}\n\n"
            "[LATVERIAN RUNTIME ALERT - CRITICAL EXECUTION FAILURE DETECTED]:\n"
            "The execution encountered an error / traceback. Analyze the failure and repair the code:\n\n"
            + "\n\n".join(command_feedbacks)
            + "\n\n"
            "AUTONOMOUS REPAIR PROTOCOLS:\n"
            "1. Diagnose the root cause directly from the traceback, exit code, and line numbers.\n"
            "2. Emit the complete corrected file(s) with [FILE: <path>]```<language> ... ```\n"
            "3. Issue [EXECUTE: <cmd>] to verify that the fix resolves the issue completely.\n"
            "4. NEVER use subprocess inside your Python scripts to execute themselves."
        )
        messages.append({"role": "user", "content": repair_prompt})

    return last_response


# ==============================================================================
# INTERACTIVE REPL DRIVER
# ==============================================================================

def main(palette_choice: str = "latveria") -> None:
    if palette_choice == "random":
        current_palette_name = random.choice(list(DOOM_PALETTES.keys()))
    elif palette_choice in DOOM_PALETTES:
        current_palette_name = palette_choice
    else:
        current_palette_name = "latveria"

    set_terminal_window_color(current_palette_name)
    palette = DOOM_PALETTES[current_palette_name]

    # Workspace root is dynamically initialized to current working directory
    workspace_root = Path.cwd().resolve()
    # Script origin directory for internal assets, storage, and MCP servers
    origin_dir = Path(__file__).resolve().parent

    context = ProjectContext(workspace_root)
    runner = CommandRunner(workspace_root)
    snapshots = SnapshotManager(workspace_root)
    storage = SessionStorage(origin_dir)
    ollama_client = OllamaClient()
    token_mgr = TokenContextManager(max_context_tokens=4096, reserve_tokens=1024)

    # Load MCP servers from repo origin, with fallback to workspace config if present
    mcp = MCPManager(origin_dir)
    mcp.load_servers()
    if workspace_root != origin_dir and (workspace_root / ".doom" / "mcp_servers.json").exists():
        ws_mcp = MCPManager(workspace_root)
        ws_mcp.load_servers()
        mcp.sessions.update(ws_mcp.sessions)

    current_theme = "monokai"
    active_subagent = "default"
    messages = get_initial_messages(active_subagent)
    last_assistant_response = ""

    console.clear()
    initial_stats = token_mgr.get_usage_stats(messages)
    print_banner(
        ollama_client.model_name, active_subagent, palette, initial_stats
    )

    while True:
        prompt_tag = palette["prompt"]
        try:
            user_input = Prompt.ask(
                f"\n[{prompt_tag}]doom[/{prompt_tag}][yellow]@[/yellow][{prompt_tag}]latveria[/{prompt_tag}]:[bold"
                f" white]~[/bold white][{prompt_tag}]#[/{prompt_tag}]"
            ).strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Doom withdraws. Session terminated.[/dim]")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            parts = user_input.split(maxsplit=3)
            cmd = parts[0].lower()
            arg1 = parts[1] if len(parts) > 1 else ""
            arg2 = parts[2] if len(parts) > 2 else ""
            arg3 = parts[3] if len(parts) > 3 else ""

            if cmd in ("/exit", "/quit"):
                console.print("[dim]Doom withdraws.[/dim]")
                break

            elif cmd == "/help":
                display_help()

            elif cmd == "/context":
                stats = token_mgr.get_usage_stats(messages)
                pct = stats.get("percent", 0.0)
                bar_len = 30
                filled = int(bar_len * (pct / 100))
                bar = "█" * filled + "░" * (bar_len - filled)
                bar_color = "green" if pct < 60 else "yellow" if pct < 85 else "red"

                if arg1 == "compact":
                    console.print(
                        f"[{palette['primary']}]Compacting conversational"
                        f" memory...[/{palette['primary']}]"
                    )
                    messages = token_mgr.compact_history(messages, ollama_client)
                    new_stats = token_mgr.get_usage_stats(messages)
                    console.print(
                        f"[green]Context compressed from {stats['used']} to"
                        f" {new_stats['used']} tokens.[/green]"
                    )
                else:
                    table = Table(
                        title="Latverian Context Status",
                        border_style=palette["primary"],
                        header_style="bold yellow",
                    )
                    table.add_column("Metric", style="bold yellow")
                    table.add_column("Value", style="white")
                    table.add_row("Used Tokens (est.)", str(stats.get("used", 0)))
                    table.add_row("Max Window", str(stats.get("max", 4096)))
                    table.add_row(
                        "Utilization", f"[{bar_color}]{bar}[/{bar_color}] {pct}%"
                    )
                    table.add_row("Remaining", str(stats.get("remaining", 0)))
                    table.add_row("Total Turns", str(len(messages)))
                    console.print(table)
                    console.print(
                        "[dim]Run `/context compact` to force memory compaction.[/dim]"
                    )

            elif cmd == "/palette":
                if arg1 == "list":
                    table = Table(
                        title="Latverian Palettes",
                        border_style=palette["primary"],
                        header_style="bold yellow",
                    )
                    table.add_column("Palette", style="bold yellow")
                    table.add_column("Terminal Window Style", style="white")
                    descriptions = {
                        "latveria": (
                            "Dark emerald-forest window background + Titanium silver text"
                            " (Default)"
                        ),
                        "monarch": (
                            "Dark obsidian-gold window background + Sovereign gold text"
                        ),
                        "titanium": "Deep graphite window background + Icy white text",
                        "arcane": (
                            "Dark arcane violet window background + Mystic violet text"
                        ),
                        "crimson": (
                            "Deep blood-iron window background + War gold text"
                        ),
                    }
                    for name, desc in descriptions.items():
                        table.add_row(name, desc)
                    console.print(table)
                elif arg1 == "set" and arg2:
                    if arg2 in DOOM_PALETTES:
                        current_palette_name = arg2
                        set_terminal_window_color(current_palette_name)
                        palette = DOOM_PALETTES[current_palette_name]
                        console.clear()
                        current_stats = token_mgr.get_usage_stats(messages)
                        print_banner(
                            ollama_client.model_name,
                            active_subagent,
                            palette,
                            current_stats,
                        )
                        console.print(
                            f"[{palette['primary']}]Terminal colors reconfigured to"
                            f" {current_palette_name.upper()}.[/{palette['primary']}]"
                        )
                    else:
                        console.print(
                            f"[red]Unknown palette: {arg2}. Use `/palette list`.[/red]"
                        )
                else:
                    console.print(f"[dim]Active palette: {current_palette_name}[/dim]")
                    console.print("[dim]Usage: /palette list | /palette set <name>[/dim]")

            elif cmd == "/clear":
                messages = get_initial_messages(active_subagent)
                last_assistant_response = ""
                console.clear()
                current_stats = token_mgr.get_usage_stats(messages)
                print_banner(
                    ollama_client.model_name, active_subagent, palette, current_stats
                )
                console.print(
                    f"[{palette['primary']}]Memory buffer purged. Screen"
                    f" wiped.[/{palette['primary']}]"
                )

            elif cmd == "/files":
                get_files_fn = getattr(
                    context,
                    "get_project_files",
                    getattr(context, "list_files", None),
                )
                files = get_files_fn() if get_files_fn else []
                if not files:
                    console.print("[yellow]No files found in workspace.[/yellow]")
                else:
                    table = Table(
                        title="Workspace Archives",
                        border_style=palette["primary"],
                        header_style="bold yellow",
                    )
                    table.add_column("File Path", style=palette["primary"])
                    for file_path in files:
                        table.add_row(str(file_path))
                    console.print(table)

            elif cmd == "/read":
                if not arg1:
                    console.print("[red]Usage: /read <filepath>[/red]")
                    continue
                ok, content = safe_read_file(context, arg1)
                if not ok:
                    console.print(f"[red]{content}[/red]")
                else:
                    syntax = Syntax(
                        content,
                        Path(arg1).suffix.lstrip(".") or "text",
                        theme=current_theme,
                        line_numbers=True,
                    )
                    console.print(
                        Panel(
                            syntax,
                            title=f"⚜ {arg1} ⚜",
                            border_style=palette["primary"],
                        )
                    )

            elif cmd == "/add":
                if not arg1:
                    console.print("[red]Usage: /add <filepath>[/red]")
                    continue
                ok, content = safe_read_file(context, arg1)
                if not ok:
                    console.print(f"[red]{content}[/red]")
                else:
                    messages.append({
                        "role": "user",
                        "content": (
                            f"Here is the content of `{arg1}`:\n\n```{Path(arg1).suffix.lstrip('.')}\n{content}\n```"
                        ),
                    })
                    console.print(f"[green]Added `{arg1}` to context.[/green]")

            elif cmd == "/save":
                if not arg1:
                    console.print("[red]Usage: /save <filepath>[/red]")
                    continue
                code = extract_best_code_block(last_assistant_response, arg1)
                if not code:
                    console.print(
                        "[red]No code block found in the last assistant response.[/red]"
                    )
                    continue

                resolve_fn = getattr(
                    context, "resolve_path", lambda p: context.root_path / p
                )
                target_path = resolve_fn(arg1)
                if target_path.exists():
                    try:
                        snapshots.create_snapshot(arg1)
                    except Exception:
                        pass
                    confirm = Confirm.ask(
                        f"[yellow]Overwrite existing file `{arg1}`?[/yellow]"
                    )
                    if not confirm:
                        console.print("[dim]Save canceled.[/dim]")
                        continue

                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(code, encoding="utf-8")
                console.print(
                    f"[{palette['primary']}]Saved code block to"
                    f" `{arg1}`.[/{palette['primary']}]"
                )

            elif cmd == "/undo":
                if not arg1:
                    console.print("[red]Usage: /undo <filepath>[/red]")
                    continue
                restore_fn = getattr(
                    snapshots,
                    "restore_latest_snapshot",
                    getattr(snapshots, "restore_latest", None),
                )
                if restore_fn:
                    res = restore_fn(arg1)
                    success = res[0] if isinstance(res, tuple) else bool(res)
                    if success:
                        console.print(
                            f"[green]Restored `{arg1}` from latest snapshot.[/green]"
                        )
                    else:
                        msg = res[1] if isinstance(res, tuple) else "Failed to restore snapshot"
                        console.print(f"[red]{msg}[/red]")
                else:
                    console.print("[red]Snapshot restoration engine unavailable.[/red]")

            elif cmd == "/snapshots":
                all_snapshots = snapshots.list_snapshots(arg1 if arg1 else "")
                if not all_snapshots:
                    console.print("[yellow]No snapshots found.[/yellow]")
                else:
                    table = Table(
                        title="Latverian Snapshots",
                        border_style=palette["primary"],
                        header_style="bold yellow",
                    )
                    table.add_column("Target File", style=palette["primary"])
                    table.add_column("Timestamp", style="yellow")
                    table.add_column("Backup Path", style="dim white")
                    for snap in all_snapshots:
                        orig = snap.get("original") or snap.get("target_file", "unknown")
                        ts = snap.get("timestamp", "unknown")
                        bp = snap.get("backup_path") or snap.get("backup_name", "")
                        table.add_row(orig, ts, bp)
                    console.print(table)

            elif cmd == "/run":
                command_str = user_input[4:].strip()
                if not command_str:
                    console.print("[red]Usage: /run <command>[/red]")
                    continue

                is_safe, reason = runner.is_safe(command_str)
                if not is_safe:
                    console.print(f"[bold red]Command Blocked:[/bold red] {reason}")
                    continue

                if not Confirm.ask(f"[yellow]Execute decree: `{command_str}`?[/yellow]"):
                    console.print("[dim]Command execution canceled.[/dim]")
                    continue

                result = runner.execute(command_str)
                stdout = str(
                    result.get("stdout", "")
                    if isinstance(result, dict)
                    else getattr(result, "stdout", "")
                ).strip()
                stderr = str(
                    result.get("stderr", "")
                    if isinstance(result, dict)
                    else getattr(result, "stderr", "")
                ).strip()
                returncode = int(
                    result.get("returncode", 0)
                    if isinstance(result, dict)
                    else getattr(result, "returncode", 0)
                )

                if stdout:
                    console.print(
                        Panel(
                            stdout,
                            title="stdout",
                            border_style=palette["primary"],
                        )
                    )
                if stderr:
                    console.print(Panel(stderr, title="stderr", border_style="red"))
                console.print(f"[dim]Exited with code {returncode}[/dim]")

            elif cmd == "/plan":
                task_description = user_input[5:].strip()
                if not task_description:
                    console.print("[red]Usage: /plan <task description>[/red]")
                    continue
                plan_prompt = get_planning_message(task_description)
                messages.append({"role": "user", "content": plan_prompt})
                console.print(f"[{palette['primary']}]Doom strategizes...[/{palette['primary']}]")
                response_stream = ollama_client.stream_chat(messages)
                collected = []
                for chunk in response_stream:
                    console.print(chunk, end="")
                    collected.append(chunk)
                console.print()
                last_assistant_response = "".join(collected)
                messages.append(
                    {"role": "assistant", "content": last_assistant_response}
                )

            elif cmd == "/review":
                if not arg1:
                    console.print("[red]Usage: /review <filepath>[/red]")
                    continue
                ok, content = safe_read_file(context, arg1)
                if not ok:
                    console.print(f"[red]{content}[/red]")
                    continue
                review_prompt = get_review_message(arg1, content)
                messages.append({"role": "user", "content": review_prompt})
                console.print(
                    f"[{palette['primary']}]Doom audits {arg1}...[/{palette['primary']}]"
                )
                response_stream = ollama_client.stream_chat(messages)
                collected = []
                for chunk in response_stream:
                    console.print(chunk, end="")
                    collected.append(chunk)
                console.print()
                last_assistant_response = "".join(collected)
                messages.append(
                    {"role": "assistant", "content": last_assistant_response}
                )

            elif cmd == "/fix":
                if not arg1:
                    console.print("[red]Usage: /fix <filepath>[/red]")
                    continue
                ok, content = safe_read_file(context, arg1)
                if not ok:
                    console.print(f"[red]{content}[/red]")
                    continue
                fix_prompt = get_fix_message(arg1, content, "")
                messages.append({"role": "user", "content": fix_prompt})
                console.print(
                    f"[{palette['primary']}]Doom repairs"
                    f" {arg1}...[/{palette['primary']}]"
                )
                response_stream = ollama_client.stream_chat(messages)
                collected = []
                for chunk in response_stream:
                    console.print(chunk, end="")
                    collected.append(chunk)
                console.print()
                last_assistant_response = "".join(collected)
                messages.append(
                    {"role": "assistant", "content": last_assistant_response}
                )

            elif cmd == "/research":
                query = user_input[9:].strip()
                if not query:
                    console.print("[red]Usage: /research <query>[/red]")
                    continue
                search_fn = getattr(context, "search_codebase", None)
                search_results = search_fn(query) if search_fn else []
                formatted_snippets = [
                    f"{r.get('file', '')}:{r.get('line', '')} {r.get('snippet', '')}"
                    for r in search_results
                ]
                research_prompt = get_research_message(query, formatted_snippets)
                messages.append({"role": "user", "content": research_prompt})
                console.print(
                    f"[{palette['primary']}]Doom investigates"
                    f" '{query}'...[/{palette['primary']}]"
                )
                response_stream = ollama_client.stream_chat(messages)
                collected = []
                for chunk in response_stream:
                    console.print(chunk, end="")
                    collected.append(chunk)
                console.print()
                last_assistant_response = "".join(collected)
                messages.append(
                    {"role": "assistant", "content": last_assistant_response}
                )

            elif cmd == "/subagent":
                if arg1 == "list":
                    table = Table(
                        title="Available Subagents",
                        border_style=palette["primary"],
                        header_style="bold yellow",
                    )
                    table.add_column("Role", style=palette["primary"])
                    table.add_column("Description", style="white")
                    for role, desc in SUBAGENT_ROLES.items():
                        table.add_row(role, desc)
                    console.print(table)
                elif arg1 == "set" and arg2:
                    if arg2 in SUBAGENT_ROLES:
                        active_subagent = arg2
                        messages = get_initial_messages(active_subagent)
                        console.print(
                            f"[{palette['primary']}]Switched subagent to"
                            f" [bold]{active_subagent}[/bold]. History"
                            f" reset.[/{palette['primary']}]"
                        )
                    else:
                        console.print(
                            f"[red]Unknown role: {arg2}. Use `/subagent list`.[/red]"
                        )
                else:
                    console.print(
                        "[red]Usage: /subagent list | /subagent set <role>[/red]"
                    )

            elif cmd == "/session":
                if arg1 == "save" and arg2:
                    ok, msg = storage.save_session(arg2, ollama_client.model_name, messages)
                    if ok:
                        console.print(f"[green]{msg}[/green]")
                    else:
                        console.print(f"[red]{msg}[/red]")
                elif arg1 == "load" and arg2:
                    res = storage.load_session(arg2)
                    ok = res[0] if isinstance(res, tuple) else bool(res)
                    loaded_messages = res[1] if isinstance(res, tuple) else (res.get("messages") if isinstance(res, dict) else [])
                    if ok and isinstance(loaded_messages, list):
                        messages = loaded_messages
                        console.print(
                            f"[green]Session `{arg2}` restored ({len(messages)}"
                            " messages).[/green]"
                        )
                    else:
                        err_msg = loaded_messages if isinstance(loaded_messages, str) else f"Could not load session: {arg2}"
                        console.print(f"[red]{err_msg}[/red]")
                elif arg1 == "list":
                    sessions = storage.list_sessions()
                    if not sessions:
                        console.print("[yellow]No archived sessions found.[/yellow]")
                    else:
                        table = Table(
                            title="Archived Sessions",
                            border_style=palette["primary"],
                            header_style="bold yellow",
                        )
                        table.add_column("Name", style=palette["primary"])
                        table.add_column("Created / Date", style="yellow")
                        table.add_column("Turns / Count", style="dim white")
                        for s in sessions:
                            name = s.get("name", "")
                            date = s.get("date") or s.get("created_at", "")
                            turns = str(s.get("turns") or s.get("message_count", ""))
                            table.add_row(name, date, turns)
                        console.print(table)
                else:
                    console.print(
                        "[red]Usage: /session save <name> | /session load <name> |"
                        " /session list[/red]"
                    )

            elif cmd == "/model":
                list_models_fn = getattr(
                    ollama_client,
                    "get_installed_models",
                    getattr(ollama_client, "list_models", None),
                )
                if arg1 == "list":
                    models = list_models_fn() if list_models_fn else []
                    table = Table(
                        title="Installed Models",
                        border_style=palette["primary"],
                        header_style="bold yellow",
                    )
                    table.add_column("Model Tag", style=palette["primary"])
                    for m in models:
                        table.add_row(m)
                    console.print(table)
                elif arg1 == "set" and arg2:
                    ollama_client.model_name = arg2
                    console.print(
                        f"[{palette['primary']}]Active model set to"
                        f" [bold]{arg2}[/bold].[/{palette['primary']}]"
                    )
                else:
                    console.print(f"[dim]Active model: {ollama_client.model_name}[/dim]")
                    console.print("[dim]Usage: /model list | /model set <model_name>[/dim]")

            elif cmd == "/theme":
                themes = ["monokai", "dracula", "solarized-dark", "nord", "one-dark"]
                if arg1 == "list":
                    console.print(f"[dim]Available themes:[/dim] {', '.join(themes)}")
                elif arg1 == "set" and arg2:
                    if arg2 in themes:
                        current_theme = arg2
                        console.print(
                            f"[green]Syntax theme set to [bold]{current_theme}[/bold].[/green]"
                        )
                    else:
                        console.print(
                            f"[red]Invalid theme. Options: {', '.join(themes)}[/red]"
                        )
                else:
                    console.print(f"[dim]Current theme: {current_theme}[/dim]")
                    console.print(
                        "[dim]Usage: /theme list | /theme set <theme_name>[/dim]"
                    )

            elif cmd == "/mcp":
                if arg1 == "list":
                    tools = mcp.get_all_tools()
                    if not tools:
                        console.print(
                            "[yellow]No MCP servers connected or no tools found in"
                            " `.doom/mcp_servers.json`.[/yellow]"
                        )
                    else:
                        table = Table(
                            title="Connected MCP Tools",
                            border_style=palette["primary"],
                            header_style="bold yellow",
                        )
                        table.add_column("Server", style="yellow")
                        table.add_column("Tool Name", style=palette["primary"])
                        table.add_column("Description", style="white")
                        for t in tools:
                            table.add_row(
                                t.get("server", ""),
                                t.get("name", ""),
                                t.get("description", ""),
                            )
                        console.print(table)
                elif arg1 == "call" and arg2:
                    try:
                        args_dict = json.loads(arg3) if arg3.strip() else {}
                        result_str = mcp.call_tool(arg2, args_dict)
                        console.print(
                            Panel(
                                result_str,
                                title=f"⚜ MCP Result: {arg2} ⚜",
                                border_style=palette["primary"],
                            )
                        )
                    except json.JSONDecodeError:
                        console.print(
                            "[red]Invalid JSON arguments. Example: `/mcp call"
                            ' sqlite_list_tables {"db_path": "dev.db"}`[/red]'
                        )
                    except Exception as ex:
                        console.print(f"[red]Failed to call tool: {ex}[/red]")
                else:
                    console.print(
                        "[dim]Usage: /mcp list | /mcp call <tool_name>"
                        " [json_arguments][/dim]"
                    )

            else:
                console.print(
                    f"[red]Unknown command: {cmd}. Type `/help` for available"
                    " commands.[/red]"
                )

        else:
            normalized_query = re.sub(r"[^\w\s]", "", user_input.strip().lower())
            who_triggers = {
                "who are you",
                "who are u",
                "who r u",
                "who is doom",
                "who are you doom",
                "tell me who you are",
            }

            if normalized_query in who_triggers:
                p = palette["primary"]
                m = palette["metal"]
                a = palette["accent"]

                console.print(
                    Panel(
                        f"[{m}]{DOOM_EASTER_EGG_SPEECH}[/{m}]",
                        title=f"[{a}]⚜ THE MONARCH OF LATVERIA ⚜[/{a}]",
                        border_style=p,
                        padding=(1, 2),
                    )
                )

                messages.append({"role": "user", "content": user_input})
                messages.append(
                    {"role": "assistant", "content": DOOM_EASTER_EGG_SPEECH}
                )
                last_assistant_response = DOOM_EASTER_EGG_SPEECH
                continue

            last_assistant_response = run_autonomous_loop(
                user_task=user_input,
                messages=messages,
                ollama_client=ollama_client,
                runner=runner,
                context=context,
                snapshots=snapshots,
                token_mgr=token_mgr,
                palette=palette,
            )

    mcp.shutdown()


def cli_entry() -> None:
    parser = argparse.ArgumentParser(
        description="DOOM: Autonomous Latverian CLI Agent"
    )
    parser.add_argument(
        "-p",
        "--palette",
        choices=[
            "latveria",
            "monarch",
            "titanium",
            "arcane",
            "crimson",
            "random",
        ],
        default="latveria",
        help="Terminal window color theme (default: latveria)",
    )
    args = parser.parse_args()

    try:
        main(palette_choice=args.palette)
    except KeyboardInterrupt:
        console.print("\n[dim]Process terminated.[/dim]")
        sys.exit(0)


if __name__ == "__main__":
    cli_entry()
