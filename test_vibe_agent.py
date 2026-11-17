"""Comprehensive automated verification suite for DOOM autonomous vibe-coding engine.

Tests:
1. Multi-file scaffolding & fallback parsing (tagged, untagged, extension heuristics).
2. Code sanitization (nested markdown indentation dedent, directive stripping).
3. Flexible execution directive parsing & deduplication.
4. Subprocess execution compatibility (dict vs dot attributes).
5. Autonomous error recovery loop with simulated runtime failures and self-healing.
6. Dynamic workspace context awareness.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

# Ensure parent directory is in python path
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))

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

from context import ProjectContext
from context_manager import TokenContextManager
from main import (
    execute_file_writes,
    extract_execute_commands,
    get_workspace_tree_summary,
    parse_all_file_blocks,
    run_autonomous_loop,
    sanitize_code_content,
)
from prompts import AUTONOMOUS_SYSTEM_PROMPT, get_initial_messages
from runner import CommandResult, CommandRunner
from snapshots import SnapshotManager


def test_multi_file_scaffolding_and_fallback():
    print("[TEST 1] Testing Multi-File Scaffolding & Fallback Parsing...")

    # Scenario A: Explicitly tagged multi-file output
    tagged_response = """
I have designed the modular architecture for DOOM:

[FILE: src/server.py]
```python
def start_server():
    print("Latverian Server Active")

if __name__ == '__main__':
    start_server()
```

[FILE: public/index.html]
```html
<!DOCTYPE html>
<html>
<head><title>DOOM UI</title></head>
<body><h1>Monarch Sovereign UI</h1></body>
</html>
```
"""
    files = parse_all_file_blocks(tagged_response, "Build full-stack server and UI")
    file_map = dict(files)
    assert "src/server.py" in file_map, "Failed to extract src/server.py"
    assert "public/index.html" in file_map, "Failed to extract public/index.html"
    assert "start_server" in file_map["src/server.py"]
    assert "Monarch Sovereign UI" in file_map["public/index.html"]

    # Scenario B: Untagged multi-file output (HTML + CSS + JS) with fallback parser
    untagged_fullstack_prompt = "Build a frontend application with index.html, styles.css, and app.js"
    untagged_response = """
Here is the HTML layout:
```html
<!DOCTYPE html>
<html lang="en">
<head><link rel="stylesheet" href="styles.css"></head>
<body><div id="app">Hello Doom</div></body>
</html>
```

Next, the accompanying stylesheet:
```css
body {
    background-color: #0a1f11;
    color: #e2e8f0;
}
```

Finally, the client logic:
```javascript
document.addEventListener("DOMContentLoaded", () => {
    console.log("Doom app initialized");
});
```
"""
    files_fb = parse_all_file_blocks(untagged_response, untagged_fullstack_prompt)
    fb_map = dict(files_fb)
    assert "index.html" in fb_map, f"Fallback parser missed index.html: {list(fb_map.keys())}"
    assert "styles.css" in fb_map, f"Fallback parser missed styles.css: {list(fb_map.keys())}"
    assert "app.js" in fb_map, f"Fallback parser missed app.js: {list(fb_map.keys())}"
    assert len(files_fb) == 3, f"Expected 3 distinct files, got {len(files_fb)}"
    # Verify no two files received the same code
    assert fb_map["index.html"] != fb_map["styles.css"]
    assert fb_map["styles.css"] != fb_map["app.js"]

    # Scenario C: Untagged Python module + Unit Tests
    python_prompt = "Create math_ops.py and test_math_ops.py"
    python_response = """
Here is the mathematical operations module:
```python
def power(base, exp):
    return base ** exp
```

