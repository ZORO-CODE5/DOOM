#!/usr/bin/env bash
set -e

echo "==================================================="
echo "  DOOM - Sovereign Autonomous CLI Agent Installer"
echo "==================================================="
echo ""

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. Detect Python 3.10+
PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "[ERROR] Python 3 was not found in PATH. Please install Python 3.10+."
    exit 1
fi

$PYTHON_BIN -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null || {
    echo "[ERROR] Python 3.10 or higher is required."
    exit 1
}

PY_VER="$($PYTHON_BIN -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")"
echo "[OK] Python $PY_VER detected."
echo ""

# 2. Initialize local virtual environment inside repository
VENV_DIR="$REPO_DIR/.venv"
if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "[1/3] Initializing virtual environment in $VENV_DIR ..."
    $PYTHON_BIN -m venv "$VENV_DIR"
    echo "[OK] Virtual environment created."
else
    echo "[1/3] Existing virtual environment found in $VENV_DIR."
fi
echo ""

# 3. Upgrade pip and install requirements
echo "[2/3] Installing dependencies from requirements.txt ..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip --quiet --retries 2 --timeout 15 2>/dev/null || true
if "$VENV_DIR/bin/python" -m pip install -r "$REPO_DIR/requirements.txt" --quiet --retries 2 --timeout 15; then
    echo "[OK] All dependencies successfully installed."
else
    echo "[WARNING] Some dependencies could not be fetched (offline or proxy)."
    echo "Existing local packages in .venv will be used."
fi
echo ""

# 4. Create global wrapper script in ~/.local/bin/doom
echo "[3/3] Registering global 'doom' command ..."
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"

LAUNCHER="$BIN_DIR/doom"
cat << EOF > "$LAUNCHER"
#!/usr/bin/env bash
exec "$VENV_DIR/bin/python" "$REPO_DIR/main.py" "\$@"
EOF
chmod +x "$LAUNCHER"

# 5. Ensure ~/.local/bin is in PATH in shell configuration
PATH_EXPORT='export PATH="$HOME/.local/bin:$PATH"'
SHELL_NAME="$(basename "${SHELL:-bash}")"

if [ "$SHELL_NAME" = "zsh" ]; then
    RC_FILE="$HOME/.zshrc"
else
    RC_FILE="$HOME/.bashrc"
fi

if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    if [ -f "$RC_FILE" ]; then
        if ! grep -q '\.local/bin' "$RC_FILE" 2>/dev/null; then
            echo "" >> "$RC_FILE"
            echo "# Added by DOOM installer" >> "$RC_FILE"
            echo "$PATH_EXPORT" >> "$RC_FILE"
            echo "[NOTICE] Added ~/.local/bin to $RC_FILE."
        fi
    else
        echo "$PATH_EXPORT" >> "$RC_FILE"
    fi
    echo "[NOTICE] Run 'source $RC_FILE' or open a new terminal to use 'doom'."
fi

echo ""
echo "==================================================="
echo "  [SUCCESS] DOOM has been installed globally!"
echo "==================================================="
echo ""
echo "Launcher created: $LAUNCHER"
echo "Target repo:     $REPO_DIR"
echo ""
echo "You can now open any terminal in any directory and run:"
echo ""
echo "    doom"
echo ""
