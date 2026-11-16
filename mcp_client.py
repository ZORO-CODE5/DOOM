import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class MCPServerSession:
    """Manages a stdio JSON-RPC session with an MCP server."""

    def __init__(self, name: str, command: str, args: list[str], env: dict[str, str] | None = None, cwd: Path | None = None):
        self.name = name
        self.command = command
        self.args = args
        self.env = env
        self.cwd = cwd
        self.process: subprocess.Popen | None = None
        self._request_id = 0
        self.tools: list[dict[str, Any]] = []

    def start(self) -> bool:
        try:
            # If command is 'python', use current virtualenv python executable
            cmd = sys.executable if self.command.lower() in ("python", "python3") else self.command
            
            # Resolve relative script path if provided
            resolved_args = []
            for arg in self.args:
                arg_path = (self.cwd / arg) if self.cwd else Path(arg)
                if arg_path.exists():
                    resolved_args.append(str(arg_path.resolve()))
                else:
                    resolved_args.append(arg)

            self.process = subprocess.Popen(
                [cmd, "-u"] + resolved_args if self.command.lower() in ("python", "python3") else [cmd] + resolved_args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
                cwd=str(self.cwd) if self.cwd else None,
            )
            return self._initialize()
        except Exception as e:
            print(f"[dim red]Failed to start server '{self.name}': {e}[/dim red]")
            return False

    def _send_rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if not self.process or not self.process.stdin or not self.process.stdout:
            return None

        self._request_id += 1
        req = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {},
        }
        try:
            self.process.stdin.write(json.dumps(req) + "\n")
            self.process.stdin.flush()

            response_line = self.process.stdout.readline()
            if not response_line:
                return None
            return json.loads(response_line)
        except Exception:
            return None

    def _initialize(self) -> bool:
        resp = self._send_rpc(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "DOOM-client", "version": "0.1.0"},
            },
        )
        if not resp or "error" in resp:
            return False

        if self.process and self.process.stdin:
            init_notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
            self.process.stdin.write(json.dumps(init_notif) + "\n")
            self.process.stdin.flush()

        self.refresh_tools()
        return True

    def refresh_tools(self) -> list[dict[str, Any]]:
        resp = self._send_rpc("tools/list")
        if resp and "result" in resp:
            self.tools = resp["result"].get("tools", [])
        return self.tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        resp = self._send_rpc("tools/call", {"name": name, "arguments": arguments})
        if not resp:
            return "Error: No response from MCP server."
        if "error" in resp:
            return f"Error: {resp['error']}"
        result = resp.get("result", {})
        content_items = result.get("content", [])
        text_outputs = [item.get("text", "") for item in content_items if item.get("type") == "text"]
        return "\n".join(text_outputs) if text_outputs else json.dumps(result)

    def close(self) -> None:
        if self.process:
            try:
                self.process.terminate()
            except Exception:
                pass
            self.process = None


class MCPManager:
    """Discovers and coordinates MCP server sessions."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.config_file = workspace_root / ".doom" / "mcp_servers.json"
        self.sessions: dict[str, MCPServerSession] = {}

    def load_servers(self) -> None:
        if not self.config_file.exists():
            return
        try:
            # Using utf-8-sig strips any Windows/PowerShell UTF-8 BOM automatically
            content = self.config_file.read_text(encoding="utf-8-sig").strip()
            if not content:
                return
            data = json.loads(content)
            servers = data.get("mcpServers", {})
            for name, cfg in servers.items():
                cmd = cfg.get("command")
                args = cfg.get("args", [])
                env = cfg.get("env")
                if cmd:
                    session = MCPServerSession(name, cmd, args, env, cwd=self.workspace_root)
                    if session.start():
                        self.sessions[name] = session
        except Exception as e:
            print(f"[dim red]Error loading mcp_servers.json: {e}[/dim red]")

    def get_all_tools(self) -> list[dict[str, Any]]:
        all_tools = []
        for server_name, session in self.sessions.items():
            for tool in session.tools:
                t = dict(tool)
                t["server"] = server_name
                all_tools.append(t)
        return all_tools

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        for session in self.sessions.values():
            for t in session.tools:
                if t.get("name") == tool_name:
                    return session.call_tool(tool_name, arguments)
        return f"Tool '{tool_name}' not found on any active MCP server."

    def shutdown(self) -> None:
        for session in self.sessions.values():
            session.close()
        self.sessions.clear()