And here are the unit tests for validation:
```python
import unittest
from math_ops import power

class TestPower(unittest.TestCase):
    def test_power(self):
        self.assertEqual(power(2, 3), 8)

if __name__ == '__main__':
    unittest.main()
```
"""
    py_files = parse_all_file_blocks(python_response, python_prompt)
    py_map = dict(py_files)
    assert "math_ops.py" in py_map, f"Missing math_ops.py: {list(py_map.keys())}"
    assert "test_math_ops.py" in py_map, f"Missing test_math_ops.py: {list(py_map.keys())}"
    assert "def power" in py_map["math_ops.py"]
    assert "TestPower" in py_map["test_math_ops.py"]

    print("  -> PASS: Multi-File Scaffolding & Fallback Parsing verified.")


def test_code_sanitization_and_syntax_preservation():
    print("[TEST 2] Testing Code Sanitization & Syntax Preservation...")

    # Nested markdown indentation test (e.g., 4 spaces inside markdown lists)
    nested_markdown_code = """
        def compute_tax(income):
            rate = 0.15
            return income * rate

        if __name__ == '__main__':
            print(compute_tax(1000))
    """
    sanitized = sanitize_code_content(nested_markdown_code)
    # Ensure it starts flush (no leading indentation on the def line)
    assert sanitized.startswith("def compute_tax"), f"Dedent failed: {repr(sanitized[:25])}"
    # Verify it compiles without IndentationError
    compiled = compile(sanitized, "<test>", "exec")
    assert compiled is not None, "Failed to compile dedented Python code"

    # Directive stripping test
    contaminated_code = """
def execute_pipeline():
    [EXECUTE: python run_pipeline.py]
    print("Pipeline step 1")
    # [FILE: dummy.txt]
    print("Pipeline step 2")
    ```EXECUTE: python test.py```
    return True
"""
    clean_code = sanitize_code_content(contaminated_code)
    assert "[EXECUTE:" not in clean_code, "Failed to strip [EXECUTE:] from code"
    assert "[FILE:" not in clean_code, "Failed to strip [FILE:] from code"
    assert "```EXECUTE" not in clean_code, "Failed to strip ```EXECUTE from code"
    # Ensure remaining code is syntactically valid
    compile(clean_code, "<clean_test>", "exec")

    print("  -> PASS: Code sanitization, dedenting, and directive stripping verified.")


def test_flexible_directive_parsing():
    print("[TEST 3] Testing Flexible Directive Parsing & Deduplication...")

    sample_response = """
To enact this decree, run these verification steps:

1. Standard square bracket:
[EXECUTE: python -m unittest test_app.py]

2. Code block fence directive:
```execute: pytest tests/test_backend.py```

3. Multiline execute block:
```execute
npm install
npm test
```

4. Plain text directive line outside code blocks:
EXECUTE: python verify.py

5. Duplicate directive (should be deduplicated):
[EXECUTE: python -m unittest test_app.py]
"""
    commands = extract_execute_commands(sample_response)
    expected = [
        "pytest tests/test_backend.py",
        "npm install",
        "npm test",
        "python -m unittest test_app.py",
        "python verify.py",
    ]
    # Verify all commands captured
    for exp in expected:
        assert exp in commands, f"Command '{exp}' not found in parsed commands: {commands}"

    # Verify duplicate was removed
    assert commands.count("python -m unittest test_app.py") == 1, "Duplicate command was not stripped!"
    # Verify order is preserved
    assert len(commands) == 5, f"Expected 5 distinct commands, got {len(commands)}: {commands}"

    print("  -> PASS: Flexible directive parsing and deduplication verified.")


def test_subprocess_compatibility_and_self_correction():
    print("[TEST 4] Testing Subprocess Compatibility & Self-Correction Loop...")

    temp_dir = Path(tempfile.mkdtemp(prefix="doom_test_workspace_"))
    try:
        context = ProjectContext(temp_dir)
        runner = CommandRunner(temp_dir)
        snapshots = SnapshotManager(temp_dir)
        token_mgr = TokenContextManager()
        palette = {
            "primary": "bold green",
            "dim": "dim green",
            "accent": "bold yellow",
            "metal": "bold white",
            "status_core": "bold cyan",
            "status_role": "bold yellow",
            "prompt": "bold green",
        }

        # Test CommandResult compatibility (both dict and dot attribute access)
        res_dict = CommandResult({
            "returncode": 0,
            "stdout": "Success Output",
            "stderr": "",
            "elapsed": 0.1,
            "timeout": False,
        })
        assert res_dict["stdout"] == "Success Output"
        assert res_dict.stdout == "Success Output"
        assert res_dict["returncode"] == 0
        assert res_dict.returncode == 0

        # Simulate Mock Ollama Client that demonstrates multi-turn self-correction
        class MockOllamaClient:
            def __init__(self):
                self.model_name = "doom-test-model"
                self.call_count = 0

            def stream_chat(self, messages):
                self.call_count += 1
                if self.call_count == 1:
                    # Turn 1: Emit a script with a deliberate bug and execution directive
                    yield """
