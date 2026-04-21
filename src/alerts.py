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
    monitoring loop.  A lock ensures that at most one sound plays at a
    time; if a play is already in progress the new request is silently
    skipped, preventing the crash that occurs when ``winsound.PlaySound``
    is called concurrently from multiple threads.
    """

    def __init__(self) -> None:
        # Non-blocking: if the lock is held (sound already playing) the
        # new play request is dropped rather than queued.
        self._play_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def play(self, sound_file: str) -> None:
        """
        Play *sound_file* asynchronously.

        Silently does nothing if the audio backend is unavailable, the
        file does not exist, or the file cannot be loaded.  Only ``.wav``
        files are supported.  If a sound is already playing, this call
        is a no-op so alerts never stack up.
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
        if not self._play_lock.acquire(blocking=False):
            # Another thread is already playing – skip this request.
            return
        try:
            if _BACKEND == "winsound":
                try:
                    _winsound.PlaySound(
                        sound_file,
                        _winsound.SND_FILENAME | _winsound.SND_NODEFAULT,
                    )
                except Exception:
                    pass
        finally:
            self._play_lock.release()
