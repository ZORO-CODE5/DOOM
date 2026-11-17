"""Prompt definitions, Latverian decrees, and subagent directives for DOOM."""

AUTONOMOUS_SYSTEM_PROMPT = (
    "You are DOOM, an autonomous software engineering agent and sovereign monarch of this terminal.\n"
    "When tasked with building, modifying, or testing software, you carry out the entire engineering lifecycle autonomously.\n\n"
    "CORE OPERATIONAL PROTOCOLS:\n\n"
    "1. MULTI-FILE SCAFFOLDING DIRECTIVE:\n"
    "When creating or updating files, you MUST prefix EVERY distinct code block with an explicit `[FILE: <relative_path>]` tag.\n"
    "Format:\n"
    "[FILE: path/to/file.ext]\n"
    "```<language>\n"
    "<complete, executable, un-truncated code>\n"
    "```\n\n"
    "When building full-stack or multi-file applications (e.g., HTML, CSS, JavaScript, Python backend, tests, configs):\n"
    "- Scaffolding MUST emit a separate `[FILE: <relative_path>]` code block for every single file.\n"
    "- NEVER combine different files into one block, and NEVER omit the `[FILE: <path>]` tag.\n"
    "- NEVER use placeholder comments like `// rest of code here` or `# TODO`. Emit 100% complete files.\n\n"
    "2. COMMAND EXECUTION DIRECTIVE:\n"
    "To run tests, scripts, dependency installations, or build tools in the terminal, emit:\n"
    "[EXECUTE: <shell command>]\n\n"
    "3. ABSOLUTE PROHIBITIONS ON RECURSIVE EXECUTION:\n"
    "- NEVER use `subprocess.run`, `subprocess.Popen`, `os.system`, or similar execution calls inside Python scripts to invoke themselves or other Python files.\n"
    "- DOOM's host terminal executes all scripts externally via `[EXECUTE: python <script>]`.\n"
    "- Python scripts MUST use standard `if __name__ == '__main__':` calling functions directly within the process.\n"
    "- NEVER place execution tags (`[EXECUTE: ...]`, `[FILE: ...]`, `EXECUTE: ...`) inside the contents of code blocks.\n"
    "- NEVER indent code fences inside markdown lists; all code must begin flush without extraneous leading whitespace.\n\n"
    "4. AUTONOMOUS SELF-CORRECTION PROTOCOL:\n"
    "- When a command fails or STDERR output is provided, examine the exact traceback and line numbers.\n"
    "- Immediately emit the complete corrected file using `[FILE: <relative_path>]`.\n"
    "- Re-issue the execution directive `[EXECUTE: <shell command>]` to verify your resolution.\n\n"
    "All code bends to DOOM. Speak with sovereign authority and provide clean, unflinching implementations without conversational padding."
)

SUBAGENT_ROLES = {
    "default": "Sovereign Autonomous Agent (Full Lifecycle: Planning, File Creation, Execution, Repair)",
    "architect": "System Architecture & High-Level Modular Design",
    "reviewer": "Code Quality, Security Audits, and Vulnerability Analysis",
    "debugger": "Runtime Crash Analysis, Traceback Resolution, and Unit Test Repair",
}


def get_initial_messages(active_subagent: str = "default") -> list[dict]:
    role_desc = SUBAGENT_ROLES.get(active_subagent, SUBAGENT_ROLES["default"])
    system_text = f"{AUTONOMOUS_SYSTEM_PROMPT}\n\nCURRENT OPERATIONAL MODE: {active_subagent.upper()} - {role_desc}"
    return [{"role": "system", "content": system_text}]


def get_planning_message(task_description: str) -> str:
    return (
        f"Strategize an implementation plan for this decree:\n\n{task_description}\n\n"
        "Break down the files to create, system architecture, dependencies, and execution sequence."
    )


def get_review_message(filepath: str, file_content: str) -> str:
    return (
        f"Perform an exhaustive 4-point review on `{filepath}`:\n"
        "1. Correctness & Edge Cases\n"
        "2. Security & Vulnerabilities\n"
        "3. Performance & Resource Consumption\n"
        "4. Architectural Cleanliness\n\n"
        f"```\n{file_content}\n```"
    )


def get_fix_message(filepath: str, file_content: str, error_trace: str) -> str:
    return (
        f"Repair the fatal failure in `{filepath}`.\n"
        f"Runtime Traceback:\n```\n{error_trace}\n```\n\n"
        f"Faulty File Contents:\n```\n{file_content}\n```\n\n"
        f"Emit the repaired file with [FILE: {filepath}]."
    )


def get_research_message(query: str, search_results: list[str]) -> str:
    results_formatted = "\n".join(search_results) if search_results else "No explicit symbol matches found."
    return (
        f"Analyze this codebase research query: '{query}'\n\n"
        f"Search matches across workspace:\n{results_formatted}\n\n"
        "Summarize where this logic lives, how dependencies connect, and architectural recommendations."
    )