[FILE: calculator.py]
```python
def divide(a, b):
    # Buggy: raises ZeroDivisionError on divide(10, 0)
    return a / b

if __name__ == '__main__':
    print("Result:", divide(10, 0))
```

[EXECUTE: python calculator.py]
"""
                elif self.call_count == 2:
                    # Turn 2: Model receives the ZeroDivisionError traceback and emits corrected file
                    yield """
[FILE: calculator.py]
```python
def divide(a, b):
    if b == 0:
        return "Cannot divide by zero"
    return a / b

if __name__ == '__main__':
    print("Result:", divide(10, 0))
```

[EXECUTE: python calculator.py]
"""
                else:
                    yield "All decrees completed."

        mock_client = MockOllamaClient()
        messages = get_initial_messages()

        final_response = run_autonomous_loop(
            user_task="Build a safe division calculator script",
            messages=messages,
            ollama_client=mock_client,
            runner=runner,
            context=context,
            snapshots=snapshots,
            token_mgr=token_mgr,
            palette=palette,
            max_turns=3,
        )

        assert mock_client.call_count == 2, f"Expected 2 turns for self-correction, got {mock_client.call_count}"
        calc_file = temp_dir / "calculator.py"
        assert calc_file.exists(), "calculator.py was not saved to disk"
        calc_content = calc_file.read_text(encoding="utf-8")
        assert "Cannot divide by zero" in calc_content, "Faulty code was not repaired by self-correction"

        print("  -> PASS: Subprocess compatibility and 2-turn self-correction verified.")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_dynamic_workspace_context_awareness():
    print("[TEST 5] Testing Dynamic Workspace Context Awareness...")

    temp_dir = Path(tempfile.mkdtemp(prefix="doom_tree_test_"))
    try:
        # Create some test files
        (temp_dir / "main.py").write_text("# main", encoding="utf-8")
        (temp_dir / "utils.py").write_text("# utils", encoding="utf-8")
        (temp_dir / "models").mkdir()
        (temp_dir / "models" / "user.py").write_text("# user", encoding="utf-8")

        # Create ignored dirs
        (temp_dir / ".git").mkdir()
        (temp_dir / ".git" / "config").write_text("# git", encoding="utf-8")
        (temp_dir / "__pycache__").mkdir()
        (temp_dir / "__pycache__" / "main.pyc").write_text("# pyc", encoding="utf-8")

        context = ProjectContext(temp_dir)
        summary = get_workspace_tree_summary(context, max_files=20)

        assert "[ACTIVE WORKSPACE FILE TREE]:" in summary
        assert "main.py" in summary
        assert "utils.py" in summary
        assert "models/user.py" in summary or "models\\user.py" in summary
        assert ".git" not in summary, "Ignored .git folder leaked into workspace tree"
        assert "__pycache__" not in summary, "Ignored __pycache__ leaked into workspace tree"

        print("  -> PASS: Dynamic workspace tree context awareness verified.")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    print("=" * 70)
    print("DOOM VIBE-CODING AUTONOMOUS AGENT VERIFICATION SUITE")
    print("=" * 70)
    try:
        test_multi_file_scaffolding_and_fallback()
        test_code_sanitization_and_syntax_preservation()
        test_flexible_directive_parsing()
        test_subprocess_compatibility_and_self_correction()
        test_dynamic_workspace_context_awareness()
        print("=" * 70)
        print("ALL TESTS PASSED WITH SOVEREIGN DISTINCTION! ⚜")
        print("=" * 70)
    except AssertionError as err:
        print(f"\n[FAIL] Test assertion failure: {err}")
        sys.exit(1)
    except Exception as ex:
        print(f"\n[ERROR] Unexpected error during verification: {ex}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
