"""
selector.py – Interactive screen-region selector.

Grabs a full-screen screenshot, displays it in a full-screen tkinter
window, and lets the user draw a selection rectangle with the mouse.
Returns the selected region as ``{"x", "y", "width", "height"}``.
"""

from __future__ import annotations

from typing import Dict, Optional

import tkinter as tk
from tkinter import messagebox

try:
    from PIL import Image, ImageTk
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

from src.capture import ScreenCapture


_OVERLAY_COLOR = "#000000"
_RECT_COLOR = "#ff3c3c"
_RECT_DASH = (6, 4)
_INSTRUCTION = (
    "Click and drag to select a region.  "
    "Press  Esc  or  right-click  to cancel."
)


class RegionSelector:
    """
    Full-screen interactive region selector.

    Usage::

        selector = RegionSelector()
        region = selector.select()   # blocks until the user picks a region
        if region:
            print(region)  # {"x": 100, "y": 200, "width": 300, "height": 50}
    """

    def __init__(self) -> None:
        self._region: Optional[Dict] = None
        self._start_x: Optional[int] = None
        self._start_y: Optional[int] = None
        self._rect_id: Optional[int] = None
        self._root: Optional[tk.Tk] = None
        self._canvas: Optional[tk.Canvas] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def select(self) -> Optional[Dict]:
        """
        Display the region-selector overlay and wait for user input.

        Returns
        -------
        Dict with keys ``x``, ``y``, ``width``, ``height`` or ``None``
        if the user cancelled.
        """
        if not _PIL_AVAILABLE:
            messagebox.showerror(
                "Missing dependency",
                "Pillow is required for region selection.\n"
                "Run:  pip install Pillow",
            )
            return None

        capture = ScreenCapture()
        img = capture.capture_full_screen()
        if img is None:
            messagebox.showerror(
                "Capture failed",
                "Could not capture the screen.\n"
                "Check that mss and Pillow are installed.",
            )
            return None

        self._region = None
        self._start_x = None
        self._start_y = None
        self._rect_id = None

        self._root = tk.Tk()
        self._root.overrideredirect(True)          # no window chrome
        self._root.attributes("-fullscreen", True)
        self._root.attributes("-topmost", True)
        self._root.config(cursor="crosshair")

        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()

        # Resize screenshot to primary screen if needed (multi-monitor
        # virtual desktops can be wider/taller than the primary).
        if img.width != screen_w or img.height != screen_h:
            img = img.crop((0, 0, min(img.width, screen_w),
                            min(img.height, screen_h)))

        photo = ImageTk.PhotoImage(img)

        self._canvas = tk.Canvas(
            self._root,
            width=screen_w,
            height=screen_h,
            cursor="crosshair",
            highlightthickness=0,
            bg=_OVERLAY_COLOR,
        )
        self._canvas.pack(fill="both", expand=True)
        self._canvas.create_image(0, 0, anchor="nw", image=photo)
        self._canvas.photo = photo  # prevent GC

        # Instruction banner at the top.
        self._canvas.create_rectangle(
            0, 0, screen_w, 46, fill="#1a1a1a", outline=""
        )
        self._canvas.create_text(
            screen_w // 2,
            23,
            text=_INSTRUCTION,
            fill="white",
            font=("Segoe UI", 13, "bold"),
        )

        self._canvas.bind("<ButtonPress-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        self._canvas.bind("<ButtonPress-3>", self._on_cancel)
        self._root.bind("<Escape>", self._on_cancel)

        self._root.mainloop()
        return self._region

    # ------------------------------------------------------------------
    # Private event handlers
    # ------------------------------------------------------------------

    def _on_press(self, event: tk.Event) -> None:
        self._start_x = event.x
        self._start_y = event.y
        if self._rect_id is not None:
            self._canvas.delete(self._rect_id)
            self._rect_id = None

    def _on_drag(self, event: tk.Event) -> None:
        if self._start_x is None:
            return
        if self._rect_id is not None:
            self._canvas.delete(self._rect_id)
        self._rect_id = self._canvas.create_rectangle(
            self._start_x,
            self._start_y,
            event.x,
            event.y,
            outline=_RECT_COLOR,
            width=2,
            dash=_RECT_DASH,
        )

    def _on_release(self, event: tk.Event) -> None:
        if self._start_x is None:
            return
        x1 = min(self._start_x, event.x)
        y1 = min(self._start_y, event.y)
        x2 = max(self._start_x, event.x)
        y2 = max(self._start_y, event.y)

        # Ignore tiny accidental clicks.
        if x2 - x1 < 5 or y2 - y1 < 5:
            return

        self._region = {
            "x": x1,
            "y": y1,
            "width": x2 - x1,
            "height": y2 - y1,
        }
        self._close()

    def _on_cancel(self, event: tk.Event = None) -> None:
        self._region = None
        self._close()

    def _close(self) -> None:
        if self._root is not None:
            self._root.destroy()
            self._root = None
