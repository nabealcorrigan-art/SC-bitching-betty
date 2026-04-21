"""
capture.py – Screen-region capture utilities.

Uses *mss* for fast, cross-monitor screen capture and returns
``PIL.Image`` objects suitable for both OCR and colour analysis.
"""

from __future__ import annotations

from typing import Dict, Optional

try:
    import mss
    import mss.tools
    _MSS_AVAILABLE = True
except ImportError:
    _MSS_AVAILABLE = False

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


class ScreenCapture:
    """Captures a rectangular region of the screen."""

    def capture_region(self, region: Dict) -> Optional["Image.Image"]:
        """
        Capture *region* and return a ``PIL.Image`` in RGB mode.

        Parameters
        ----------
        region:
            ``{"x": int, "y": int, "width": int, "height": int}``
            in screen pixels (top-left origin).

        Returns
        -------
        ``PIL.Image`` or ``None`` if capture fails.
        """
        if not _MSS_AVAILABLE or not _PIL_AVAILABLE:
            return None

        try:
            with mss.mss() as sct:
                monitor_area = {
                    "left": int(region["x"]),
                    "top": int(region["y"]),
                    "width": max(1, int(region["width"])),
                    "height": max(1, int(region["height"])),
                }
                screenshot = sct.grab(monitor_area)
                img = Image.frombytes(
                    "RGB", screenshot.size, screenshot.rgb
                )
                return img
        except Exception:
            return None

    def capture_primary_screen(self) -> Optional["Image.Image"]:
        """
        Capture only the primary monitor.

        ``mss.monitors`` always starts with the virtual desktop at index 0,
        followed by each physical monitor starting at index 1.  Index 1 is
        always the primary monitor.

        Returns
        -------
        ``PIL.Image`` or ``None``.
        """
        if not _MSS_AVAILABLE or not _PIL_AVAILABLE:
            return None

        try:
            with mss.mss() as sct:
                # monitors[0] = virtual desktop, monitors[1] = primary monitor.
                # mss guarantees at least two entries whenever a display is present.
                primary = sct.monitors[1]
                screenshot = sct.grab(primary)
                img = Image.frombytes(
                    "RGB", screenshot.size, screenshot.rgb
                )
                return img
        except Exception:
            return None

    def capture_full_screen(self) -> Optional["Image.Image"]:
        """
        Capture the entire virtual desktop (all monitors combined).

        Returns
        -------
        ``PIL.Image`` or ``None``.
        """
        if not _MSS_AVAILABLE or not _PIL_AVAILABLE:
            return None

        try:
            with mss.mss() as sct:
                # monitors[0] is the virtual screen spanning all monitors.
                screenshot = sct.grab(sct.monitors[0])
                img = Image.frombytes(
                    "RGB", screenshot.size, screenshot.rgb
                )
                return img
        except Exception:
            return None
