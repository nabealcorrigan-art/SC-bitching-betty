"""
overlay.py – Region outline overlay windows.

Displays a borderless, always-on-top window over each monitored screen
region so the user can see exactly which area is being observed at a glance.
Only the outline border is shown; the interior is fully transparent.
"""

from __future__ import annotations

import tkinter as tk
from typing import Dict, List, Optional, Tuple

from src.monitor_model import Monitor

try:
    import mss as _mss_mod
    _MSS_AVAILABLE = True
except ImportError:
    _MSS_AVAILABLE = False

_TRANSPARENT_KEY    = "#010101"     # window bg colour made invisible via -transparentcolor
_BORDER_COLOR       = "#00ccff"     # cyan outline colour
_BORDER_WIDTH       = 3
_MIN_OVERLAY_DIM    = 10            # minimum overlay width/height in logical pixels


class _SingleOverlay:
    """One outline-only overlay window highlighting a single screen region."""

    def __init__(
        self,
        root: tk.Misc,
        region: Dict,
        scale_x: float,
        scale_y: float,
    ) -> None:
        self._root = root
        self._scale_x = scale_x
        self._scale_y = scale_y
        self._win: Optional[tk.Toplevel] = None
        self._canvas: Optional[tk.Canvas] = None
        self._build(region)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _to_logical(self, region: Dict) -> Tuple[int, int, int, int]:
        """Convert physical-pixel region dict to logical (tkinter) pixel tuple."""
        lx = int(region["x"] / self._scale_x)
        ly = int(region["y"] / self._scale_y)
        lw = max(_MIN_OVERLAY_DIM, int(region["width"] / self._scale_x))
        lh = max(_MIN_OVERLAY_DIM, int(region["height"] / self._scale_y))
        return lx, ly, lw, lh

    def _build(self, region: Dict) -> None:
        lx, ly, lw, lh = self._to_logical(region)

        self._win = tk.Toplevel(self._root)
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)

        self._win.geometry(f"{lw}x{lh}+{lx}+{ly}")

        # Make the background colour fully transparent so only the border is
        # visible.  -transparentcolor is supported on Windows; on other
        # platforms we fall back to a very low alpha so the outline is still
        # clearly visible while the interior is nearly invisible.
        try:
            self._win.attributes("-transparentcolor", _TRANSPARENT_KEY)
        except tk.TclError:
            try:
                self._win.attributes("-alpha", 0.6)
            except tk.TclError:
                pass

        self._canvas = tk.Canvas(
            self._win,
            width=lw,
            height=lh,
            bg=_TRANSPARENT_KEY,
            highlightthickness=0,
        )
        self._canvas.pack()
        self._draw(lw, lh)

    def _draw(self, lw: int, lh: int) -> None:
        """Populate canvas items (border)."""
        bw = _BORDER_WIDTH
        # Border rectangle
        self._canvas.create_rectangle(
            bw, bw, lw - bw, lh - bw,
            outline=_BORDER_COLOR,
            width=bw,
            fill="",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, region: Dict) -> None:
        """Reposition and resize the overlay to match a new region."""
        if self._win is None:
            self._build(region)
            return
        lx, ly, lw, lh = self._to_logical(region)
        self._win.geometry(f"{lw}x{lh}+{lx}+{ly}")
        self._canvas.config(width=lw, height=lh)
        self._canvas.delete("all")
        self._draw(lw, lh)

    def destroy(self) -> None:
        """Remove the overlay window from the screen."""
        if self._win is not None:
            try:
                self._win.destroy()
            except Exception:
                pass
            self._win = None
            self._canvas = None


class RegionOverlayManager:
    """
    Manages a set of semi-transparent overlay windows – one per enabled monitor.

    Usage::

        manager = RegionOverlayManager(root)
        manager.show(monitors)   # call when monitoring starts
        manager.hide()           # call when monitoring stops
    """

    def __init__(self, root: tk.Misc) -> None:
        self._root = root
        self._overlays: Dict[str, _SingleOverlay] = {}
        self._scale_x, self._scale_y = self._compute_scale()

    # ------------------------------------------------------------------

    def _compute_scale(self) -> Tuple[float, float]:
        """Return (scale_x, scale_y) mapping physical→logical pixels."""
        if not _MSS_AVAILABLE:
            return 1.0, 1.0
        try:
            with _mss_mod.mss() as sct:
                primary = sct.monitors[1]
                phys_w: int = primary["width"]
                phys_h: int = primary["height"]
            log_w = self._root.winfo_screenwidth()
            log_h = self._root.winfo_screenheight()
            sx = phys_w / log_w if log_w > 0 else 1.0
            sy = phys_h / log_h if log_h > 0 else 1.0
            return sx, sy
        except Exception:
            return 1.0, 1.0

    # ------------------------------------------------------------------

    def show(self, monitors: List[Monitor]) -> None:
        """
        Display an overlay for every enabled monitor in *monitors*.

        Any previously shown overlays are destroyed first.
        """
        self.hide()
        # Recompute scale in case display configuration changed.
        self._scale_x, self._scale_y = self._compute_scale()
        for m in monitors:
            if not m.enabled:
                continue
            self._overlays[m.id] = _SingleOverlay(
                self._root,
                m.region,
                scale_x=self._scale_x,
                scale_y=self._scale_y,
            )

    def hide(self) -> None:
        """Destroy all overlay windows."""
        for ov in self._overlays.values():
            ov.destroy()
        self._overlays.clear()
