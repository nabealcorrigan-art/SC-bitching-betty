"""
app.py – Main tkinter application window for SC Bitching Betty.

Layout
------
┌─────────────────────────────────────────────────┐
│  SC Bitching Betty                              │
│  ┌──────────────┐  ┌──────────────────────────┐ │
│  │ Monitors     │  │ [Add] [Edit] [Remove]    │ │
│  │ listbox      │  │                          │ │
│  │              │  │ [▶ Start] [■ Stop]       │ │
│  └──────────────┘  └──────────────────────────┘ │
│  ┌─────────────────────────────────────────────┐ │
│  │ Settings tab                                │ │
│  └─────────────────────────────────────────────┘ │
│  Status: Idle                    ■ x monitors    │
└─────────────────────────────────────────────────┘
"""

from __future__ import annotations

import copy
import os
import tkinter as tk
from tkinter import (
    colorchooser,
    filedialog,
    messagebox,
    simpledialog,
    ttk,
)
from typing import Dict, List, Optional

from src.monitor_model import ColorConfig, Monitor, OcrConfig
from src.capture import ScreenCapture
from src.selector import RegionSelector
from src.ocr import OcrReader
from src.colors import ColorDetector
from src.alerts import AlertManager
from src.config import ConfigManager
from src.engine import MonitoringEngine


# ---------------------------------------------------------------------------
# Helper – small icon square for a colour swatch
# ---------------------------------------------------------------------------

_MIN_REGION_DIMENSION = 1


def _rgb_to_hex(rgb: List[int]) -> str:
    r, g, b = (max(0, min(255, c)) for c in rgb[:3])
    return f"#{r:02x}{g:02x}{b:02x}"


# ===========================================================================
# Monitor edit dialog
# ===========================================================================

