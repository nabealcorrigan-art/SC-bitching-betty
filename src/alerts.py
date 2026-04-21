"""
alerts.py – Sound alert playback.

Uses the standard-library *winsound* module (Windows) to play ``.wav``
sound files in a non-blocking way via a daemon thread.  Falls back to a
silent no-op on non-Windows platforms so the rest of the application
keeps working.
"""

from __future__ import annotations

import os
import sys
import threading

# winsound is part of the Python standard library on Windows – no
# third-party packages required.
if sys.platform == "win32":
    try:
        import winsound as _winsound
        _BACKEND = "winsound"
    except ImportError:
        _winsound = None  # type: ignore[assignment]
        _BACKEND = "none"
else:
    _winsound = None  # type: ignore[assignment]
    _BACKEND = "none"


class AlertManager:
    """
    Plays sound files when an alert is triggered.

    The sound is played on a daemon thread so it never blocks the
    monitoring loop.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def play(self, sound_file: str) -> None:
        """
        Play *sound_file* asynchronously.

        Silently does nothing if the audio backend is unavailable, the
        file does not exist, or the file cannot be loaded.  Only ``.wav``
        files are supported.
        """
        if not sound_file or not os.path.isfile(sound_file):
            return
        thread = threading.Thread(
            target=self._play_blocking,
            args=(sound_file,),
            daemon=True,
        )
        thread.start()

    @property
    def available(self) -> bool:
        """``True`` when a sound backend is usable."""
        return _BACKEND != "none"

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _play_blocking(self, sound_file: str) -> None:
        """Play the sound file, blocking the calling thread until done."""
        if _BACKEND == "winsound":
            try:
                _winsound.PlaySound(
                    sound_file,
                    _winsound.SND_FILENAME | _winsound.SND_NODEFAULT,
                )
            except Exception:
                pass
