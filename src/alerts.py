"""
alerts.py – Sound alert playback.

Uses *pygame.mixer* to play `.wav` / `.ogg` sound files in a
non-blocking way.  Falls back to a silent no-op if pygame is not
installed so the rest of the application keeps working.
"""

from __future__ import annotations

import os
import threading
from typing import Dict, Optional

try:
    import pygame
    import pygame.mixer
    _PYGAME_AVAILABLE = True
except ImportError:
    _PYGAME_AVAILABLE = False


_INIT_LOCK = threading.Lock()
_MIXER_READY = False


def _ensure_mixer() -> bool:
    """Initialise pygame.mixer once, thread-safely.  Returns readiness."""
    global _MIXER_READY
    if _MIXER_READY:
        return True
    if not _PYGAME_AVAILABLE:
        return False
    with _INIT_LOCK:
        if _MIXER_READY:
            return True
        try:
            pygame.mixer.pre_init(frequency=44100, size=-16,
                                  channels=2, buffer=512)
            pygame.mixer.init()
            _MIXER_READY = True
            return True
        except Exception:
            return False


class AlertManager:
    """
    Plays sound files when an alert is triggered.

    The sound is played on a daemon thread so it never blocks the
    monitoring loop.
    """

    def __init__(self) -> None:
        self._cache: Dict[str, "pygame.mixer.Sound"] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def play(self, sound_file: str) -> None:
        """
        Play *sound_file* asynchronously.

        Silently does nothing if pygame is unavailable, the file does
        not exist, or the file cannot be loaded.
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
        """``True`` when pygame.mixer is usable."""
        return _ensure_mixer()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _play_blocking(self, sound_file: str) -> None:
        """Load (or re-use from cache) and play the sound file."""
        if not _ensure_mixer():
            return
        try:
            sound = self._load(sound_file)
            if sound is not None:
                sound.play()
        except Exception:
            pass

    def _load(self, sound_file: str) -> Optional["pygame.mixer.Sound"]:
        """Return a cached or freshly loaded ``pygame.mixer.Sound``."""
        if sound_file in self._cache:
            return self._cache[sound_file]
        try:
            sound = pygame.mixer.Sound(sound_file)
            self._cache[sound_file] = sound
            return sound
        except Exception:
            return None