class MonitorDialog(tk.Toplevel):
    """Modal dialog for adding / editing a Monitor."""

    def __init__(self, parent: tk.Widget, monitor: Optional[Monitor] = None,
                 default_sound: str = "") -> None:
        super().__init__(parent)
        self.title("Edit Monitor" if monitor else "Add Monitor")
        self.resizable(False, False)
        self.grab_set()

        self.result: Optional[Monitor] = None
        self._monitor = monitor or Monitor()
        self._default_sound = default_sound

        self._build()
        self._populate()
        self.wait_window()

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build(self) -> None:
        pad = {"padx": 8, "pady": 4}

        # ── Name ──────────────────────────────────────────────────────
        row = ttk.Frame(self)
        row.pack(fill="x", **pad)
        ttk.Label(row, text="Name:", width=16, anchor="e").pack(side="left")
        self._name_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._name_var, width=32).pack(
            side="left", padx=(4, 0)
        )

        # ── Enabled ───────────────────────────────────────────────────
        row = ttk.Frame(self)
        row.pack(fill="x", **pad)
        self._enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row, text="Enabled", variable=self._enabled_var).pack(
            side="left", padx=(120, 0)
        )

        # ── Region ────────────────────────────────────────────────────
        region_frame = ttk.LabelFrame(self, text="Screen Region")
        region_frame.pack(fill="x", padx=8, pady=4)

        coord_row = ttk.Frame(region_frame)
        coord_row.pack(side="left", padx=4, pady=4)

        self._reg_x_var = tk.IntVar(value=0)
        self._reg_y_var = tk.IntVar(value=0)
        self._reg_w_var = tk.IntVar(value=200)
        self._reg_h_var = tk.IntVar(value=50)

        for label_text, var in (
            ("x:", self._reg_x_var),
            ("y:", self._reg_y_var),
            ("w:", self._reg_w_var),
            ("h:", self._reg_h_var),
        ):
            ttk.Label(coord_row, text=label_text).pack(side="left")
            ttk.Spinbox(
                coord_row, textvariable=var,
                from_=0, to=9999, width=6,
            ).pack(side="left", padx=(0, 6))

        ttk.Button(region_frame, text="Select…",
                   command=self._pick_region).pack(side="left", padx=4)

        # ── Monitor type ──────────────────────────────────────────────
        type_frame = ttk.LabelFrame(self, text="Trigger Type")
        type_frame.pack(fill="x", padx=8, pady=4)

        self._type_var = tk.StringVar(value="ocr")
        ttk.Radiobutton(type_frame, text="OCR (text)",
                        variable=self._type_var, value="ocr",
                        command=self._toggle_type).pack(
            side="left", padx=8, pady=4
        )
        ttk.Radiobutton(type_frame, text="Colour",
                        variable=self._type_var, value="color",
                        command=self._toggle_type).pack(
            side="left", padx=8, pady=4
        )

        # ── OCR config ────────────────────────────────────────────────
        self._ocr_frame = ttk.LabelFrame(self, text="OCR Settings")
        self._ocr_frame.pack(fill="x", padx=8, pady=4)

        row = ttk.Frame(self._ocr_frame)
        row.pack(fill="x", padx=4, pady=2)
        ttk.Label(row, text="Trigger text:", width=16, anchor="e").pack(
            side="left"
        )
        self._ocr_text_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._ocr_text_var, width=30).pack(
            side="left", padx=(4, 0)
        )

        row = ttk.Frame(self._ocr_frame)
        row.pack(fill="x", padx=4, pady=2)
        ttk.Label(row, text="Match type:", width=16, anchor="e").pack(
            side="left"
        )
        self._match_type_var = tk.StringVar(value="contains")
        match_cb = ttk.Combobox(
            row,
            textvariable=self._match_type_var,
            values=["contains", "exact", "regex",
                    "numeric_above", "numeric_below", "numeric_outside"],
            state="readonly",
            width=18,
        )
        match_cb.pack(side="left", padx=(4, 0))
        match_cb.bind("<<ComboboxSelected>>", self._toggle_numeric)

        row = ttk.Frame(self._ocr_frame)
        row.pack(fill="x", padx=4, pady=2)
        ttk.Label(row, text="Threshold value:", width=16, anchor="e").pack(
            side="left"
        )
        self._ocr_threshold_var = tk.StringVar(value="0")
        self._ocr_thresh_entry = ttk.Entry(
            row, textvariable=self._ocr_threshold_var, width=10,
            state="disabled"
        )
        self._ocr_thresh_entry.pack(side="left", padx=(4, 0))
        ttk.Label(row, text="(for numeric match types)").pack(
            side="left", padx=4
        )

        self._ocr_thresh_high_row = ttk.Frame(self._ocr_frame)
        self._ocr_thresh_high_row.pack(fill="x", padx=4, pady=2)
        ttk.Label(
            self._ocr_thresh_high_row, text="High threshold:", width=16,
            anchor="e"
        ).pack(side="left")
        self._ocr_threshold_high_var = tk.StringVar(value="100")
        self._ocr_thresh_high_entry = ttk.Entry(
            self._ocr_thresh_high_row,
            textvariable=self._ocr_threshold_high_var,
            width=10,
            state="disabled",
        )
        self._ocr_thresh_high_entry.pack(side="left", padx=(4, 0))
        ttk.Label(
            self._ocr_thresh_high_row, text="(for numeric_outside)"
        ).pack(side="left", padx=4)

        row = ttk.Frame(self._ocr_frame)
        row.pack(fill="x", padx=4, pady=2)
        self._case_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row, text="Case-sensitive",
                        variable=self._case_var).pack(
            side="left", padx=(120, 0)
        )

        # ── Colour config ─────────────────────────────────────────────
        self._color_frame = ttk.LabelFrame(self, text="Colour Settings")
        self._color_frame.pack(fill="x", padx=8, pady=4)

        row = ttk.Frame(self._color_frame)
        row.pack(fill="x", padx=4, pady=2)
        ttk.Label(row, text="Target colour:", width=16, anchor="e").pack(
            side="left"
        )
        self._color_var = [255, 0, 0]
        self._swatch = tk.Label(row, width=4, bg="#ff0000", relief="raised")
        self._swatch.pack(side="left", padx=4)
        ttk.Button(row, text="Pick…",
                   command=self._pick_color).pack(side="left")

        row = ttk.Frame(self._color_frame)
        row.pack(fill="x", padx=4, pady=2)
        ttk.Label(row, text="Tolerance (0-441):", width=16, anchor="e").pack(
            side="left"
        )
        self._tolerance_var = tk.StringVar(value="30")
        ttk.Entry(row, textvariable=self._tolerance_var, width=8).pack(
            side="left", padx=(4, 0)
        )

        row = ttk.Frame(self._color_frame)
        row.pack(fill="x", padx=4, pady=2)
        ttk.Label(row, text="Threshold % (0-100):", width=16,
                  anchor="e").pack(side="left")
        self._color_pct_var = tk.StringVar(value="10")
        ttk.Entry(row, textvariable=self._color_pct_var, width=8).pack(
            side="left", padx=(4, 0)
        )

        # ── Sound file ────────────────────────────────────────────────
        sf_frame = ttk.LabelFrame(self, text="Sound File")
        sf_frame.pack(fill="x", padx=8, pady=4)

        row = ttk.Frame(sf_frame)
        row.pack(fill="x", padx=4, pady=4)
        self._sound_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._sound_var, width=36).pack(
            side="left"
        )
        ttk.Button(row, text="Browse…",
                   command=self._pick_sound).pack(side="left", padx=4)

        # ── Timing ────────────────────────────────────────────────────
        timing_frame = ttk.LabelFrame(self, text="Timing")
        timing_frame.pack(fill="x", padx=8, pady=4)

        row = ttk.Frame(timing_frame)
        row.pack(fill="x", padx=4, pady=2)
        ttk.Label(row, text="Cooldown (s):", width=16, anchor="e").pack(
            side="left"
        )
        self._cooldown_var = tk.StringVar(value="5")
        ttk.Entry(row, textvariable=self._cooldown_var, width=8).pack(
            side="left", padx=(4, 0)
        )

        row = ttk.Frame(timing_frame)
        row.pack(fill="x", padx=4, pady=2)
        ttk.Label(row, text="Poll interval (s):", width=16, anchor="e").pack(
            side="left"
        )
        self._poll_var = tk.StringVar(value="0.5")
        ttk.Entry(row, textvariable=self._poll_var, width=8).pack(
            side="left", padx=(4, 0)
        )

        # ── Buttons ───────────────────────────────────────────────────
        btn_row = ttk.Frame(self)
        btn_row.pack(fill="x", padx=8, pady=8)
        ttk.Button(btn_row, text="OK", command=self._on_ok, width=12).pack(
            side="right", padx=4
        )
        ttk.Button(btn_row, text="Cancel",
                   command=self.destroy, width=12).pack(side="right")

        self._toggle_type()

    # ------------------------------------------------------------------
    # Populate from existing monitor
    # ------------------------------------------------------------------

    def _populate(self) -> None:
        m = self._monitor
        self._name_var.set(m.name)
        self._enabled_var.set(m.enabled)
        r = m.region
        self._reg_x_var.set(int(r.get("x", 0)))
        self._reg_y_var.set(int(r.get("y", 0)))
        self._reg_w_var.set(int(r.get("width", 200)))
        self._reg_h_var.set(int(r.get("height", 50)))
        self._type_var.set(m.monitor_type)

        self._ocr_text_var.set(m.ocr_config.trigger_text)
        self._match_type_var.set(m.ocr_config.match_type)
        self._ocr_threshold_var.set(str(m.ocr_config.threshold_value))
        self._ocr_threshold_high_var.set(str(m.ocr_config.threshold_value_high))
        self._case_var.set(m.ocr_config.case_sensitive)

        self._color_var = list(m.color_config.target_color)
        self._swatch.config(bg=_rgb_to_hex(self._color_var))
        self._tolerance_var.set(str(m.color_config.tolerance))
        self._color_pct_var.set(str(m.color_config.threshold_percent))

        if m.sound_file:
            self._sound_var.set(m.sound_file)
        elif self._default_sound:
            self._sound_var.set(self._default_sound)

        self._cooldown_var.set(str(m.cooldown))
        self._poll_var.set(str(m.poll_interval))

        self._toggle_type()
        self._toggle_numeric()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _toggle_type(self) -> None:
        if self._type_var.get() == "ocr":
            self._ocr_frame.pack(fill="x", padx=8, pady=4)
            self._color_frame.pack_forget()
        else:
            self._color_frame.pack(fill="x", padx=8, pady=4)
            self._ocr_frame.pack_forget()

    def _toggle_numeric(self, event=None) -> None:
        mt = self._match_type_var.get()
        if mt in ("numeric_above", "numeric_below", "numeric_outside"):
            self._ocr_thresh_entry.config(state="normal")
        else:
            self._ocr_thresh_entry.config(state="disabled")
        if mt == "numeric_outside":
            self._ocr_thresh_high_entry.config(state="normal")
        else:
            self._ocr_thresh_high_entry.config(state="disabled")

    def _pick_region(self) -> None:
        self.withdraw()
        try:
            sel = RegionSelector(master=self)
            region = sel.select()
        finally:
            self.deiconify()
        if region:
            self._monitor.region = region
            self._reg_x_var.set(int(region["x"]))
            self._reg_y_var.set(int(region["y"]))
            self._reg_w_var.set(int(region["width"]))
            self._reg_h_var.set(int(region["height"]))

    def _pick_color(self) -> None:
        initial = _rgb_to_hex(self._color_var)
        result = colorchooser.askcolor(color=initial,
                                       title="Choose target colour",
                                       parent=self)
        if result and result[0]:
            r, g, b = (int(c) for c in result[0])
            self._color_var = [r, g, b]
            self._swatch.config(bg=_rgb_to_hex(self._color_var))

    def _pick_sound(self) -> None:
        path = filedialog.askopenfilename(
            title="Select alert sound file",
            filetypes=[("Audio files", "*.wav *.ogg *.mp3"),
                       ("All files", "*.*")],
            parent=self,
        )
        if path:
            self._sound_var.set(path)

    def _on_ok(self) -> None:
        # Validate and build result Monitor.
        try:
            cooldown = float(self._cooldown_var.get())
            poll = float(self._poll_var.get())
            tolerance = int(self._tolerance_var.get())
            color_pct = float(self._color_pct_var.get())
            ocr_thresh = float(self._ocr_threshold_var.get())
            ocr_thresh_high = float(self._ocr_threshold_high_var.get())
            reg_x = int(self._reg_x_var.get())
            reg_y = int(self._reg_y_var.get())
            reg_w = max(_MIN_REGION_DIMENSION, int(self._reg_w_var.get()))
            reg_h = max(_MIN_REGION_DIMENSION, int(self._reg_h_var.get()))
        except ValueError as exc:
            messagebox.showerror("Invalid value", str(exc), parent=self)
            return
        except tk.TclError:
            messagebox.showerror(
                "Invalid region coordinates",
                "Please enter numeric values between 0 and 9999 for all "
                "region fields.",
                parent=self,
            )
            return

        if (
            self._match_type_var.get() == "numeric_outside"
            and ocr_thresh >= ocr_thresh_high
        ):
            messagebox.showerror(
                "Invalid thresholds",
                "For numeric_outside the low threshold must be less than the "
                "high threshold.",
                parent=self,
            )
            return

        m = self._monitor
        m.name = self._name_var.get().strip() or "Monitor"
        m.enabled = self._enabled_var.get()
        m.monitor_type = self._type_var.get()
        m.region = {"x": reg_x, "y": reg_y, "width": reg_w, "height": reg_h}

        m.ocr_config = OcrConfig(
            trigger_text=self._ocr_text_var.get(),
            match_type=self._match_type_var.get(),
            threshold_value=ocr_thresh,
            threshold_value_high=ocr_thresh_high,
            case_sensitive=self._case_var.get(),
        )
        m.color_config = ColorConfig(
            target_color=list(self._color_var),
            tolerance=tolerance,
            threshold_percent=color_pct,
        )
        m.sound_file = self._sound_var.get().strip()
        m.cooldown = max(0.0, cooldown)
        m.poll_interval = max(0.1, poll)

        self.result = m
        self.destroy()


