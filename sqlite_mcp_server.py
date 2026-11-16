import json
import sqlite3
import sys
from pathlib import Path


def send_response(response: dict) -> None:
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()


def list_tables(db_path: str) -> str:
    path = Path(db_path)
    if not path.exists():
        return f"Error: Database file '{db_path}' not found."
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return json.dumps(tables)
    except Exception as e:
        return f"Database error: {e}"


def run_query(db_path: str, query: str) -> str:
    path = Path(db_path)
    if not path.exists():
        return f"Error: Database file '{db_path}' not found."
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        conn.close()
        return json.dumps({"columns": columns, "rows": rows})
    except Exception as e:
        return f"Execution error: {e}"


def main() -> None:
    tools = [
        {
            "name": "sqlite_list_tables",
            "description": "Lists all table names in a target SQLite database file.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "db_path": {"type": "string", "description": "Path to SQLite file"}
                },
                "required": ["db_path"],
            },
        },
        {
            "name": "sqlite_run_query",
            "description": "Executes a SELECT SQL query on a SQLite database.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "db_path": {"type": "string", "description": "Path to SQLite file"},
                    "query": {"type": "string", "description": "SQL query to run"},
                },
                "required": ["db_path", "query"],
            },
        },
    ]

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = req.get("method")
        msg_id = req.get("id")

        if method == "initialize":
            send_response({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "sqlite-local-mcp", "version": "1.0.0"},
                },
            })

        elif method == "notifications/initialized":
            pass

        elif method == "tools/list":
            send_response({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": tools},
            })

        elif method == "tools/call":
            params = req.get("params", {})
            name = params.get("name")
            arguments = params.get("arguments", {})

            if name == "sqlite_list_tables":
                out = list_tables(arguments.get("db_path", ""))
            elif name == "sqlite_run_query":
                out = run_query(arguments.get("db_path", ""), arguments.get("query", ""))
            else:
                out = f"Unknown tool: {name}"

            send_response({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": out}]
                },
            })


if __name__ == "__main__":
    main()