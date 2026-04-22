"""
alerts.py – Sound alert playback.

Uses *pygame.mixer* to play ``.wav`` sound files concurrently so that
multiple alerts can play at the same time.  Falls back to the
standard-library *winsound* module (Windows-only, single sound at a
time) when pygame is unavailable, and degrades to a silent no-op on
platforms where neither backend is usable.
"""

from __future__ import annotations

import os
import sys
import threading

# Prefer pygame for concurrent multi-channel mixing.
try:
    import pygame as _pygame
    _pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=512)
    _pygame.mixer.init()
    _BACKEND = "pygame"
except Exception:
    _pygame = None  # type: ignore[assignment]
    # Fall back to winsound (Windows only, single-sound-at-a-time).
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

# Protect winsound (non-reentrant) with a lock; pygame doesn't need one.
_winsound_lock = threading.Lock()


class AlertManager:
    """
    Plays sound files when an alert is triggered.

    When the *pygame* backend is active each sound is loaded into a
    ``pygame.mixer.Sound`` object and played on a free mixer channel,
    allowing multiple alerts to overlap.  The *winsound* fallback still
    plays one sound at a time (skipping concurrent requests) because
    ``winsound.PlaySound`` is not re-entrant.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def play(self, sound_file: str) -> None:
        """
        Play *sound_file* asynchronously.

        Silently does nothing if the audio backend is unavailable, the
        file does not exist, or the file cannot be loaded.  Only ``.wav``
        files are supported.  Multiple calls may overlap when the pygame
        backend is active.
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
        if _BACKEND == "pygame":
            try:
                sound = _pygame.mixer.Sound(sound_file)
                channel = sound.play()
                if channel is not None:
                    # Block this thread until playback finishes so the
                    # daemon thread lifetime matches the sound duration.
                    while channel.get_busy():
                        _pygame.time.wait(100)
            except Exception:
                pass
        elif _BACKEND == "winsound":
            if not _winsound_lock.acquire(blocking=False):
                # winsound is not re-entrant – skip if busy.
                return
            try:
                _winsound.PlaySound(
                    sound_file,
                    _winsound.SND_FILENAME | _winsound.SND_NODEFAULT,
                )
            except Exception:
                pass
            finally:
                _winsound_lock.release()
