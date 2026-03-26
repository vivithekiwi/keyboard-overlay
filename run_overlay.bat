@echo off
echo ════════════════════════════════════════════
echo   Keyboard Overlay — Setup ^& Launch
echo ════════════════════════════════════════════
echo.

:: Check Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install from https://python.org
    echo         Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

:: Install dependency
echo Installing pynput...
pip install pynput --quiet
echo.

:: Launch
echo Launching overlay...  (right-click the overlay to quit)
echo.
python "%~dp0keyboard_overlay.py"
