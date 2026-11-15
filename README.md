```markdown
# NEXUS ⚡

> **Think. Build. Execute.**  
> A lightweight, modular, local-first AI coding companion and terminal workflow engine powered by Ollama.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Local LLM: Ollama](https://img.shields.io/badge/Inference-Ollama-000000.svg?logo=ollama&logoColor=white)](https://ollama.ai/)
[![Terminal Engine: Rich](https://img.shields.io/badge/Interface-Rich-magenta.svg)](https://github.com/Textualize/rich)
[![Validation: Pydantic](https://img.shields.io/badge/Data%20Validation-Pydantic%20v2-E92063.svg)](https://docs.pydantic.dev/)

---

## Table of Contents

- [Overview](#overview)
- [Design Philosophy](#design-philosophy)
- [System Architecture](#system-architecture)
- [Core Features](#core-features)
- [Interactive Command Matrix](#interactive-command-matrix)
- [Specialized Subagent Personas](#specialized-subagent-personas)
- [Safety & Sandbox Guardrails](#safety--sandbox-guardrails)
- [Installation & Setup](#installation--setup)
- [End-to-End Workflow Walkthrough](#end-to-end-workflow-walkthrough)
- [Configuration & State Storage](#configuration--state-storage)
- [Hardware Optimization](#hardware-optimization)
- [Roadmap (Phase 3)](#roadmap-phase-3)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

**NEXUS** is a fully local AI coding assistant designed for developers seeking terminal-centric workflows without telemetry, API subscription costs, or code privacy risks. Running on consumer hardware through Ollama (standard configuration: `qwen2.5-coder:3b`), NEXUS combines low-latency streaming code generation with defensive workspace execution, automatic pre-write state snapshots, automated diagnostics, and multi-file codebase intelligence.

---

## Design Philosophy

- **Zero Cloud Dependence:** All inference, session caching, codebase indexing, and diagnostics execute strictly on localhost. No API keys, no external subscriptions, and no remote data transmission.
- **Defensive Execution:** The assistant cannot write to disk, run shell commands, or overwrite files without explicit user confirmation.
- **Resilient State Rollbacks:** Any destructive or state-changing disk modification creates a timestamped safety snapshot automatically.
- **Minimalist Footprint:** Built with standard Python libraries alongside strictly necessary utilities (`ollama`, `rich`, `typer`, `pydantic`).

---

## System Architecture

NEXUS decouples the interactive presentation layer, the AI inference driver, the filesystem sandbox, and process execution into dedicated modules:


```

nexus/
├── .nexus/                         # Internal state and persistence (git-ignored)
│   ├── sessions/                   # Pydantic-validated conversation JSON checkpoints
│   └── snapshots/                  # Timestamped file backups (..bak)
├── context.py                      # Workspace scanner, traversal safety checks, regex search
├── main.py                         # CLI entry point, REPL event loop, command routing
├── ollama_client.py                # Ollama driver, streaming inference, model switcher
├── prompts.py                      # Base system prompts, subagents, and structured directives
├── requirements.txt                # Project dependencies
├── runner.py                       # Subprocess execution engine with security blacklists
├── snapshots.py                    # Snapshot backup creation and rollback engine
└── storage.py                      # Session persistence and Pydantic serialization models