# ===========================================================================
# Settings dialog
# ===========================================================================

class SettingsDialog(tk.Toplevel):
    """Modal dialog for global application settings."""

    def __init__(self, parent: tk.Widget, settings: Dict) -> None:
        super().__init__(parent)
        self.title("Settings")
        self.resizable(False, False)
        self.grab_set()

        self.result: Optional[Dict] = None
        self._settings = dict(settings)
        self._build()
        self._populate()
        self.wait_window()

    def _build(self) -> None:
        pad = {"padx": 8, "pady": 4}

        row = ttk.Frame(self)
        row.pack(fill="x", **pad)
        ttk.Label(row, text="Tesseract path:", width=18, anchor="e").pack(
            side="left"
        )
        self._tess_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._tess_var, width=36).pack(
            side="left", padx=4
        )
        ttk.Button(row, text="Browse…",
                   command=self._pick_tess).pack(side="left")

        row = ttk.Frame(self)
        row.pack(fill="x", **pad)
        ttk.Label(row, text="Default sound file:", width=18,
                  anchor="e").pack(side="left")
        self._sound_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._sound_var, width=36).pack(
            side="left", padx=4
        )
        ttk.Button(row, text="Browse…",
                   command=self._pick_sound).pack(side="left")

        row = ttk.Label(
            self,
            text=(
                "Tesseract-OCR must be installed separately.\n"
                "Download from: https://github.com/UB-Mannheim/tesseract/wiki"
            ),
            foreground="grey",
            justify="left",
        )
        row.pack(fill="x", padx=12, pady=4)

        btn_row = ttk.Frame(self)
        btn_row.pack(fill="x", padx=8, pady=8)
        ttk.Button(btn_row, text="OK", command=self._on_ok,
                   width=12).pack(side="right", padx=4)
        ttk.Button(btn_row, text="Cancel",
                   command=self.destroy, width=12).pack(side="right")

    def _populate(self) -> None:
        self._tess_var.set(self._settings.get("tesseract_cmd", ""))
        self._sound_var.set(self._settings.get("default_sound_file", ""))

    def _pick_tess(self) -> None:
        path = filedialog.askopenfilename(
            title="Select tesseract.exe",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
            parent=self,
        )
        if path:
            self._tess_var.set(path)

    def _pick_sound(self) -> None:
        path = filedialog.askopenfilename(
            title="Select default alert sound",
            filetypes=[("Audio files", "*.wav *.ogg *.mp3"),
                       ("All files", "*.*")],
            parent=self,
        )
        if path:
            self._sound_var.set(path)

    def _on_ok(self) -> None:
        self.result = {
            "tesseract_cmd": self._tess_var.get().strip(),
            "default_sound_file": self._sound_var.get().strip(),
        }
        self.destroy()


