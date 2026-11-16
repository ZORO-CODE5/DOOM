"""DOOM entry point, interactive loop, and command router."""

import re
import sys
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax
from rich.table import Table

from context import ProjectContext
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
DEFAULT_MODEL = "qwen2.5-coder:3b"

AVAILABLE_THEMES = {
    "monokai": "Monokai (Dark / Vibrant)",
    "dracula": "Dracula (Dark / Purple tones)",
    "solarized-dark": "Solarized Dark (Teal / Warm)",
    "github-dark": "GitHub Dark (Modern Dark)",
    "one-dark": "One Dark (Atom-inspired)",
}
CURRENT_THEME = "monokai"
CURRENT_SUBAGENT = "default"


def display_welcome(model_name: str, workspace_name: str, theme_name: str, subagent_role: str):
    welcome_text = (
        "[bold cyan]DOOM[/bold cyan] - Local AI Coding Companion\n"
        "[dim]Tagline: Think. Build. Execute.[/dim]\n\n"
        f"Active Model:    [green]{model_name}[/green]\n"
        f"Active Subagent: [cyan]{subagent_role.upper()}[/cyan]\n"
        f"Workspace:       [yellow]{workspace_name}[/yellow]\n"
        f"Syntax Theme:    [magenta]{theme_name}[/magenta]\n\n"
        "Commands:\n"
        "  [yellow]/subagent <list|set>[/yellow]     - Switch specialized persona (architect, security, tester)\n"
        "  [yellow]/research <query>[/yellow]        - Search codebase and analyze across files\n"
        "  [yellow]/plan <task>[/yellow]             - Generate architecture blueprint\n"
        "  [yellow]/review <path>[/yellow]           - Conduct structured code review\n"
        "  [yellow]/fix <path>[/yellow]              - Diagnose and generate fixed file\n"
        "  [yellow]/snapshots [path][/yellow]        - List file snapshots\n"
        "  [yellow]/undo <path>[/yellow]             - Rollback file to previous snapshot\n"
        "  [yellow]/model <list|set>[/yellow]        - View or switch active local AI model\n"
        "  [yellow]/theme <list|set>[/yellow]        - Customize syntax highlighting theme\n"
        "  [yellow]/files[/yellow]                   - List tracked project files\n"
        "  [yellow]/read <path>[/yellow]            - View a file in the terminal\n"
        "  [yellow]/add <path>[/yellow]             - Load a file into AI context\n"
        "  [yellow]/save <path>[/yellow]            - Save last generated code to disk\n"
        "  [yellow]/run <command>[/yellow]          - Run terminal command (with approval)\n"
        "  [yellow]/session <save|load|list>[/yellow] - Manage conversation checkpoints\n"
        "  [yellow]/clear[/yellow]                   - Reset conversation memory\n"
        "  [yellow]/help[/yellow]                    - Show command list\n"
        "  [yellow]/exit[/yellow]                    - Exit DOOM"
    )
    console.print(
        Panel(welcome_text, title="[bold]Welcome[/bold]", border_style="cyan")
    )


def show_help():
    help_content = """
### DOOM Commands

* **/subagent list** - View available specialized personas (default, architect, security, tester).
* **/subagent set <role>** - Activate a specialized subagent for domain-focused reasoning.
* **/research <query>** - Search across all files in the project and synthesize multi-file analysis.
* **/plan <task>** - Plan the architecture of a feature before coding.
* **/review <path>** - Perform a structured audit of a local file.
* **/fix <path>** - Automatically diagnose errors in a file and generate a complete fix.
* **/snapshots [path]** - View all saved snapshots.
* **/undo <path>** - Revert a file to its most recent snapshot.
* **/model list** - Show all local Ollama models installed on this machine.
* **/model set <name>** - Switch active LLM on the fly.
* **/theme list** - Show available syntax highlighting styles.
* **/theme set <name>** - Change the active code theme.
* **/files** - List all tracked project files.
* **/read <path>** - Preview a local file with syntax highlighting.
* **/add <path>** - Attach a file into active AI context.
* **/save <path>** - Save the latest AI code snippet to disk.
* **/run <cmd>** - Safely execute a PowerShell command.
* **/session save <name>** - Save the current conversation state to disk.
* **/session load <name>** - Restore a saved conversation session.
* **/session list** - Show all saved sessions.
* **/clear** - Clear screen and reset conversation history.
* **/help** - Display this command cheat sheet.
* **/exit** (or **/quit**) - Close the session.
"""
    console.print(Markdown(help_content))