```

### Module Responsibilities

| Module | Core Responsibility |
|---|---|
| **`main.py`** | Coordinates the REPL loop, terminal formatting via Rich, and user confirmation prompts. |
| **`context.py`** | Enforces directory boundary limits, ignores binary/virtualenv files, and performs cross-file regex queries. |
| **`ollama_client.py`** | Streams responses token-by-token from Ollama's local HTTP API and manages runtime model swaps. |
| **`prompts.py`** | Supplies strictly bounded prompts for planning, auditing, error diagnostics, and subagent personas. |
| **`runner.py`** | Executes PowerShell/bash commands while blocking malicious command patterns. |
| **`snapshots.py`** | Preserves file versions immediately prior to any `/save` overwrite. |
| **`storage.py`** | Serializes full multi-turn conversation trees with schema verification. |

---

## Core Features

- **Architectural Planning Mode (`/plan`):** Formulates step-by-step implementation blueprints and test checklists before writing code.
- **Automated Static Code Review (`/review`):** Audits target files across correctness, performance, PEP 8 styling, and actionable suggestions.
- **Self-Healing Diagnostics (`/fix`):** Captures runtime error tracebacks from `/run`, isolates root causes, and generates complete corrected code blocks.
- **Deep Codebase Search (`/research`):** Searches all tracked files for symbols, imports, or keywords and returns synthesized architectural documentation.
- **Automated Snapshots & Rollback (`/snapshots`, `/undo`):** Backs up files prior to overwrite and restores them with a single confirmation.
- **Session Serialization (`/session`):** Saves and restores named conversation sessions across terminal restarts.
- **Runtime Model & UI Customization (`/model`, `/theme`):** Switch between installed Ollama models and modify terminal syntax themes on the fly.

---

## Interactive Command Matrix

All commands use a slash prefix (`/`) inside the NEXUS interactive prompt.

| Command | Arguments | Description |
|---|---|---|
| `/plan` | `<task description>` | Produces an architectural blueprint with objectives, files, and verification steps. |
| `/review` | `<filepath>` | Performs a structured 4-point audit of a file without editing disk state. |
| `/fix` | `<filepath>` | Diagnoses bugs or recent execution errors in a file and provides corrected code. |
| `/research` | `<query \| symbol>` | Scans project files and synthesizes multi-file references and implementations. |
| `/subagent` | `list \| set <role>` | Switches the active persona (`default`, `architect`, `security`, `tester`). |
| `/snapshots`| `[filepath]` | Displays all timestamped file backups stored in `.nexus/snapshots/`. |
| `/undo` | `<filepath>` | Reverts a file to its most recent pre-save snapshot. |
| `/read` | `<filepath>` | Renders a file directly in the terminal with line numbers and syntax highlighting. |
| `/add` | `<filepath>` | Ingests a local file into the AI's active conversational memory. |
| `/save` | `<filepath>` | Extracts the last generated code block and writes it to disk (with overwrite warnings). |
| `/run` | `<command>` | Safely executes a shell command in the workspace directory with execution timing. |
| `/session` | `save <name>` | Serializes active conversation history to `.nexus/sessions/<name>.json`. |
| `/session` | `load <name>` | Deserializes and restores a saved conversation checkpoint into active memory. |
| `/session` | `list` | Lists all saved sessions, creation timestamps, and message counts. |
| `/model` | `list \| set <model>`| Lists locally downloaded Ollama models or switches the active model at runtime. |
| `/theme` | `list \| set <theme>`| Switches syntax highlighting (`monokai`, `dracula`, `solarized-dark`, etc.). |
| `/files` | — | Lists all tracked files in the workspace (excluding `.venv`, `.git`, `.nexus`). |
| `/clear` | — | Resets in-memory conversation history and clears the terminal screen. |
| `/help` | — | Displays the interactive command cheat sheet. |
| `/exit` | — | Terminates the NEXUS session. |

---

## Specialized Subagent Personas

NEXUS allows reconfiguring its reasoning engine via `/subagent set <role>`:


```

┌─────────────────┐     ┌──────────────────────────────────────────────────────────────┐
│    Subagent     │     │ Primary Directive                                            │
├─────────────────┼─────┼──────────────────────────────────────────────────────────────┤
│  default        │ ──► │ Clean, beginner-friendly everyday coding and assistance      │
│  architect      │ ──► │ System design, modularity, API contracts, design patterns    │
│  security       │ ──► │ OWASP checks, input validation, directory traversal defense  │
│  tester         │ ──► │ Unit testing, edge-case analysis, test-driven mock designs   │
└─────────────────┘     └──────────────────────────────────────────────────────────────┘

