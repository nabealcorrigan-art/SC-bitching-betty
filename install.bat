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
    echo Download Python 3.11+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [1/3] Installing Python dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)

echo.
echo [2/3] Generating default alert sound (sounds\alert.wav)...
python generate_default_sound.py

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
pause
