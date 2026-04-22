"""
monitor_model.py – Data classes that represent a screen-monitoring rule.

Each Monitor describes:
  • which region of the screen to watch
  • whether to use OCR text matching or colour-threshold detection
  • what sound to play when the condition is met
  • cooldown / poll timing
"""

import uuid
from dataclasses import dataclass, field
from typing import Dict, List


# ---------------------------------------------------------------------------
# Sub-configs
# ---------------------------------------------------------------------------

@dataclass
class OcrConfig:
    """Settings for OCR-based triggering."""

    trigger_text: str = ""
    """Text to look for in the OCR output."""

    match_type: str = "contains"
    """
    How to compare the OCR output to *trigger_text*.

    Allowed values
    ~~~~~~~~~~~~~~
    ``contains``        – OCR text contains *trigger_text* (default)
    ``exact``           – OCR text equals *trigger_text*
    ``regex``           – *trigger_text* is a regular-expression pattern
    ``numeric_above``   – number in OCR text > *threshold_value*
                          (non-numeric characters are ignored)
    ``numeric_below``   – number in OCR text < *threshold_value*
                          (non-numeric characters are ignored)
    ``numeric_outside`` – number in OCR text < *threshold_value* **or**
                          > *threshold_value_high*; use this to alert when
                          a reading leaves a normal range
                          (non-numeric characters are ignored)
    ``altitude_below``  – looks for a value in the form ``<digits>m``
                          (e.g. ``"2103m"`` or ``"102m"``) anywhere in the
                          OCR text and triggers when that number is below
                          *threshold_value*; useful for Star Citizen altitude
                          readouts
    ``ralt_altitude_below`` – looks for a radar-altitude string of the
                          form ``RALT <spaces> <digits>m`` (e.g.
                          ``"RALT  130m"``) and triggers when that number
                          is below *threshold_value*; handles the variable
                          spacing in Star Citizen's RALT HUD readout
    ``ralt_contains``   – extracts the RALT altitude value (same parser as
                          ``ralt_altitude_below``) and triggers when
                          *trigger_text* appears in the stringified altitude
                          (e.g. set *trigger_text* to ``"500"`` to fire an
                          audible callout every time the RALT reads 500 m)
    """

    threshold_value: float = 0.0
    """
    Lower threshold used by ``numeric_above``, ``numeric_below``, and
    ``numeric_outside``.
    """

    threshold_value_high: float = 100.0
    """Upper threshold used by ``numeric_outside``."""

    case_sensitive: bool = False
    """Whether text comparisons are case-sensitive."""

    js_filter: str = ""
    """
    Optional JavaScript function body that transforms the raw OCR text
    before it is compared against trigger conditions.

    The script receives the raw OCR string as the variable ``text`` and
    must return the (possibly modified) string.  Errors in the script are
    silently ignored and the original text is used instead.

    Example – keep only digits::

        return text.replace(/[^0-9]/g, '');

    Example – trim and upper-case::

        return text.trim().toUpperCase();
    """


@dataclass
class ColorConfig:
    """Settings for colour-threshold triggering."""

    target_color: List[int] = field(default_factory=lambda: [255, 0, 0])
    """Target RGB colour, e.g. ``[255, 0, 0]`` for pure red."""

    tolerance: int = 30
    """
    Maximum Euclidean distance in RGB space for a pixel to be counted
    as *matching* the target colour (0–441).
    """

    threshold_percent: float = 10.0
    """
    Alert fires when this percentage (0–100) of pixels in the region
    match the target colour within *tolerance*.
    """


# ---------------------------------------------------------------------------
# Main Monitor dataclass
# ---------------------------------------------------------------------------

@dataclass
class Monitor:
    """A single monitoring rule."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    """Unique identifier (auto-generated)."""

    name: str = "New Monitor"
    """Human-readable label shown in the UI."""

    enabled: bool = True
    """Whether this monitor is active."""

    region: Dict = field(
        default_factory=lambda: {"x": 0, "y": 0, "width": 200, "height": 50}
    )
    """Screen region: ``{"x", "y", "width", "height"}`` in pixels."""

    monitor_type: str = "ocr"
    """``"ocr"`` or ``"color"``."""

    ocr_config: OcrConfig = field(default_factory=OcrConfig)
    """OCR trigger settings (used when *monitor_type* == ``"ocr"``)."""

    color_config: ColorConfig = field(default_factory=ColorConfig)
    """Colour trigger settings (used when *monitor_type* == ``"color"``)."""

    sound_file: str = ""
    """Absolute or relative path to the ``.wav`` / ``.ogg`` alert sound."""

    cooldown: float = 5.0
    """Minimum seconds between consecutive alerts for this monitor."""

    poll_interval: float = 0.1
    """How often (seconds) to sample this region."""

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "region": self.region,
            "monitor_type": self.monitor_type,
            "ocr_config": {
                "trigger_text": self.ocr_config.trigger_text,
                "match_type": self.ocr_config.match_type,
                "threshold_value": self.ocr_config.threshold_value,
                "threshold_value_high": self.ocr_config.threshold_value_high,
                "case_sensitive": self.ocr_config.case_sensitive,
                "js_filter": self.ocr_config.js_filter,
            },
            "color_config": {
                "target_color": self.color_config.target_color,
                "tolerance": self.color_config.tolerance,
                "threshold_percent": self.color_config.threshold_percent,
            },
            "sound_file": self.sound_file,
            "cooldown": self.cooldown,
            "poll_interval": self.poll_interval,
        }

    @staticmethod
    def from_dict(data: dict) -> "Monitor":
        """Reconstruct a Monitor from a plain dictionary."""
        ocr_raw = data.get("ocr_config", {})
        color_raw = data.get("color_config", {})
        return Monitor(
            id=data.get("id", str(uuid.uuid4())[:8]),
            name=data.get("name", "Monitor"),
            enabled=data.get("enabled", True),
            region=data.get(
                "region", {"x": 0, "y": 0, "width": 200, "height": 50}
            ),
            monitor_type=data.get("monitor_type", "ocr"),
            ocr_config=OcrConfig(
                trigger_text=ocr_raw.get("trigger_text", ""),
                match_type=ocr_raw.get("match_type", "contains"),
                threshold_value=float(ocr_raw.get("threshold_value", 0.0)),
                threshold_value_high=float(
                    ocr_raw.get("threshold_value_high", 100.0)
                ),
                case_sensitive=bool(ocr_raw.get("case_sensitive", False)),
                js_filter=ocr_raw.get("js_filter", ""),
            ),
            color_config=ColorConfig(
                target_color=color_raw.get("target_color", [255, 0, 0]),
                tolerance=int(color_raw.get("tolerance", 30)),
                threshold_percent=float(
                    color_raw.get("threshold_percent", 10.0)
                ),
            ),
            sound_file=data.get("sound_file", ""),
            cooldown=float(data.get("cooldown", 5.0)),
            poll_interval=float(data.get("poll_interval", 0.1)),
        )