```

---

## Safety & Sandbox Guardrails

### 1. Filesystem Boundary Protection
`ProjectContext` resolves all relative paths using `.resolve()` and verifies that every target path sits strictly within the project root using `is_relative_to(root_path)`. Any attempt to read or write files outside the workspace is blocked.

### 2. Destructive Command Interception
The `CommandRunner` evaluates command strings against a strict security blacklist before prompting the user for execution approval. Commands containing dangerous operations are halted:

- **Windows:** `format`, `del /s`, `rmdir /s`, `reg add`, `bcdedit`, `net user`
- **Linux/macOS:** `rm -rf /`, `mkfs`, `dd if=`, `:(){ :|:& };:`, `chmod -R 777 /`

### 3. Pre-Write Automatic Backups
Before `main.py` writes to an existing file via `/save`, `SnapshotManager` duplicates the original file into `.nexus/snapshots/<filename>.<timestamp>.bak`. If a generated patch causes unexpected issues, running `/undo <filepath>` restores the previous file immediately.

---

## Installation & Setup

### Prerequisites

- **Python 3.10+**
- **Git**
- **[Ollama](https://ollama.ai/)**

### 1. Clone the Repository
```bash
git clone [https://github.com/ZORO-CODE5/NEXUS.git](https://github.com/ZORO-CODE5/NEXUS.git)
cd NEXUS

```

### 2. Configure Virtual Environment

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

```

**Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate

```

### 3. Install Dependencies

```bash
pip install -r requirements.txt

```

### 4. Pull the Default LLM

Ensure the Ollama background daemon is running, then download the default model:

```bash
ollama pull qwen2.5-coder:3b

```

### 5. Launch NEXUS

```bash
python main.py

```

---

## End-to-End Workflow Walkthrough

Here is a standard development workflow using NEXUS inside your terminal:

### 1. Plan a New Feature

```text
NEXUS: /plan Create a string utility module with slugify and camel_case functions

```

NEXUS outputs an architecture plan outlining functions, edge cases, and test specifications.

### 2. Generate and Save Code

```text
NEXUS: Implement string_utils.py based on the plan above

```

Once the code block streams in:

```text
NEXUS: /save string_utils.py

```

NEXUS prompts for confirmation and writes `string_utils.py` to your project directory.

### 3. Generate and Execute Unit Tests

```text
NEXUS: Write a comprehensive unittest suite for string_utils.py
NEXUS: /save test_strings.py
NEXUS: /run python -m unittest test_strings.py

```

NEXUS requests approval, executes the test suite via PowerShell, and captures stdout/stderr with runtime benchmarks.

### 4. Automatic Diagnostics (If Tests Fail)

If an assertion fails:

```text
NEXUS: /fix string_utils.py

```

NEXUS ingests the traceback, identifies the error, outputs the fix, and automatically snapshots the original file before saving the update.

### 5. Review Code Quality

```text
NEXUS: /review string_utils.py

```

Performs a static quality audit evaluating boundary cases, performance, and PEP 8 standards.

---

## Configuration & State Storage

### `.gitignore` Recommendations

To ensure clean version control, NEXUS keeps all internal checkpoints isolated in `.nexus/`. Ensure your `.gitignore` includes:

```gitignore
.venv/
__pycache__/
*.py[cod]
.nexus/

```

### Session Schema

Sessions saved via `/session save <name>` are validated using the following Pydantic data structure:

```json
{
  "session_name": "feature_auth",
  "created_at": "2026-11-15 21:00:00",
  "model": "qwen2.5-coder:3b",
  "messages": [
    {
      "role": "user",
      "content": "..."
    },
    {
      "role": "assistant",
      "content": "..."
    }
  ]
}

```

---

## Hardware Optimization

NEXUS was developed and tested for smooth operation on standard developer hardware (e.g., Intel Core i7, 16 GB RAM, NVIDIA RTX 2050 4GB VRAM):

| Model Tag | Parameter Size | Approx. VRAM / RAM | Recommended Use Case |
| --- | --- | --- | --- |
| `qwen2.5-coder:3b` | 3 Billion | ~2.5 GB – 3.2 GB | **Recommended:** Real-time generation, low memory footprint. |
| `qwen2.5-coder:7b` | 7 Billion | ~5.5 GB – 6.5 GB | Higher complex reasoning (shares GPU + system RAM). |
| `deepseek-r1:1.5b` | 1.5 Billion | ~1.8 GB – 2.2 GB | Fast reasoning checks and scratchpad planning. |

*Note: Use `/model list` and `/model set <name>` to alternate between models based on workload requirements.*

---

## Roadmap (Phase 3)

* [ ] **Interactive Visual Diff Viewer:** Render terminal-based unified diffs before confirming `/save` overwrites.
* [ ] **Git CLI Integration:** Native `/git` command layer for staging, diffing, and generating commit messages based on diff summaries.
* [ ] **Model Context Protocol (MCP) Client:** Standardized protocol connectors for local SQLite, Postgres, and external API tool executions.
* [ ] **Standalone CLI Distribution:** Package NEXUS via `pyproject.toml` so it can be invoked globally (`nexus`) in any working directory.

---

## Contributing

Contributions, issues, and feature suggestions are welcome!

1. Fork the repository.
2. Create your feature branch (`git checkout -b feature/interactive-diff`).
3. Commit your changes (`git commit -m 'feat: add rich side-by-side file diff'`).
4. Push to the branch (`git push origin feature/interactive-diff`).
5. Open a Pull Request.

---

## License

Distributed under the MIT License. See [LICENSE](https://www.google.com/search?q=LICENSE) for more details.

```

```