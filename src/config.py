"""
config.py – Persistent JSON configuration for SC Bitching Betty.

Saves and loads global settings (Tesseract path, default sound file)
and the list of configured monitors.
"""

from __future__ import annotations

import json
import os
from typing import Dict, List

from src.monitor_model import Monitor

_DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "config.json"
)


class ConfigManager:
    """Read/write ``config.json`` next to the project root."""

    def __init__(self, path: str = _DEFAULT_CONFIG_PATH) -> None:
        self._path = path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> Dict:
        """
        Load configuration from disk.

        Returns a dict with keys:
          - ``"settings"``  – global settings dict
          - ``"monitors"``  – list of ``Monitor`` objects
        """
        default = self._default()
        if not os.path.isfile(self._path):
            return default

        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            return default

        monitors = [
            Monitor.from_dict(m)
            for m in data.get("monitors", [])
        ]
        settings = {**default["settings"], **data.get("settings", {})}
        return {"settings": settings, "monitors": monitors}

    def save(self, settings: Dict, monitors: List[Monitor]) -> None:
        """
        Persist *settings* and *monitors* to disk.

        Parameters
        ----------
        settings: Global settings dict.
        monitors: List of ``Monitor`` objects.
        """
        data = {
            "settings": settings,
            "monitors": [m.to_dict() for m in monitors],
        }
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    @staticmethod
    def _default() -> Dict:
        return {
            "settings": {
                "tesseract_cmd": "",
                "default_sound_file": "",
            },
            "monitors": [],
        }
