#!/usr/bin/env python3
"""
SC Bitching Betty – Audible alert tool for Star Citizen.

Monitors selected screen regions via OCR and colour recognition,
then plays a configurable sound file when user-defined thresholds
are met.

Usage
-----
    python betty.py

Requirements
------------
    pip install -r requirements.txt
    # Windows: also install Tesseract-OCR from
    #   https://github.com/UB-Mannheim/tesseract/wiki
"""

import sys
import os

# Ensure the project root is on the path so `src` is importable.
sys.path.insert(0, os.path.dirname(__file__))

from src.app import BettyApp

if __name__ == "__main__":
    app = BettyApp()
    app.run()