def list_files(project_context: ProjectContext):
    files = project_context.get_project_files()
    if not files:
        console.print("[yellow]No tracked project files found.[/yellow]\n")
        return

    tree_display = f"### Project Files ({len(files)} total)\n"
    for file_path in files:
        tree_display += f"* `{file_path}`\n"

    console.print(Markdown(tree_display))


def handle_read_command(project_context: ProjectContext, argument: str):
    if not argument:
        console.print("[yellow]Usage: /read <filepath>[/yellow]\n")
        return

    file_path = argument.strip()
    success, result = project_context.read_file(file_path)

    if not success:
        console.print(f"[bold red]Error:[/bold red] {result}\n")
        return

    extension = file_path.split(".")[-1] if "." in file_path else "text"
    lexer_map = {
        "py": "python",
        "json": "json",
        "md": "markdown",
        "txt": "text",
    }
    lexer = lexer_map.get(extension, "text")

    console.print(f"\n[dim]=== File: {file_path} (Theme: {CURRENT_THEME}) ===[/dim]")
    syntax_view = Syntax(result, lexer, theme=CURRENT_THEME, line_numbers=True)
    console.print(syntax_view)
    console.print(
        f"[dim]=== End of File ({len(result.splitlines())} lines) ===[/dim]\n"
    )


def handle_add_command(
    project_context: ProjectContext,
    conversation_history: list[dict[str, str]],
    argument: str,
):
    if not argument:
        console.print("[yellow]Usage: /add <filepath>[/yellow]\n")
        return

    file_path = argument.strip()
    success, result = project_context.read_file(file_path)

    if not success:
        console.print(f"[bold red]Error:[/bold red] {result}\n")
        return

    file_context_message = {
        "role": "user",
        "content": (
            f"[Context: File loaded from workspace]\n"
            f"Filename: {file_path}\n"
            f"```\n{result}\n```\n"
            f"I have loaded `{file_path}` into our session. Acknowledge briefly that you have read it."
        ),
    }
    conversation_history.append(file_context_message)
    conversation_history.append({
        "role": "assistant",
        "content": (
            f"I have loaded and analyzed `{file_path}`. What would you like to"
            " do with it?"
        ),
    })

    console.print(f"[green]Added `{file_path}` to DOOM context.[/green]\n")


def extract_code_block(markdown_text: str) -> str:
    match = re.search(r"```(?:\w+)?\n(.*?)```", markdown_text, re.DOTALL)
    if match:
        return match.group(1).rstrip()
    return markdown_text.strip()


def handle_save_command(
    project_context: ProjectContext,
    snapshot_manager: SnapshotManager,
    conversation_history: list[dict[str, str]],
    argument: str,
):
    if not argument:
        console.print("[yellow]Usage: /save <filepath>[/yellow]\n")
        return

    target_file = argument.strip()
    last_assistant_msg = None
    for msg in reversed(conversation_history):
        if msg["role"] == "assistant":
            last_assistant_msg = msg["content"]
            break

    if not last_assistant_msg:
        console.print("[yellow]No AI-generated response found to save.[/yellow]\n")
        return

    code_to_write = extract_code_block(last_assistant_msg)
    file_exists = project_context.file_exists(target_file)
    action_label = (
        "[bold red]OVERWRITE[/bold red]"
        if file_exists
        else "[bold green]CREATE[/bold green]"
    )

    prompt_question = f"Do you want DOOM to {action_label} '[cyan]{target_file}[/cyan]' ({len(code_to_write.splitlines())} lines)?"
    if not Confirm.ask(prompt_question, default=False):
        console.print("[dim]Save cancelled by user.[/dim]\n")
        return

    if file_exists:
        snap_ok, snap_msg = snapshot_manager.create_snapshot(target_file)
        if snap_ok:
            console.print(f"[dim]{snap_msg}[/dim]")

    success, message = project_context.write_file(target_file, code_to_write)
    if success:
        console.print(f"[bold green]Success:[/bold green] {message}\n")
    else:
        console.print(f"[bold red]Failed:[/bold red] {message}\n")


