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
    echo Download Python 3.8 or newer from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: Check that Python version is 3.8 or newer (winsound is stdlib – no
:: special Python version needed for audio playback any more)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set PYMAJ=%%a
    set PYMIN=%%b
)
if %PYMAJ% neq 3 (
    echo ERROR: Python 3.8 or newer is required. Detected Python %PYVER%.
    echo Download Python from https://www.python.org/downloads/
    pause
    exit /b 1
)
if %PYMIN% lss 8 (
    echo ERROR: Python 3.8 or newer is required. Detected Python %PYVER%.
    echo Download Python from https://www.python.org/downloads/
    pause
    exit /b 1
)


echo [1/3] Upgrading pip to the latest version...
python -m pip install --upgrade pip
if %errorlevel% neq 0 (
    echo.
    echo WARNING: pip upgrade failed, continuing with existing pip version...
    echo.
)

echo.
echo [2/3] Installing Python dependencies...
pip install --prefer-binary mss Pillow pytesseract numpy
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Dependency install failed.
    echo Download Python from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo.
echo [3/3] Generating default alert sound (sounds\alert.wav)...
python "%~dp0generate_default_sound.py"

echo.
echo Done!
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
echo NOTE: Sound playback uses Python's built-in winsound module –
echo no additional audio packages are required.
echo.
pause
