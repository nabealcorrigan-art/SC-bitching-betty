@echo off
title SC Bitching Betty – Installer
echo ============================================================
echo  SC Bitching Betty – Windows Installer
echo ============================================================
echo.

:: ── Check Python ────────────────────────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not on PATH.
    echo Download Python 3.11, 3.12, or 3.13 from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: Check that Python version is 3.11–3.13 (pygame has no wheels for 3.14+ yet)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set PYMAJ=%%a
    set PYMIN=%%b
)
if %PYMAJ% neq 3 (
    echo ERROR: Python 3.11, 3.12, or 3.13 is required. Detected Python %PYVER%.
    echo Download Python 3.13 from https://www.python.org/downloads/
    pause
    exit /b 1
)
if %PYMIN% lss 11 (
    echo ERROR: Python 3.11, 3.12, or 3.13 is required. Detected Python %PYVER%.
    echo Download Python 3.13 from https://www.python.org/downloads/
    pause
    exit /b 1
)
if %PYMIN% gtr 13 (
    echo ERROR: Python %PYVER% is not yet supported.
    echo pygame does not provide pre-built wheels for Python 3.14 or newer.
    echo Please install Python 3.13 from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [1/3] Installing Python dependencies...
pip install -r "%~dp0requirements.txt"
if %errorlevel% neq 0 (
    echo.
    echo ERROR: pip install failed.
    echo If pygame failed to install, ensure you are using Python 3.11, 3.12, or 3.13.
    echo Download Python 3.13 from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo.
echo [2/3] Generating default alert sound (sounds\alert.wav)...
python "%~dp0generate_default_sound.py"

echo.
echo [3/3] Done!
echo.
echo ============================================================
echo  IMPORTANT – Tesseract-OCR
echo ============================================================
echo  OCR features require Tesseract-OCR to be installed.
echo  Download the Windows installer from:
echo    https://github.com/UB-Mannheim/tesseract/wiki
echo  After installing, open SC Bitching Betty and set the path
echo  in File ^> Settings.
echo ============================================================
echo.
echo Run the application with:
echo    python betty.py
echo.
echo NOTE: If you see install errors, ensure you are using Python 3.11, 3.12, or 3.13.
echo Download Python 3.13 from https://www.python.org/downloads/
echo.
pause