def handle_run_command(
    runner: CommandRunner,
    conversation_history: list[dict[str, str]],
    argument: str,
    last_error_holder: dict[str, str],
):
    if not argument:
        console.print("[yellow]Usage: /run <command>[/yellow]\n")
        return

    command = argument.strip()
    is_safe, reason = runner.is_safe(command)
    if not is_safe:
        console.print(f"[bold red]Security Warning:[/bold red] {reason}\n")
        return

    confirm = Confirm.ask(
        f"Execute command: [bold cyan]{command}[/bold cyan]?", default=False
    )
    if not confirm:
        console.print("[dim]Execution cancelled by user.[/dim]\n")
        return

    console.print("[dim]Executing in PowerShell...[/dim]")
    result = runner.execute(command)

    if result["stdout"]:
        console.print(
            f"\n[bold green]Output ({result['elapsed']}s):[/bold green]"
        )
        console.print(result["stdout"])

    if result["stderr"]:
        if result["returncode"] != 0:
            console.print(
                f"\n[bold red]Error Output ({result['elapsed']}s):[/bold red]"
            )
            console.print(result["stderr"])
            last_error_holder["error"] = result["stderr"]
        else:
            console.print(
                f"\n[dim cyan]Execution Log ({result['elapsed']}s):[/dim cyan]"
            )
            console.print(result["stderr"])

    if not result["stdout"] and not result["stderr"]:
        console.print(
            f"[dim]Command finished with return code {result['returncode']}"
            f" ({result['elapsed']}s).[/dim]"
        )

    console.print()

    if result["returncode"] != 0 and result["stderr"]:
        feedback = {
            "role": "user",
            "content": (
                f"[Terminal Execution Error]\n"
                f"Command: {command}\n"
                f"Exit Code: {result['returncode']}\n"
                f"Error:\n{result['stderr']}\n\n"
                "Please analyze this error and tell me how to fix it."
            ),
        }
        conversation_history.append(feedback)
        console.print(
            "[dim]Command error recorded into conversation context.[/dim]\n"
        )


def handle_plan_command(
    ai_client: OllamaClient,
    conversation_history: list[dict[str, str]],
    argument: str,
):
    if not argument:
        console.print("[yellow]Usage: /plan <task description>[/yellow]\n")
        return

    task = argument.strip()
    plan_message = get_planning_message(task)
    conversation_history.append(plan_message)

    console.print(f"\n[bold magenta]DOOM [PLANNING][/bold magenta]:")
    collected_response = ""

    with console.status(
        "[dim magenta]Formulating implementation plan...[/dim magenta]",
        spinner="dots",
    ):
        tokens = []
        for token in ai_client.stream_chat(conversation_history):
            tokens.append(token)
        collected_response = "".join(tokens)

    console.print(Markdown(collected_response))
    console.print()

    conversation_history.append(
        {"role": "assistant", "content": collected_response}
    )


