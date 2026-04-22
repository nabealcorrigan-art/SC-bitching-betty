"""
engine.py – Background monitoring engine.

A single daemon thread polls every enabled monitor at its configured
interval, runs the appropriate check (OCR or colour), and calls the
alert manager when a condition is met.  Cooldown is enforced per-monitor
to prevent alert spam.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Dict, List, Optional

from src.monitor_model import Monitor
from src.capture import ScreenCapture
from src.ocr import OcrReader, apply_js_filter
from src.colors import ColorDetector
from src.alerts import AlertManager


class MonitoringEngine:
    """
    Background polling engine.

    Parameters
    ----------
    monitors:       Shared list of ``Monitor`` objects (may be mutated
                    externally; access is protected by ``_lock``).
    alert_manager:  Plays sound files when a condition fires.
    ocr_reader:     OCR back-end.
    color_detector: Colour-threshold back-end.
    on_status:      Optional callback ``(monitor_id, triggered: bool)``
                    called on the polling thread when a result is ready.
    on_ocr_text:    Optional callback ``(monitor_id, raw_text: str)``
                    called after every OCR read so the UI can display
                    what characters the program is currently seeing.
    """

    def __init__(
        self,
        monitors: List[Monitor],
        alert_manager: AlertManager,
        ocr_reader: OcrReader,
        color_detector: ColorDetector,
        on_status: Optional[Callable[[str, bool], None]] = None,
        on_ocr_text: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self._monitors = monitors
        self._alert = alert_manager
        self._ocr = ocr_reader
        self._colors = color_detector
        self._on_status = on_status
        self._on_ocr_text = on_ocr_text

        self._capture = ScreenCapture()
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._running = False

        # Per-monitor timing state  {monitor_id: float (unix ts)}
        self._last_check: Dict[str, float] = {}
        self._last_alert: Dict[str, float] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start the background polling thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="betty-engine"
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the polling thread to stop and wait for it."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        while self._running:
            now = time.monotonic()

            with self._lock:
                monitors_snapshot = list(self._monitors)

            # Collect all monitors that triggered and have passed their cooldown.
            pending_alerts: List[Monitor] = []

            for monitor in monitors_snapshot:
                if not monitor.enabled:
                    continue

                # Respect per-monitor poll interval.
                last_poll = self._last_check.get(monitor.id, 0.0)
                if now - last_poll < monitor.poll_interval:
                    continue
                self._last_check[monitor.id] = now

                # Capture region.
                img = self._capture.capture_region(monitor.region)
                if img is None:
                    continue

                # Evaluate condition.
                triggered = False
                if monitor.monitor_type == "ocr":
                    raw_text = self._ocr.read_text(img)
                    # Apply optional per-monitor JavaScript filter so the
                    # user can reshape the OCR string before matching.
                    if monitor.ocr_config.js_filter:
                        raw_text = apply_js_filter(
                            raw_text, monitor.ocr_config.js_filter
                        )
                    # Notify UI with the (possibly filtered) OCR text.
                    if self._on_ocr_text:
                        try:
                            self._on_ocr_text(monitor.id, raw_text)
                        except Exception:
                            pass
                    triggered = self._ocr.check_text(raw_text, monitor.ocr_config)
                elif monitor.monitor_type == "color":
                    triggered = self._colors.check(img, monitor.color_config)

                # Notify UI.
                if self._on_status:
                    try:
                        self._on_status(monitor.id, triggered)
                    except Exception:
                        pass

                # Queue alert if triggered and cooldown has elapsed.
                if triggered:
                    last_alert = self._last_alert.get(monitor.id, 0.0)
                    if now - last_alert >= monitor.cooldown:
                        pending_alerts.append(monitor)

            # Among simultaneously triggered ralt_altitude_below monitors,
            # only the one with the lowest threshold (most critical altitude)
            # plays; higher-threshold ones are suppressed.
            pending_alerts = self._apply_ralt_priority(pending_alerts)

            for monitor in pending_alerts:
                self._last_alert[monitor.id] = now
                self._alert.play(monitor.sound_file)

            # Short sleep to avoid busy-spinning at 100% CPU.
            time.sleep(0.005)

    def _apply_ralt_priority(self, monitors: List[Monitor]) -> List[Monitor]:
        """
        Suppress higher-threshold ``ralt_altitude_below`` monitors when a
        lower-threshold one is also ready to alert.

        When two or more ``ralt_altitude_below`` rules trigger at the same
        time, only the one with the lowest ``threshold_value`` (the most
        critical altitude warning) plays.  Rules of any other type are
        passed through unchanged.
        """
        ralt_candidates = [
            m for m in monitors
            if m.monitor_type == "ocr"
            and m.ocr_config.match_type == "ralt_altitude_below"
        ]
        if len(ralt_candidates) <= 1:
            return monitors

        # Keep only the most critical (lowest threshold) RALT monitor.
        # len(ralt_candidates) >= 2 here, so min() is always safe.
        lowest = min(ralt_candidates, key=lambda m: m.ocr_config.threshold_value)
        suppressed = {id(m) for m in ralt_candidates if m is not lowest}
        return [m for m in monitors if id(m) not in suppressed]
