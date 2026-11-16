"""DOOM entry point, interactive loop, command router, and autonomous MCP agent."""

import json
import re
import sys
from pathlib import Path
from typing import Any

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from context import ProjectContext
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
from runner import CommandRunner
from snapshots import SnapshotManager
from storage import SessionStorage

console = Console()

DOOM_BANNER_TEXT = r"""
  [bold yellow]⚜[/bold yellow]  [bold green]██████╗  ██████╗  ██████╗ ███╗   ███╗[/bold green]  [bold yellow]⚜[/bold yellow]
     [bold green]██╔══██╗██╔═══██╗██╔═══██╗████╗ ████║[/bold green]      [bold white]ALL CODE BENDS TO DOOM[/bold white]
     [bold green]██║  ██║██║   ██║██║   ██║██╔████╔██║[/bold green]
     [bold green]██║  ██║██║   ██║██║   ██║██║╚██╔╝██║[/bold green]
     [bold green]██████╔╝╚██████╔╝╚██████╔╝██║ ╚═╝ ██║[/bold green]
     [bold green]╚═════╝  ╚═════╝  ╚═════╝ ╚═╝     ╚═╝[/bold green]
"""


def print_banner(model_name: str, active_subagent: str, theme: str) -> None:
    header_content = (
        f"{DOOM_BANNER_TEXT.strip()}\n"
        f"[dim green]─────────────────────────────────────────────────────────────────────────────[/dim green]\n"
        f"  [bold green]CORE:[/bold green] [bold cyan]{model_name}[/bold cyan]   │   "
        f"[bold green]ROLE:[/bold green] [bold magenta]{active_subagent.upper()}[/bold magenta]"
    )

    console.print(
        Panel(
            Align.center(Text.from_markup(header_content)),
            border_style="bold green",
            subtitle="[dim green]Type /help for commands or /exit to quit.[/dim green]",
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
        ("/files", "", "List all tracked files in the workspace"),
        ("/read", "<path>", "Display file contents with syntax highlighting"),
        ("/add", "<path>", "Load a local file into the AI's active context"),
        ("/save", "<path>", "Save the last generated code block to a file"),
        ("/undo", "<path>", "Revert a file to its previous backup snapshot"),
        ("/snapshots", "[path]", "List saved file snapshots and timestamps"),
        ("/run", "<cmd>", "Execute a shell command with safety confirmation"),
        ("/plan", "<task>", "Generate a structured implementation plan"),
        ("/review", "<path>", "Perform a 4-point code quality and security review"),
        ("/fix", "<path>", "Analyze runtime errors and generate a corrected file"),
        ("/research", "<query>", "Search symbols across files and analyze usage"),
        ("/subagent", "list | set <role>", "Inspect or switch active persona"),
        ("/session", "save | load | list", "Persist or restore named chat sessions"),
        ("/model", "list | set <name>", "List or switch active Ollama models"),
        ("/theme", "list | set <theme>", "Inspect or change syntax highlighting theme"),
        ("/mcp", "list | call <tool> <args>", "Inspect connected MCP servers or invoke tools"),
    ]

    for cmd, args, desc in commands:
        table.add_row(cmd, args, desc)

    console.print(table)


def extract_last_code_block(text: str) -> str | None:
    pattern = r"```(?:\w+)?\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        return matches[-1].rstrip()
    return None


def format_mcp_tools_for_ollama(mcp_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Converts MCP tool declarations into Ollama function calling definitions."""
    ollama_tools = []
    for tool in mcp_tools:
        ollama_tools.append({
            "type": "function",
            "function": {
                "name": tool.get("name"),
                "description": tool.get("description", ""),
                "parameters": tool.get(
                    "inputSchema",
                    {
                        "type": "object",
                        "properties": {},
                    },
                ),
            },
        })
    return ollama_tools


def parse_tool_calls_from_response(msg_dict: dict[str, Any], available_tool_names: set[str]) -> list[dict[str, Any]]:
    """Extracts tool calls from native tool_calls, markdown fences, or raw JSON text."""
    raw_calls = msg_dict.get("tool_calls") or []
    calls = []

    for call in raw_calls:
        if isinstance(call, dict):
            func = call.get("function", {})
            name = func.get("name")
            args = func.get("arguments", {})
        else:
            func = getattr(call, "function", None)
            name = getattr(func, "name", None) if func else None
            args = getattr(func, "arguments", {}) if func else {}

        if name and name in available_tool_names:
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            calls.append({"name": name, "arguments": args})

    if calls:
        return calls

    content = (msg_dict.get("content") or "").strip()
    if not content:
        return []

    candidates = []

    fence_matches = re.findall(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL | re.IGNORECASE)
    candidates.extend(fence_matches)

    tag_matches = re.findall(r"<tool_call>\s*(.*?)\s*</tool_call>", content, re.DOTALL | re.IGNORECASE)
    candidates.extend(tag_matches)

    first_brace = content.find("{")
    last_brace = content.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidates.append(content[first_brace : last_brace + 1])

    candidates.append(content)

    for candidate in candidates:
        candidate_clean = candidate.strip()
        try:
            data = json.loads(candidate_clean)
            if isinstance(data, dict) and data.get("name") in available_tool_names:
                args = data.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                return [{"name": data["name"], "arguments": args}]
        except Exception:
            continue

    return []


def handle_chat_turn(
    user_input: str,
    messages: list[dict[str, Any]],
    ollama_client: OllamaClient,
    mcp: MCPManager,
) -> str:
    """Manages chat turn with support for autonomous multi-step tool calls."""
    messages.append({"role": "user", "content": user_input})
    all_tools = mcp.get_all_tools()
    ollama_tools = format_mcp_tools_for_ollama(all_tools) if all_tools else None
    available_tool_names = {t.get("name") for t in all_tools if t.get("name")}

    if not ollama_tools:
        console.print("[bold green]DOOM:[/bold green] ", end="")
        collected = []
        for chunk in ollama_client.stream_chat(messages):
            console.print(chunk, end="")
            collected.append(chunk)
        console.print()
        response_text = "".join(collected)
        messages.append({"role": "assistant", "content": response_text})
        return response_text

    max_steps = 5
    step = 0
    while step < max_steps:
        step += 1
        raw_resp = ollama_client.chat_with_tools(messages, ollama_tools)

        if hasattr(raw_resp, "message"):
            raw_msg = raw_resp.message
            msg = {
                "role": getattr(raw_msg, "role", "assistant"),
                "content": getattr(raw_msg, "content", "") or "",
                "tool_calls": getattr(raw_msg, "tool_calls", None),
            }
        elif isinstance(raw_resp, dict):
            raw_msg = raw_resp.get("message", {})
            msg = {
                "role": raw_msg.get("role", "assistant"),
                "content": raw_msg.get("content", "") or "",
                "tool_calls": raw_msg.get("tool_calls", None),
            }
        else:
            msg = {"role": "assistant", "content": str(raw_resp), "tool_calls": None}

        tool_calls = parse_tool_calls_from_response(msg, available_tool_names)

        if not tool_calls:
            content = msg.get("content", "")
            console.print(f"[bold green]DOOM:[/bold green] {content}")
            messages.append({"role": "assistant", "content": content})
            return content

        messages.append({
            "role": "assistant",
            "content": msg.get("content", ""),
        })

        for call in tool_calls:
            func_name = call["name"]
            func_args = call.get("arguments", {})

            console.print(
                f"[dim yellow]Using Tool:[/dim yellow] [bold green]{func_name}[/bold green]({json.dumps(func_args)})"
            )
            tool_output = mcp.call_tool(func_name, func_args)

            messages.append({
                "role": "user",
                "content": (
                    f"[Tool Result from {func_name}]: {tool_output}\n"
                    "Now provide a direct, concise response explaining this result to the user."
                ),
            })

    console.print("[yellow]Reached maximum tool execution turns.[/yellow]")
    return ""


def main() -> None:
    context = ProjectContext(Path.cwd())
    runner = CommandRunner(context.root_path)
    snapshots = SnapshotManager(context.root_path)
    storage = SessionStorage(context.root_path)
    ollama_client = OllamaClient()

    mcp = MCPManager(context.root_path)
    mcp.load_servers()

    current_theme = "monokai"
    active_subagent = "default"
    messages = get_initial_messages(active_subagent)
    last_assistant_response = ""
    last_run_error = ""

    console.clear()
    print_banner(ollama_client.model_name, active_subagent, current_theme)

    while True:
        try:
            user_input = Prompt.ask(
                "\n[bold green]doom[/bold green][yellow]@[/yellow][bold green]latveria[/bold green]:[bold white]~[/bold white][bold green]#[/bold green]"
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

            elif cmd == "/clear":
                messages = get_initial_messages(active_subagent)
                last_assistant_response = ""
                last_run_error = ""
                console.clear()
                print_banner(ollama_client.model_name, active_subagent, current_theme)
                console.print("[green]Memory buffer purged. Screen wiped.[/green]")

            elif cmd == "/files":
                get_files_fn = getattr(context, "get_project_files", getattr(context, "list_files", None))
                files = get_files_fn() if get_files_fn else []
                if not files:
                    console.print("[yellow]No files found in workspace.[/yellow]")
                else:
                    table = Table(title="Workspace Archives", border_style="green", header_style="bold yellow")
                    table.add_column("File Path", style="bold green")
                    for file_path in files:
                        table.add_row(str(file_path))
                    console.print(table)

            elif cmd == "/read":
                if not arg1:
                    console.print("[red]Usage: /read <filepath>[/red]")
                    continue
                content = context.read_file(arg1)
                if content is None:
                    console.print(f"[red]Could not read file: {arg1}[/red]")
                else:
                    syntax = Syntax(
                        content,
                        Path(arg1).suffix.lstrip(".") or "text",
                        theme=current_theme,
                        line_numbers=True,
                    )
                    console.print(Panel(syntax, title=f"⚜ {arg1} ⚜", border_style="green"))

            elif cmd == "/add":
                if not arg1:
                    console.print("[red]Usage: /add <filepath>[/red]")
                    continue
                content = context.read_file(arg1)
                if content is None:
                    console.print(f"[red]Could not read file: {arg1}[/red]")
                else:
                    messages.append({
                        "role": "user",
                        "content": f"Here is the content of `{arg1}`:\n\n```{Path(arg1).suffix.lstrip('.')}\n{content}\n```",
                    })
                    console.print(f"[green]Added `{arg1}` to context.[/green]")

            elif cmd == "/save":
                if not arg1:
                    console.print("[red]Usage: /save <filepath>[/red]")
                    continue
                code = extract_last_code_block(last_assistant_response)
                if not code:
                    console.print("[red]No code block found in the last assistant response.[/red]")
                    continue

                resolve_fn = getattr(context, "resolve_path", lambda p: context.root_path / p)
                target_path = resolve_fn(arg1)
                if target_path.exists():
                    snapshots.create_snapshot(target_path)
                    confirm = Confirm.ask(f"[yellow]Overwrite existing file `{arg1}`?[/yellow]")
                    if not confirm:
                        console.print("[dim]Save canceled.[/dim]")
                        continue

                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(code, encoding="utf-8")
                console.print(f"[green]Saved code block to `{arg1}`.[/green]")

            elif cmd == "/undo":
                if not arg1:
                    console.print("[red]Usage: /undo <filepath>[/red]")
                    continue
                resolve_fn = getattr(context, "resolve_path", lambda p: context.root_path / p)
                target_path = resolve_fn(arg1)
                success = snapshots.restore_latest(target_path)
                if success:
                    console.print(f"[green]Restored `{arg1}` from latest snapshot.[/green]")
                else:
                    console.print(f"[red]No snapshots found for `{arg1}`.[/red]")

            elif cmd == "/snapshots":
                all_snapshots = snapshots.list_snapshots(arg1 if arg1 else None)
                if not all_snapshots:
                    console.print("[yellow]No snapshots found.[/yellow]")
                else:
                    table = Table(title="Latverian Snapshots", border_style="green", header_style="bold yellow")
                    table.add_column("Target File", style="bold green")
                    table.add_column("Backup File", style="dim white")
                    table.add_column("Timestamp", style="yellow")
                    for snap in all_snapshots:
                        table.add_row(snap["target_file"], snap["backup_name"], snap["timestamp"])
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
                if result.stdout:
                    console.print(Panel(result.stdout.strip(), title="stdout", border_style="green"))
                if result.stderr:
                    console.print(Panel(result.stderr.strip(), title="stderr", border_style="red"))
                    last_run_error = result.stderr.strip()
                console.print(f"[dim]Exited with code {result.returncode} in {result.duration:.2f}s[/dim]")

            elif cmd == "/plan":
                task_description = user_input[5:].strip()
                if not task_description:
                    console.print("[red]Usage: /plan <task description>[/red]")
                    continue
                plan_prompt = get_planning_message(task_description)
                messages.append({"role": "user", "content": plan_prompt})
                console.print("[bold green]Doom strategizes...[/bold green]")
                response_stream = ollama_client.stream_chat(messages)
                collected = []
                for chunk in response_stream:
                    console.print(chunk, end="")
                    collected.append(chunk)
                console.print()
                last_assistant_response = "".join(collected)
                messages.append({"role": "assistant", "content": last_assistant_response})

            elif cmd == "/review":
                if not arg1:
                    console.print("[red]Usage: /review <filepath>[/red]")
                    continue
                content = context.read_file(arg1)
                if content is None:
                    console.print(f"[red]Could not read file: {arg1}[/red]")
                    continue
                review_prompt = get_review_message(arg1, content)
                messages.append({"role": "user", "content": review_prompt})
                console.print(f"[bold green]Doom audits {arg1}...[/bold green]")
                response_stream = ollama_client.stream_chat(messages)
                collected = []
                for chunk in response_stream:
                    console.print(chunk, end="")
                    collected.append(chunk)
                console.print()
                last_assistant_response = "".join(collected)
                messages.append({"role": "assistant", "content": last_assistant_response})

            elif cmd == "/fix":
                if not arg1:
                    console.print("[red]Usage: /fix <filepath>[/red]")
                    continue
                content = context.read_file(arg1)
                if content is None:
                    console.print(f"[red]Could not read file: {arg1}[/red]")
                    continue
                fix_prompt = get_fix_message(arg1, content, last_run_error)
                messages.append({"role": "user", "content": fix_prompt})
                console.print(f"[bold green]Doom repairs {arg1}...[/bold green]")
                response_stream = ollama_client.stream_chat(messages)
                collected = []
                for chunk in response_stream:
                    console.print(chunk, end="")
                    collected.append(chunk)
                console.print()
                last_assistant_response = "".join(collected)
                messages.append({"role": "assistant", "content": last_assistant_response})

            elif cmd == "/research":
                query = user_input[9:].strip()
                if not query:
                    console.print("[red]Usage: /research <query>[/red]")
                    continue
                search_fn = getattr(context, "search_codebase", None)
                search_results = search_fn(query) if search_fn else []
                research_prompt = get_research_message(query, search_results)
                messages.append({"role": "user", "content": research_prompt})
                console.print(f"[bold green]Doom investigates '{query}'...[/bold green]")
                response_stream = ollama_client.stream_chat(messages)
                collected = []
                for chunk in response_stream:
                    console.print(chunk, end="")
                    collected.append(chunk)
                console.print()
                last_assistant_response = "".join(collected)
                messages.append({"role": "assistant", "content": last_assistant_response})

            elif cmd == "/subagent":
                if arg1 == "list":
                    table = Table(title="Available Subagents", border_style="green", header_style="bold yellow")
                    table.add_column("Role", style="bold green")
                    table.add_column("Description", style="white")
                    for role, desc in SUBAGENT_ROLES.items():
                        table.add_row(role, desc)
                    console.print(table)
                elif arg1 == "set" and arg2:
                    if arg2 in SUBAGENT_ROLES:
                        active_subagent = arg2
                        messages = get_initial_messages(active_subagent)
                        console.print(f"[green]Switched subagent to [bold]{active_subagent}[/bold]. History reset.[/green]")
                    else:
                        console.print(f"[red]Unknown role: {arg2}. Use `/subagent list`.[/red]")
                else:
                    console.print("[red]Usage: /subagent list | /subagent set <role>[/red]")

            elif cmd == "/session":
                if arg1 == "save" and arg2:
                    storage.save_session(arg2, ollama_client.model_name, messages)
                    console.print(f"[green]Session sealed in archives as `{arg2}`.[/green]")
                elif arg1 == "load" and arg2:
                    loaded = storage.load_session(arg2)
                    if loaded:
                        messages = loaded["messages"]
                        ollama_client.model_name = loaded.get("model", ollama_client.model_name)
                        console.print(f"[green]Session `{arg2}` restored ({len(messages)} messages).[/green]")
                    else:
                        console.print(f"[red]Could not load session: {arg2}[/red]")
                elif arg1 == "list":
                    sessions = storage.list_sessions()
                    if not sessions:
                        console.print("[yellow]No archived sessions found.[/yellow]")
                    else:
                        table = Table(title="Archived Sessions", border_style="green", header_style="bold yellow")
                        table.add_column("Name", style="bold green")
                        table.add_column("Created", style="yellow")
                        table.add_column("Model", style="cyan")
                        table.add_column("Messages", style="dim white")
                        for s in sessions:
                            table.add_row(s["name"], s["created_at"], s["model"], str(s["message_count"]))
                        console.print(table)
                else:
                    console.print("[red]Usage: /session save <name> | /session load <name> | /session list[/red]")

            elif cmd == "/model":
                list_models_fn = getattr(ollama_client, "get_installed_models", getattr(ollama_client, "list_models", None))
                if arg1 == "list":
                    models = list_models_fn() if list_models_fn else []
                    table = Table(title="Installed Models", border_style="green", header_style="bold yellow")
                    table.add_column("Model Tag", style="bold green")
                    for m in models:
                        table.add_row(m)
                    console.print(table)
                elif arg1 == "set" and arg2:
                    ollama_client.model_name = arg2
                    console.print(f"[green]Active model set to [bold]{arg2}[/bold].[/green]")
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
                        console.print(f"[green]Syntax theme set to [bold]{current_theme}[/bold].[/green]")
                    else:
                        console.print(f"[red]Invalid theme. Options: {', '.join(themes)}[/red]")
                else:
                    console.print(f"[dim]Current theme: {current_theme}[/dim]")
                    console.print("[dim]Usage: /theme list | /theme set <theme_name>[/dim]")

            elif cmd == "/mcp":
                if arg1 == "list":
                    tools = mcp.get_all_tools()
                    if not tools:
                        console.print("[yellow]No MCP servers connected or no tools found in `.doom/mcp_servers.json`.[/yellow]")
                    else:
                        table = Table(title="Connected MCP Tools", border_style="green", header_style="bold yellow")
                        table.add_column("Server", style="yellow")
                        table.add_column("Tool Name", style="bold green")
                        table.add_column("Description", style="white")
                        for t in tools:
                            table.add_row(t.get("server", ""), t.get("name", ""), t.get("description", ""))
                        console.print(table)
                elif arg1 == "call" and arg2:
                    try:
                        args_dict = json.loads(arg3) if arg3.strip() else {}
                        result_str = mcp.call_tool(arg2, args_dict)
                        console.print(Panel(result_str, title=f"⚜ MCP Result: {arg2} ⚜", border_style="green"))
                    except json.JSONDecodeError:
                        console.print(
                            '[red]Invalid JSON arguments. Example: `/mcp call sqlite_list_tables {"db_path": "dev.db"}`[/red]'
                        )
                    except Exception as ex:
                        console.print(f"[red]Failed to call tool: {ex}[/red]")
                else:
                    console.print("[dim]Usage: /mcp list | /mcp call <tool_name> [json_arguments][/dim]")

            else:
                console.print(f"[red]Unknown command: {cmd}. Type `/help` for available commands.[/red]")

        else:
            last_assistant_response = handle_chat_turn(user_input, messages, ollama_client, mcp)

    mcp.shutdown()


def cli_entry() -> None:
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[dim]Process terminated.[/dim]")
        sys.exit(0)


if __name__ == "__main__":
    cli_entry()