def handle_review_command(
    ai_client: OllamaClient,
    project_context: ProjectContext,
    conversation_history: list[dict[str, str]],
    argument: str,
):
    if not argument:
        console.print("[yellow]Usage: /review <filepath>[/yellow]\n")
        return

    file_path = argument.strip()
    success, content = project_context.read_file(file_path)

    if not success:
        console.print(f"[bold red]Error:[/bold red] {content}\n")
        return

    review_message = get_review_message(file_path, content)
    conversation_history.append(review_message)

    console.print(f"\n[bold blue]DOOM [CODE REVIEW: {file_path}][/bold blue]:")
    collected_response = ""

    with console.status(
        f"[dim blue]Reviewing {file_path}...[/dim blue]",
        spinner="dots",
    ):
        tokens = []
        for token in ai_client.stream_chat(conversation_history):
            tokens.append(token)
        collected_response = "".join(tokens)

    console.print(Markdown(collected_response))
    console.print()

    conversation_history.append(
        {"role": "assistant", "content": collected_response}
    )


def handle_fix_command(
    ai_client: OllamaClient,
    project_context: ProjectContext,
    conversation_history: list[dict[str, str]],
    argument: str,
    last_error_holder: dict[str, str],
):
    if not argument:
        console.print("[yellow]Usage: /fix <filepath>[/yellow]\n")
        return

    file_path = argument.strip()
    success, content = project_context.read_file(file_path)

    if not success:
        console.print(f"[bold red]Error:[/bold red] {content}\n")
        return

    error_ctx = last_error_holder.get("error", "")
    fix_message = get_fix_message(file_path, content, error_ctx)
    conversation_history.append(fix_message)

    console.print(f"\n[bold yellow]DOOM [DIAGNOSTICS & FIX: {file_path}][/bold yellow]:")
    collected_response = ""

    with console.status(
        f"[dim yellow]Diagnosing and fixing {file_path}...[/dim yellow]",
        spinner="dots",
    ):
        tokens = []
        for token in ai_client.stream_chat(conversation_history):
            tokens.append(token)
        collected_response = "".join(tokens)

    console.print(Markdown(collected_response))
    console.print()

    conversation_history.append(
        {"role": "assistant", "content": collected_response}
    )
    console.print(f"[dim]Tip: Type '[cyan]/save {file_path}[/cyan]' to apply this fix to disk.[/dim]\n")


def handle_research_command(
    ai_client: OllamaClient,
    project_context: ProjectContext,
    conversation_history: list[dict[str, str]],
    argument: str,
):
    if not argument:
        console.print("[yellow]Usage: /research <query/symbol>[/yellow]\n")
        return

    query = argument.strip()
    matches = project_context.search_codebase(query)

    if not matches:
        console.print(f"[yellow]No occurrences of '{query}' found across project files.[/yellow]\n")
        return

    table = Table(title=f"Codebase Matches: '{query}'", border_style="cyan")
    table.add_column("File", style="cyan")
    table.add_column("Line", justify="right", style="magenta")
    table.add_column("Snippet", style="dim")

    for item in matches[:10]:
        table.add_row(str(item["file"]), str(item["line"]), str(item["snippet"]))

    console.print(table)
    console.print()

    research_msg = get_research_message(query, matches)
    conversation_history.append(research_msg)

    console.print(f"[bold cyan]DOOM [RESEARCH ANALYSIS: '{query}']:[/bold cyan]")
    collected_response = ""

    with console.status(
        f"[dim cyan]Synthesizing findings across {len(matches)} occurrences...[/dim cyan]",
        spinner="dots",
    ):
        tokens = []
        for token in ai_client.stream_chat(conversation_history):
            tokens.append(token)
        collected_response = "".join(tokens)

    console.print(Markdown(collected_response))
    console.print()

    conversation_history.append(
        {"role": "assistant", "content": collected_response}
    )


