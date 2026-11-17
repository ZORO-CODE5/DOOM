@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo   DOOM - Sovereign Autonomous CLI Agent Installer
echo ===================================================
echo.

set "REPO_DIR=%~dp0"

:: 1. Verify Python 3.10+ is installed and present in PATH
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.10 or higher is required and must be present in your PATH.
    echo Please install Python 3.10+ from https://www.python.org/ and verify 'Add Python to PATH' is checked.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"') do set PYTHON_VERSION=%%v
echo [OK] Python %PYTHON_VERSION% detected.
echo.

:: 2. Initialize local virtual environment in repo
if not exist "%REPO_DIR%.venv\Scripts\python.exe" (
    echo [1/3] Initializing virtual environment in %REPO_DIR%.venv ...
    python -m venv "%REPO_DIR%.venv"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
) else (
    echo [1/3] Existing virtual environment found in %REPO_DIR%.venv.
)
echo.

:: 3. Upgrade pip and install all dependencies from requirements.txt
echo [2/3] Installing dependencies from requirements.txt ...
"%REPO_DIR%.venv\Scripts\python.exe" -m pip install --upgrade pip --quiet --retries 2 --timeout 15 2>nul
"%REPO_DIR%.venv\Scripts\python.exe" -m pip install -r "%REPO_DIR%requirements.txt" --quiet --retries 2 --timeout 15
if errorlevel 1 (
    echo [WARNING] Dependencies could not be updated online.
    echo Existing local packages in .venv will be used.
) else (
    echo [OK] All dependencies successfully installed.
)
echo.

:: 4. Register global launcher doom.cmd
echo [3/3] Registering global 'doom' command ...
set "TARGET_DIR=%LOCALAPPDATA%\Microsoft\WindowsApps"
set "LAUNCHER=%TARGET_DIR%\doom.cmd"

cmd /c "(echo @echo off & echo ""%REPO_DIR%.venv\Scripts\python.exe"" ""%REPO_DIR%main.py"" %%%%*) > ""%LAUNCHER%""" >nul 2>&1

if not exist "%LAUNCHER%" (
    set "TARGET_DIR=%USERPROFILE%\.local\bin"
    if not exist "!TARGET_DIR!" mkdir "!TARGET_DIR!" >nul 2>&1
    set "LAUNCHER=!TARGET_DIR!\doom.cmd"
    (
        echo @echo off
        echo "%REPO_DIR%.venv\Scripts\python.exe" "%REPO_DIR%main.py" %%*
    ) > "!LAUNCHER!" 2>nul
)

if not exist "%LAUNCHER%" (
    echo [ERROR] Failed to write launcher to %LAUNCHER%.
    pause
    exit /b 1
)

echo [OK] Global launcher registered at:
echo      %LAUNCHER%
echo.
echo ===================================================
echo   [SUCCESS] DOOM has been installed globally!
echo ===================================================
echo.
echo You can now open a new terminal in any project directory and run:
echo.
echo     doom
echo.
pause
