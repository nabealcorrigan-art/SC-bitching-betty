"""
selector.py – Interactive screen-region selector.

Captures a screenshot of the primary monitor, displays it in a
borderless full-screen tkinter window, and lets the user draw a
selection rectangle with the mouse.  The drawn rectangle has a red
outline and **no fill** so the underlying screen content remains fully
visible.  Returns the selected region as ``{"x", "y", "width",
"height"}``.
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


_OVERLAY_BG   = "#000001"   # near-black canvas background (fills any gap around the photo)
_RECT_COLOR   = "#ff3c3c"   # red outline for the drag rectangle
_RECT_FILL    = ""          # no fill – keep screen content visible
_RECT_WIDTH   = 2
_RECT_DASH    = (6, 4)
_BANNER_BG    = "#1a1a1a"
_BANNER_H     = 46
_INSTRUCTION  = (
    "Click and drag to select a region.  "
    "Press  Esc  or  right-click  to cancel."
)
_CONFIRM_INSTRUCTION = "Region selected!  Closing…"
_CONFIRM_DELAY_MS    = 1200   # ms to keep the confirmed selection visible


class RegionSelector:
    """
    Full-screen interactive region selector.

    Usage::

        selector = RegionSelector(master=root)
        region = selector.select()   # blocks until the user picks a region
        if region:
            print(region)  # {"x": 100, "y": 200, "width": 300, "height": 50}
    """

    def __init__(self, master: Optional[tk.Tk] = None) -> None:
        self._master = master
        self._region: Optional[Dict] = None
        self._start_x: Optional[int] = None
        self._start_y: Optional[int] = None
        self._rect_id: Optional[int] = None
        self._banner_text_id: Optional[int] = None
        self._root: Optional[tk.Misc] = None
        self._canvas: Optional[tk.Canvas] = None
        # Scale factors from canvas (logical) pixels to physical screen pixels,
        # and the primary monitor's offset in the virtual-desktop coordinate
        # system used by mss.
        self._scale_x: float = 1.0
        self._scale_y: float = 1.0
        self._monitor_left: int = 0
        self._monitor_top: int = 0

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

        self._region = None
        self._start_x = None
        self._start_y = None
        self._rect_id = None
        self._banner_text_id = None

        # ------------------------------------------------------------------
        # Create the overlay window (hidden) so we can query the real
        # logical screen dimensions before capturing the screenshot.
        # When a master Tk window already exists we must use Toplevel rather
        # than a second tk.Tk(), because ImageTk.PhotoImage is bound to the
        # first Tk interpreter and cannot be used with a separate one.
        # NOTE: Do NOT use -fullscreen together with overrideredirect – on
        # Windows the window manager no longer controls the window, so
        # -fullscreen has no effect and the window stays tiny.  Instead we
        # use an explicit geometry() call to position and size it ourselves.
        # ------------------------------------------------------------------
        if self._master is not None:
            self._root = tk.Toplevel(self._master)
        else:
            self._root = tk.Tk()
        self._root.withdraw()                  # hide while we set up
        self._root.overrideredirect(True)      # borderless
        self._root.attributes("-topmost", True)
        self._root.update_idletasks()          # flush pending geometry requests

        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()

        # Position the window to cover exactly the primary screen.
        self._root.geometry(f"{screen_w}x{screen_h}+0+0")
        self._root.config(cursor="crosshair")

        # ------------------------------------------------------------------
        # Capture the primary monitor and resize to logical screen dimensions.
        # mss returns physical pixels; on HiDPI/scaled displays these differ
        # from logical pixels reported by tkinter, so we resize rather than
        # crop to ensure the photo fills the canvas correctly.
        # ------------------------------------------------------------------
        capture = ScreenCapture()
        img = capture.capture_primary_screen()
        if img is None:
            self._root.destroy()
            messagebox.showerror(
                "Capture failed",
                "Could not capture the screen.\n"
                "Check that mss and Pillow are installed.",
            )
            return None

        # Record the physical pixel dimensions BEFORE any resize so we can
        # derive the scale factors needed to map canvas (logical) coordinates
        # back to physical screen coordinates when the user makes a selection.
        phys_w, phys_h = img.width, img.height
        self._scale_x = phys_w / screen_w if screen_w > 0 else 1.0
        self._scale_y = phys_h / screen_h if screen_h > 0 else 1.0

        # Retrieve the primary monitor's virtual-desktop offset.  mss uses
        # absolute physical coordinates, so we must add this offset when the
        # stored region is later passed back to capture_region().
        self._monitor_left = 0
        self._monitor_top = 0
        try:
            import mss as _mss
            with _mss.mss() as _sct:
                _primary = _sct.monitors[1]
                self._monitor_left = _primary["left"]
                self._monitor_top = _primary["top"]
        except Exception:
            pass

        if img.width != screen_w or img.height != screen_h:
            img = img.resize((screen_w, screen_h), Image.LANCZOS)

        photo = ImageTk.PhotoImage(img)

        self._canvas = tk.Canvas(
            self._root,
            width=screen_w,
            height=screen_h,
            cursor="crosshair",
            highlightthickness=0,
            bg=_OVERLAY_BG,
        )
        self._canvas.pack(fill="both", expand=True)
        self._canvas.create_image(0, 0, anchor="nw", image=photo)
        self._canvas.photo = photo  # prevent GC

        # Instruction banner at the top.
        self._canvas.create_rectangle(
            0, 0, screen_w, _BANNER_H, fill=_BANNER_BG, outline=""
        )
        self._banner_text_id = self._canvas.create_text(
            screen_w // 2,
            _BANNER_H // 2,
            text=_INSTRUCTION,
            fill="white",
            font=("Segoe UI", 13, "bold"),
        )

        self._canvas.bind("<ButtonPress-1>",   self._on_press)
        self._canvas.bind("<B1-Motion>",       self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        self._canvas.bind("<ButtonPress-3>",   self._on_cancel)
        self._root.bind("<Escape>",            self._on_cancel)

        # Show the window and grab all input so drag events are never lost.
        self._root.deiconify()
        self._root.focus_force()
        self._root.grab_set()

        # wait_window blocks until _close() destroys the Toplevel/Tk window,
        # which works correctly whether _root is a Toplevel or a standalone Tk.
        if self._master is not None:
            self._master.wait_window(self._root)
        else:
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

        # Convert from canvas (logical) pixels to physical screen coordinates.
        # The canvas was scaled down from physical pixels when the screenshot
        # was resized to fit the logical screen dimensions.  mss expects
        # absolute physical coordinates, so we scale back up and add the
        # primary monitor's virtual-desktop offset.
        phys_x1 = int(x1 * self._scale_x) + self._monitor_left
        phys_y1 = int(y1 * self._scale_y) + self._monitor_top
        phys_x2 = int(x2 * self._scale_x) + self._monitor_left
        phys_y2 = int(y2 * self._scale_y) + self._monitor_top

        self._region = {
            "x": phys_x1,
            "y": phys_y1,
            "width": phys_x2 - phys_x1,
            "height": phys_y2 - phys_y1,
        }

        # Replace the dashed drag rectangle with a solid confirmed outline and
        # update the banner so the user can see the region before the overlay
        # closes.
        if self._rect_id is not None:
            self._canvas.delete(self._rect_id)
        self._rect_id = self._canvas.create_rectangle(
            x1, y1, x2, y2,
            outline=_RECT_COLOR,
            width=3,
        )
        if self._banner_text_id:
            self._canvas.itemconfig(
                self._banner_text_id, text=_CONFIRM_INSTRUCTION
            )
        self._canvas.unbind("<ButtonPress-1>")
        self._canvas.unbind("<B1-Motion>")
        self._canvas.unbind("<ButtonRelease-1>")
        self._root.unbind("<Escape>")

        # Close after a short delay so the user can see the selection.
        self._root.after(_CONFIRM_DELAY_MS, self._close)

    def _on_cancel(self, event: tk.Event = None) -> None:
        self._region = None
        self._close()

    def _close(self) -> None:
        if self._root is not None:
            self._root.destroy()
            self._root = None