def handle_subagent_command(argument: str, conversation_history: list[dict[str, str]]) -> str:
    """Manages viewing and switching specialized subagent personas."""
    global CURRENT_SUBAGENT
    parts = argument.strip().split(maxsplit=1)
    subcmd = parts[0].lower() if parts else ""
    param = parts[1].strip().lower() if len(parts) > 1 else ""

    if subcmd == "list" or not subcmd:
        table = Table(title="Available Subagents", border_style="cyan")
        table.add_column("Role", style="cyan")
        table.add_column("Description", style="white")
        table.add_column("Status", style="bold")

        descriptions = {
            "default": "Balanced coding companion for everyday programming and explanations",
            "architect": "System design, modular structures, separation of concerns, and API planning",
            "security": "Vulnerability scanning, input sanitization, OWASP checks, and safe execution",
            "tester": "Unit testing suites, edge cases, regression coverage, and mocks",
        }

        for role in SUBAGENT_ROLES:
            status_text = "[green]* Active[/green]" if role == CURRENT_SUBAGENT else "[dim]Available[/dim]"
            table.add_row(role, descriptions.get(role, ""), status_text)

        console.print(table)
        console.print("[dim]Use '/subagent set <role>' to switch active persona.[/dim]\n")
        return CURRENT_SUBAGENT

    elif subcmd == "set":
        if param not in SUBAGENT_ROLES:
            console.print(
                f"[yellow]Unknown role '{param}'. Available: {', '.join(SUBAGENT_ROLES.keys())}[/yellow]\n"
            )
            return CURRENT_SUBAGENT

        CURRENT_SUBAGENT = param
        # Update system instruction in the active conversation
        conversation_history[0] = {"role": "system", "content": SUBAGENT_ROLES[CURRENT_SUBAGENT]}
        console.print(f"[bold green]Active Subagent changed to:[/bold green] [cyan]{CURRENT_SUBAGENT.upper()}[/cyan]\n")
        return CURRENT_SUBAGENT

    else:
        console.print("[yellow]Usage: /subagent <list|set> [role][/yellow]\n")
        return CURRENT_SUBAGENT


def handle_snapshots_command(snapshot_manager: SnapshotManager, argument: str):
    target_filter = argument.strip()
    snaps = snapshot_manager.list_snapshots(target_filter)

    if not snaps:
        console.print("[dim]No snapshots found.[/dim]\n")
        return

    table = Table(title="File Snapshots", border_style="cyan")
    table.add_column("File", style="cyan")
    table.add_column("Snapshot Date", style="dim")
    table.add_column("Backup Path", style="dim")

    for s in snaps:
        table.add_row(s["original"], s["timestamp"], s["backup_path"])

    console.print(table)
    console.print()


def handle_undo_command(snapshot_manager: SnapshotManager, argument: str):
    if not argument:
        console.print("[yellow]Usage: /undo <filepath>[/yellow]\n")
        return

    file_path = argument.strip()
    confirm = Confirm.ask(
        f"Revert '[cyan]{file_path}[/cyan]' to its previous snapshot?", default=False
    )
    if not confirm:
        console.print("[dim]Rollback cancelled by user.[/dim]\n")
        return

    success, msg = snapshot_manager.restore_latest_snapshot(file_path)
    if success:
        console.print(f"[bold green]Success:[/bold green] {msg}\n")
    else:
        console.print(f"[bold red]Error:[/bold red] {msg}\n")


def handle_model_command(ai_client: OllamaClient, argument: str):
    parts = argument.strip().split(maxsplit=1)
    subcmd = parts[0].lower() if parts else ""
    param = parts[1].strip() if len(parts) > 1 else ""

    if subcmd == "list" or not subcmd:
        models = ai_client.get_installed_models()
        if not models:
            console.print("[yellow]No local Ollama models found.[/yellow]\n")
            return

        table = Table(title="Installed Ollama Models", border_style="cyan")
        table.add_column("Model Name", style="cyan")
        table.add_column("Status", style="bold")

        for m in models:
            is_active = (m == ai_client.model_name) or (ai_client.model_name in m)
            status_text = "[green]* Active[/green]" if is_active else "[dim]Available[/dim]"
            table.add_row(m, status_text)

        console.print(table)
        console.print("[dim]Use '/model set <name>' to switch models.[/dim]\n")

    elif subcmd == "set":
        if not param:
            console.print("[yellow]Usage: /model set <model_name>[/yellow]\n")
            return

        large_model_tokens = ["14b", "32b", "70b"]
        if any(tok in param.lower() for tok in large_model_tokens):
            console.print(
                "[yellow]Advisory:[/yellow] This model may exceed your 4 GB VRAM limit, "
                "which could result in slower system responsiveness."
            )

        success, result = ai_client.switch_model(param)
        if success:
            console.print(f"[bold green]Switched active model to:[/bold green] [cyan]{result}[/cyan]\n")
        else:
            console.print(f"[bold red]Error:[/bold red] {result}\n")

    else:
        console.print("[yellow]Usage: /model <list|set> [name][/yellow]\n")


