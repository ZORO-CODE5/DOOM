# ⚜ DOOM

```
  ⚜  ██████╗  ██████╗  ██████╗ ███╗   ███╗  ⚜
     ██╔══██╗██╔═══██╗██╔═══██╗████╗ ████║      ALL CODE BENDS TO DOOM
     ██║  ██║██║   ██║██║   ██║██╔████╔██║
     ██║  ██║██║   ██║██║   ██║██║╚██╔╝██║
     ██████╔╝╚██████╔╝╚██████╔╝██║ ╚═╝ ██║
     ╚═════╝  ╚═════╝  ╚═════╝ ╚═╝     ╚═╝

```

> **A sovereign, local-first AI coding companion powered by Ollama and MCP.**

**DOOM** is a terminal-based AI assistant built for privacy, zero cloud reliance, and complete local execution. Powered by local LLMs (like `qwen2.5-coder:3b`) via Ollama and extensible through the Model Context Protocol (MCP), DOOM operates directly inside your workspace with a Doctor Doom-themed CLI interface.

---

## ⚡ Features

* **100% Local Inference**: Runs entirely offline via [Ollama](https://ollama.com/), keeping your private source code strictly on your machine.
* **Model Context Protocol (MCP)**: Autonomous multi-step tool execution over JSON-RPC (e.g., SQLite query engines, external local tools) with robust fallback JSON parsing.
* **Doctor Doom Latverian CLI**: Customized terminal UX built with `rich`, featuring royal Latverian banners, styled diagnostics, syntax highlighting, and custom prompts (`doom@latveria:~#`).
* **Safety Snapshots & Undo**: Automatic file snapshots before applying modifications, allowing instant reverts via `/undo`.
* **Visual Diff Viewer**: Unified line-by-line colored diff inspection before saving or overwriting any code block.
* **Sandboxed Command Execution**: Built-in safety-checked command runner with user confirmation safeguards.
* **Session Persistence**: Save and restore complete chat sessions across tasks.

---

## 🛠️ Architecture

```
nexus/
├── main.py              # CLI loop, decree router, and autonomous MCP agent
├── ollama_client.py     # Ollama API streaming & tool-calling client
├── mcp_client.py        # Model Context Protocol (MCP) server manager
├── diff_viewer.py       # Syntax-highlighted unified diff generator
├── runner.py            # Guarded shell command execution engine
├── context.py           # Workspace indexing, file reading, and AST search
├── snapshots.py         # Versioning and snapshot rollback engine
├── storage.py           # Session serialization and persistent history
└── prompts.py           # System prompts and subagent persona definitions

```

---

## 🚀 Installation & Setup

### Prerequisites

1. **Python 3.10+** installed.
2. **[Ollama](https://ollama.com/)** running locally:
```powershell
ollama pull qwen2.5-coder:3b
ollama run qwen2.5-coder:3b

```



### 1. Clone & Install Locally

```powershell
git clone https://github.com/ZORO-CODE5/NEXUS.git doom
cd doom

```

#### Option A: Global CLI Access via `pipx` (Recommended)

```powershell
pip install pipx
python -m pipx ensurepath
pipx install -e .

```

*Ensure `C:\Users\<user>\.local\bin` is in your environment `PATH`.*

#### Option B: Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .

```

---

## 💻 Usage

Run `doom` directly from any folder or project root:

```powershell
doom

```

### Prompt & Decrees

```text
doom@latveria:~# /help

```

### Operational Commands

| Command | Arguments | Description |
| --- | --- | --- |
| `/help` | — | Display the full command protocol index |
| `/files` | — | List all tracked source files in current workspace |
| `/read` | `<path>` | Render file contents with syntax highlighting |
| `/add` | `<path>` | Inject file contents into the active conversation buffer |
| `/save` | `<path>` | Preview diff and save the last generated code block |
| `/undo` | `<path>` | Revert a modified file to its previous backup snapshot |
| `/snapshots` | `[path]` | List all saved backups and timestamps |
| `/run` | `<cmd>` | Execute a local shell command with safety checks |
| `/plan` | `<task>` | Formulate a structured step-by-step implementation strategy |
| `/review` | `<path>` | Execute a 4-point security and quality code audit |
| `/fix` | `<path>` | Diagnose runtime errors and patch the target file |
| `/research` | `<query>` | Search workspace symbols and analyze usage patterns |
| `/subagent` | `list` | `set <role>` | Switch agent persona (e.g., `planner`, `reviewer`, `coder`) |
| `/model` | `list` | `set <name>` | List or switch active Ollama models on the fly |
| `/theme` | `list` | `set <theme>` | Change terminal syntax highlighting palette |
| `/session` | `save` | `load` | `list` | Archive and restore active chat sessions |
| `/mcp` | `list` | `call <tool> <args>` | Inspect active MCP servers or invoke tools manually |
| `/clear` | — | Purge conversational memory buffer and reset terminal |
| `/exit` | — | Terminate active DOOM session |

---

## 🔌 MCP Server Configuration

To wire external tool servers into DOOM, configure `.doom/mcp_servers.json` in your project or home directory:

```json
{
  "mcpServers": {
    "sqlite": {
      "command": "python",
      "args": ["-m", "mcp_server_sqlite", "--db-path", "dev.db"]
    }
  }
}

```

Once defined, DOOM automatically detects available functions and can call them autonomously during chat turns.