# ===========================================================================
# Main application window
# ===========================================================================

class BettyApp:
    """
    SC Bitching Betty – main application class.

    Call ``run()`` to start the tkinter event loop.
    """

    _STATUS_IDLE = "Idle – monitoring stopped"
    _STATUS_RUNNING = "Monitoring active"

    def __init__(self) -> None:
        self._monitors: List[Monitor] = []
        self._settings: Dict = {
            "tesseract_cmd": "",
            "default_sound_file": "",
        }

        self._config = ConfigManager()
        self._alert = AlertManager()
        self._detector = ColorDetector()
        self._ocr: OcrReader = OcrReader()

        # Per-monitor live-status indicators: {id: bool (triggered)}
        self._live_status: Dict[str, bool] = {}
        # Most-recent raw OCR text per monitor: {id: str}
        self._ocr_texts: Dict[str, str] = {}
        # Debounce flags – only one pending callback at a time for each update.
        self._tree_refresh_pending: bool = False
        self._ocr_display_pending: bool = False

        self._engine: Optional[MonitoringEngine] = None

        self._root = tk.Tk()
        self._root.title("SC Bitching Betty")
        self._root.minsize(560, 460)
        self._root.config(bd=2, relief="groove")
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._load_config()
        # Re-run dependency check now that settings (including the Tesseract
        # path) have been loaded; the first check inside _build_ui ran before
        # the config was available.
        self._check_deps()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Enter the tkinter main loop."""
        self._root.mainloop()

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # ── Menu bar ──────────────────────────────────────────────────
        menubar = tk.Menu(self._root)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Settings…", command=self._open_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)
        self._root.config(menu=menubar)

        # ── Toolbar ───────────────────────────────────────────────────
        toolbar = ttk.Frame(self._root, relief="raised")
        toolbar.pack(side="top", fill="x")

        self._start_btn = ttk.Button(
            toolbar, text="▶  Start Monitoring",
            command=self._start_monitoring, width=20
        )
        self._start_btn.pack(side="left", padx=4, pady=4)

        self._stop_btn = ttk.Button(
            toolbar, text="■  Stop Monitoring",
            command=self._stop_monitoring, width=20,
            state="disabled"
        )
        self._stop_btn.pack(side="left", padx=4, pady=4)

        ttk.Separator(toolbar, orient="vertical").pack(
            side="left", fill="y", padx=6
        )

        ttk.Button(toolbar, text="⚙  Settings",
                   command=self._open_settings).pack(
            side="left", padx=4, pady=4
        )

        # ── Monitor list ──────────────────────────────────────────────
        list_frame = ttk.LabelFrame(self._root, text="Monitors")
        list_frame.pack(fill="both", expand=True, padx=8, pady=4)

        # Inner frame with a solid border around the treeview.
        tree_border = tk.Frame(list_frame, relief="solid", borderwidth=1)
        tree_border.pack(side="left", fill="both", expand=True,
                         padx=4, pady=4)

        columns = ("name", "type", "region", "sound", "status")
        self._tree = ttk.Treeview(
            tree_border, columns=columns, show="headings", selectmode="browse"
        )
        self._tree.heading("name",   text="Name")
        self._tree.heading("type",   text="Type")
        self._tree.heading("region", text="Region")
        self._tree.heading("sound",  text="Sound file")
        self._tree.heading("status", text="Status")
        self._tree.column("name",   width=140)
        self._tree.column("type",   width=60,  anchor="center")
        self._tree.column("region", width=160)
        self._tree.column("sound",  width=130)
        self._tree.column("status", width=80,  anchor="center")
        self._tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(
            list_frame, orient="vertical", command=self._tree.yview
        )
        scrollbar.pack(side="right", fill="y", pady=4)
        self._tree.config(yscrollcommand=scrollbar.set)

        # Tag colouring for live status.
        self._tree.tag_configure("triggered",  foreground="#cc0000")
        self._tree.tag_configure("ok",         foreground="#007700")
        self._tree.tag_configure("disabled",   foreground="#888888")

        # ── Drag-and-drop reordering ───────────────────────────────────
        # A canvas line is drawn over the treeview to show the drop target.
        self._drag_source: Optional[str] = None
        self._drag_canvas = tk.Canvas(
            self._tree, height=2, bg="#0055cc",
            highlightthickness=0, borderwidth=0,
        )
        self._tree.bind("<ButtonPress-1>",   self._on_drag_start)
        self._tree.bind("<B1-Motion>",       self._on_drag_motion)
        self._tree.bind("<ButtonRelease-1>", self._on_drag_release)
        self._tree.bind("<Escape>",          self._on_drag_cancel)

        # ── CRUD buttons ──────────────────────────────────────────────
        crud = ttk.Frame(self._root)
        crud.pack(fill="x", padx=8, pady=4)

        ttk.Button(crud, text="Add Monitor",
                   command=self._add_monitor).pack(side="left", padx=4)
        ttk.Button(crud, text="Edit Selected",
                   command=self._edit_monitor).pack(side="left", padx=4)
        ttk.Button(crud, text="Remove Selected",
                   command=self._remove_monitor).pack(side="left", padx=4)
        ttk.Button(crud, text="Toggle Enable",
                   command=self._toggle_monitor).pack(side="left", padx=4)
        ttk.Button(crud, text="Drag & Select Region",
                   command=self._drag_select_region).pack(side="left", padx=4)

        # ── Live OCR output ───────────────────────────────────────────
        ocr_out_frame = ttk.LabelFrame(self._root, text="Live OCR Output")
        ocr_out_frame.pack(fill="x", padx=8, pady=(0, 4))

        self._ocr_output_text = tk.Text(
            ocr_out_frame, height=3, state="disabled",
            wrap="word", relief="flat",
            background=self._root.cget("background"),
            font=("Courier", 9),
        )
        self._ocr_output_text.pack(fill="x", padx=4, pady=4)

        # ── Status bar ────────────────────────────────────────────────
        status_bar = ttk.Frame(self._root, relief="sunken")
        status_bar.pack(side="bottom", fill="x")

        self._status_var = tk.StringVar(value=self._STATUS_IDLE)
        ttk.Label(status_bar, textvariable=self._status_var).pack(
            side="left", padx=6
        )

        self._dep_var = tk.StringVar()
        ttk.Label(status_bar, textvariable=self._dep_var,
                  foreground="grey").pack(side="right", padx=6)

        self._check_deps()

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        data = self._config.load()
        self._settings = data["settings"]
        self._monitors = data["monitors"]
        self._refresh_ocr()
        self._refresh_tree()

    def _save_config(self) -> None:
        self._config.save(self._settings, self._monitors)

    def _refresh_ocr(self) -> None:
        self._ocr = OcrReader(
            tesseract_cmd=self._settings.get("tesseract_cmd") or None
        )

    # ------------------------------------------------------------------
    # Dependency check
    # ------------------------------------------------------------------

    def _check_deps(self) -> None:
        missing = []
        try:
            import mss  # noqa: F401
        except ImportError:
            missing.append("mss")
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            missing.append("Pillow")
        try:
            import numpy  # noqa: F401
        except ImportError:
            missing.append("numpy")
        if missing:
            self._dep_var.set(f"Missing: {', '.join(missing)}")
        elif not self._ocr.available:
            self._dep_var.set(
                "OCR unavailable – install Tesseract-OCR and set its path in Settings"
            )
        else:
            self._dep_var.set("All dependencies OK")

    # ------------------------------------------------------------------
    # Tree refresh
    # ------------------------------------------------------------------

    def _refresh_tree(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)

        for m in self._monitors:
            r = m.region
            region_str = f"({r['x']},{r['y']}) {r['width']}×{r['height']}"
            sound_str = os.path.basename(m.sound_file) if m.sound_file else "—"
            live = self._live_status.get(m.id)
            if not m.enabled:
                status_str = "disabled"
                tag = "disabled"
            elif live is True:
                status_str = "⚠ ALERT"
                tag = "triggered"
            elif live is False:
                status_str = "OK"
                tag = "ok"
            else:
                status_str = "—"
                tag = ""

            self._tree.insert(
                "",
                "end",
                iid=m.id,
                values=(m.name, m.monitor_type.upper(), region_str,
                        sound_str, status_str),
                tags=(tag,),
            )

    def _selected_monitor(self) -> Optional[Monitor]:
        sel = self._tree.selection()
        if not sel:
            return None
        mid = sel[0]
        for m in self._monitors:
            if m.id == mid:
                return m
        return None

    # ------------------------------------------------------------------
    # CRUD actions
    # ------------------------------------------------------------------

    def _add_monitor(self) -> None:
        dlg = MonitorDialog(
            self._root,
            default_sound=self._settings.get("default_sound_file", "")
        )
        if dlg.result:
            self._monitors.append(dlg.result)
            self._save_config()
            self._refresh_tree()

    def _edit_monitor(self) -> None:
        m = self._selected_monitor()
        if not m:
            messagebox.showinfo("No selection", "Please select a monitor.")
            return
        dlg = MonitorDialog(
            self._root,
            monitor=copy.deepcopy(m),
            default_sound=self._settings.get("default_sound_file", "")
        )
        if dlg.result:
            idx = next(
                i for i, mon in enumerate(self._monitors) if mon.id == m.id
            )
            self._monitors[idx] = dlg.result
            self._save_config()
            self._refresh_tree()

    def _remove_monitor(self) -> None:
        m = self._selected_monitor()
        if not m:
            messagebox.showinfo("No selection", "Please select a monitor.")
            return
        if messagebox.askyesno("Confirm", f"Remove '{m.name}'?",
                               parent=self._root):
            self._monitors = [x for x in self._monitors if x.id != m.id]
            self._save_config()
            self._refresh_tree()

    def _toggle_monitor(self) -> None:
        m = self._selected_monitor()
        if not m:
            messagebox.showinfo("No selection", "Please select a monitor.")
            return
        m.enabled = not m.enabled
        self._save_config()
        self._refresh_tree()

    def _drag_select_region(self) -> None:
        m = self._selected_monitor()
        if not m:
            messagebox.showinfo(
                "No selection",
                "Please select a monitor to update its region.",
            )
            return
        self._root.withdraw()
        try:
            sel = RegionSelector(master=self._root)
            region = sel.select()
        finally:
            self._root.deiconify()
        if region:
            m.region = region
            self._save_config()
            self._refresh_tree()

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._root, self._settings)
        if dlg.result:
            self._settings = dlg.result
            self._save_config()
            self._refresh_ocr()

    # ------------------------------------------------------------------
    # Monitoring control
    # ------------------------------------------------------------------

    def _start_monitoring(self) -> None:
        if self._engine and self._engine.running:
            return
        if not self._monitors:
            messagebox.showinfo(
                "No monitors",
                "Add at least one monitor before starting.",
            )
            return

        # Warn if any OCR monitor is enabled but Tesseract is not available.
        has_ocr = any(
            m.enabled and m.monitor_type == "ocr" for m in self._monitors
        )
        if has_ocr and not self._ocr.available:
            messagebox.showwarning(
                "OCR unavailable",
                "One or more monitors use OCR, but Tesseract-OCR is not "
                "installed or its path is not configured.\n\n"
                "OCR monitors will never trigger until Tesseract is set up.\n"
                "Go to File → Settings to set the Tesseract executable path.",
            )

        self._engine = MonitoringEngine(
            monitors=self._monitors,
            alert_manager=self._alert,
            ocr_reader=self._ocr,
            color_detector=self._detector,
            on_status=self._on_engine_status,
            on_ocr_text=self._on_engine_ocr_text,
        )
        self._engine.start()

        self._start_btn.config(state="disabled")
        self._stop_btn.config(state="normal")
        self._status_var.set(self._STATUS_RUNNING)

    def _stop_monitoring(self) -> None:
        if self._engine:
            self._engine.stop()
            self._engine = None

        self._live_status.clear()
        self._ocr_texts.clear()
        self._tree_refresh_pending = False
        self._ocr_display_pending = False
        self._start_btn.config(state="normal")
        self._stop_btn.config(state="disabled")
        self._status_var.set(self._STATUS_IDLE)
        self._refresh_tree()
        self._update_ocr_display()

    # ------------------------------------------------------------------
    # Drag-and-drop helpers
    # ------------------------------------------------------------------

    def _on_drag_start(self, event: tk.Event) -> None:
        item = self._tree.identify_row(event.y)
        self._drag_source = item if item else None

    def _on_drag_motion(self, event: tk.Event) -> None:
        if not self._drag_source:
            return
        target = self._tree.identify_row(event.y)
        if target and target != self._drag_source:
            self._tree.config(cursor="sb_v_double_arrow")
            # Draw a line at the top edge of the target row to show where
            # the item will be inserted.
            bbox = self._tree.bbox(target)
            if bbox:
                x, y, width, height = bbox
                line_y = y if event.y < y + height // 2 else y + height
                self._drag_canvas.place(x=0, y=line_y - 1,
                                        width=width, height=2)
                self._drag_canvas.lift()
        else:
            self._drag_canvas.place_forget()
            self._tree.config(cursor="")

    def _on_drag_release(self, event: tk.Event) -> None:
        self._drag_canvas.place_forget()
        self._tree.config(cursor="")
        if not self._drag_source:
            return
        src = self._drag_source
        self._drag_source = None

        target = self._tree.identify_row(event.y)
        if not target or target == src:
            return

        src_idx = next(
            (i for i, m in enumerate(self._monitors) if m.id == src), None
        )
        tgt_idx = next(
            (i for i, m in enumerate(self._monitors) if m.id == target), None
        )
        if src_idx is None or tgt_idx is None:
            return

        # Determine whether to insert before or after the target row.
        bbox = self._tree.bbox(target)
        if bbox:
            _, y, _, height = bbox
            insert_after = event.y >= y + height // 2
        else:
            insert_after = tgt_idx > src_idx

        mon = self._monitors.pop(src_idx)
        insert_at = tgt_idx if not insert_after else tgt_idx + 1
        # Adjust for the removed element.
        if src_idx < insert_at:
            insert_at -= 1
        self._monitors.insert(insert_at, mon)
        self._save_config()
        self._refresh_tree()
        self._tree.selection_set(src)

    def _on_drag_cancel(self, event: Optional[tk.Event] = None) -> None:
        self._drag_canvas.place_forget()
        self._tree.config(cursor="")
        self._drag_source = None

    # ------------------------------------------------------------------
    # Engine status callbacks (called on monitoring thread)
    # ------------------------------------------------------------------

    def _on_engine_status(self, monitor_id: str, triggered: bool) -> None:
        self._live_status[monitor_id] = triggered
        # Debounce: only schedule one refresh at a time to avoid flooding
        # the event queue when many monitors fire in quick succession.
        if not self._tree_refresh_pending:
            self._tree_refresh_pending = True
            self._root.after(100, self._do_tree_refresh)

    def _do_tree_refresh(self) -> None:
        self._tree_refresh_pending = False
        try:
            self._refresh_tree()
        except Exception:
            pass

    def _on_engine_ocr_text(self, monitor_id: str, text: str) -> None:
        self._ocr_texts[monitor_id] = text
        if not self._ocr_display_pending:
            self._ocr_display_pending = True
            self._root.after(200, self._do_ocr_display)

    def _do_ocr_display(self) -> None:
        self._ocr_display_pending = False
        self._update_ocr_display()

    def _update_ocr_display(self) -> None:
        """Refresh the Live OCR Output widget with the latest reads."""
        lines: List[str] = []
        for m in self._monitors:
            if m.monitor_type == "ocr":
                raw = self._ocr_texts.get(m.id, "")
                # Show the text on one line, trimmed; use repr so
                # invisible whitespace / newlines are visible.
                preview = repr(raw.strip()) if raw.strip() else "(no text)"
                lines.append(f"[{m.name}]  {preview}")
        display = "\n".join(lines) if lines else "(no OCR monitors active)"
        try:
            self._ocr_output_text.config(state="normal")
            self._ocr_output_text.delete("1.0", "end")
            self._ocr_output_text.insert("1.0", display)
            self._ocr_output_text.config(state="disabled")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Window close
    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        self._stop_monitoring()
        self._save_config()
        self._root.destroy()