def handle_theme_command(argument: str):
    global CURRENT_THEME
    parts = argument.strip().split(maxsplit=1)
    subcmd = parts[0].lower() if parts else ""
    param = parts[1].strip().lower() if len(parts) > 1 else ""

    if subcmd == "list" or not subcmd:
        table = Table(title="Available Code Themes", border_style="magenta")
        table.add_column("Theme Key", style="magenta")
        table.add_column("Description", style="white")
        table.add_column("Status", style="bold")

        for key, desc in AVAILABLE_THEMES.items():
            status_text = "[green]* Active[/green]" if key == CURRENT_THEME else "[dim]Available[/dim]"
            table.add_row(key, desc, status_text)

        console.print(table)
        console.print("[dim]Use '/theme set <key>' to change theme.[/dim]\n")

    elif subcmd == "set":
        if param not in AVAILABLE_THEMES:
            console.print(
                f"[yellow]Unknown theme '{param}'. Available: {', '.join(AVAILABLE_THEMES.keys())}[/yellow]\n"
            )
            return

        CURRENT_THEME = param
        console.print(f"[bold green]Syntax theme set to:[/bold green] [magenta]{param}[/magenta]\n")

    else:
        console.print("[yellow]Usage: /theme <list|set> [name][/yellow]\n")


def handle_session_command(
    storage: SessionStorage,
    ai_client: OllamaClient,
    conversation_history: list[dict[str, str]],
    argument: str,
) -> list[dict[str, str]]:
    parts = argument.strip().split(maxsplit=1)
    subcmd = parts[0].lower() if parts else ""
    param = parts[1].strip() if len(parts) > 1 else ""

    if subcmd == "save":
        if not param:
            console.print("[yellow]Usage: /session save <session_name>[/yellow]\n")
            return conversation_history
        success, msg = storage.save_session(
            param, ai_client.model_name, conversation_history
        )
        if success:
            console.print(f"[bold green]Success:[/bold green] {msg}\n")
        else:
            console.print(f"[bold red]Error:[/bold red] {msg}\n")
        return conversation_history

    elif subcmd == "load":
        if not param:
            console.print("[yellow]Usage: /session load <session_name>[/yellow]\n")
            return conversation_history
        success, result = storage.load_session(param)
        if success:
            console.print(
                f"[bold green]Success:[/bold green] Loaded session '{param}'"
                f" ({len(result)} turns restored).\n"
            )
            return result
        else:
            console.print(f"[bold red]Error:[/bold red] {result}\n")
            return conversation_history

    elif subcmd == "list":
        sessions = storage.list_sessions()
        if not sessions:
            console.print("[dim]No saved sessions found.[/dim]\n")
            return conversation_history

        table = Table(title="Saved DOOM Sessions", border_style="cyan")
        table.add_column("Session Name", style="cyan")
        table.add_column("Saved Date", style="dim")
        table.add_column("History Length", justify="right")

        for s in sessions:
            table.add_row(s["name"], s["date"], f"{s['turns']} messages")

        console.print(table)
        console.print()
        return conversation_history

    else:
        console.print("[yellow]Usage: /session <save|load|list> [name][/yellow]\n")
        return conversation_history


