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
    echo Download Python 3.11 or newer from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: Check that Python version is 3.11 or newer
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set PYMAJ=%%a
    set PYMIN=%%b
)
if %PYMAJ% neq 3 (
    echo ERROR: Python 3.11 or newer is required. Detected Python %PYVER%.
    echo Download Python from https://www.python.org/downloads/
    pause
    exit /b 1
)
if %PYMIN% lss 11 (
    echo ERROR: Python 3.11 or newer is required. Detected Python %PYVER%.
    echo Download Python from https://www.python.org/downloads/
    pause
    exit /b 1
)


echo [1/4] Upgrading pip to the latest version...
python -m pip install --upgrade pip
if %errorlevel% neq 0 (
    echo.
    echo WARNING: pip upgrade failed, continuing with existing pip version...
    echo.
)

echo.
echo [2/4] Installing pygame (binary only – no compilation)...
pip install --only-binary=pygame "pygame>=2.5.2"
if %errorlevel% neq 0 (
    echo.
    echo ERROR: pygame could not be installed as a binary wheel.
    echo This usually means your Python version does not have a pre-built pygame wheel.
    echo Supported Python versions for pygame on Windows: 3.11 and 3.12
    echo.
    echo Please install Python 3.12 from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation,
    echo then run this installer again.
    pause
    exit /b 1
)

echo.
echo [3/4] Installing remaining Python dependencies...
pip install --prefer-binary mss Pillow pytesseract numpy
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Dependency install failed.
    echo Download Python from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo.
echo [4/4] Generating default alert sound (sounds\alert.wav)...
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
echo NOTE: If you see install errors, ensure you are using Python 3.11 or newer.
echo Download Python from https://www.python.org/downloads/
echo.
pause