def main():
    global CURRENT_SUBAGENT
    workspace = ProjectContext()
    runner = CommandRunner(working_dir=workspace.root_path)
    storage = SessionStorage(workspace_root=workspace.root_path)
    snapshot_manager = SnapshotManager(workspace_root=workspace.root_path)
    last_error_holder: dict[str, str] = {}

    ai_client = OllamaClient(model_name=DEFAULT_MODEL)
    display_welcome(ai_client.model_name, workspace.root_path.name, CURRENT_THEME, CURRENT_SUBAGENT)

    with console.status("[cyan]Connecting to Ollama...[/cyan]"):
        is_ready, message = ai_client.verify_connection()

    if not is_ready:
        console.print(f"[bold red]Connection Error:[/bold red] {message}")
        sys.exit(1)

    console.print("[green]Ready.[/green] Ask a coding question or enter a command.\n")

    conversation_history = get_initial_messages(CURRENT_SUBAGENT)

    while True:
        try:
            user_input = Prompt.ask("[bold cyan]DOOM[/bold cyan]").strip()

            if not user_input:
                continue

            parts = user_input.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if cmd in ["/exit", "/quit"]:
                console.print("[dim]Shutting down DOOM. Happy coding![/dim]")
                break

            if cmd == "/clear":
                console.clear()
                conversation_history = get_initial_messages(CURRENT_SUBAGENT)
                last_error_holder.clear()
                display_welcome(ai_client.model_name, workspace.root_path.name, CURRENT_THEME, CURRENT_SUBAGENT)
                console.print("[dim]Conversation history reset.[/dim]\n")
                continue

            if cmd == "/help":
                show_help()
                continue

            if cmd == "/files":
                list_files(workspace)
                continue

            if cmd == "/read":
                handle_read_command(workspace, arg)
                continue

            if cmd == "/add":
                handle_add_command(workspace, conversation_history, arg)
                continue

            if cmd == "/save":
                handle_save_command(
                    workspace, snapshot_manager, conversation_history, arg
                )
                continue

            if cmd == "/run":
                handle_run_command(
                    runner, conversation_history, arg, last_error_holder
                )
                continue

            if cmd == "/plan":
                handle_plan_command(ai_client, conversation_history, arg)
                continue

            if cmd == "/review":
                handle_review_command(
                    ai_client, workspace, conversation_history, arg
                )
                continue

            if cmd == "/fix":
                handle_fix_command(
                    ai_client,
                    workspace,
                    conversation_history,
                    arg,
                    last_error_holder,
                )
                continue

            if cmd == "/research":
                handle_research_command(
                    ai_client, workspace, conversation_history, arg
                )
                continue

            if cmd == "/subagent":
                CURRENT_SUBAGENT = handle_subagent_command(arg, conversation_history)
                continue

            if cmd == "/snapshots":
                handle_snapshots_command(snapshot_manager, arg)
                continue

            if cmd == "/undo":
                handle_undo_command(snapshot_manager, arg)
                continue

            if cmd == "/model":
                handle_model_command(ai_client, arg)
                continue

            if cmd == "/theme":
                handle_theme_command(arg)
                continue

            if cmd == "/session":
                conversation_history = handle_session_command(
                    storage, ai_client, conversation_history, arg
                )
                continue

            # Standard chat flow
            conversation_history.append({"role": "user", "content": user_input})

            console.print("\n[bold green]DOOM[/bold green]:")
            collected_response = ""

            with console.status(
                f"[dim cyan]Thinking ({CURRENT_SUBAGENT})...[/dim cyan]", spinner="dots"
            ):
                tokens = []
                for token in ai_client.stream_chat(conversation_history):
                    tokens.append(token)
                collected_response = "".join(tokens)

            console.print(Markdown(collected_response))
            console.print()

            conversation_history.append(
                {"role": "assistant", "content": collected_response}
            )

        except KeyboardInterrupt:
            console.print("\n[dim]Session interrupted. Exiting...[/dim]")
            break
        except Exception as err:
            console.print(f"\n[bold red]Runtime Error:[/bold red] {err}\n")


if __name__ == "__main__":
    main()