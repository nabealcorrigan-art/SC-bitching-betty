"""
ocr.py – OCR text extraction and threshold checking.

Wraps *pytesseract* and provides helper logic for matching OCR results
against the conditions defined in ``OcrConfig``.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

try:
    import pytesseract
    _TESSERACT_AVAILABLE = True
except ImportError:
    _TESSERACT_AVAILABLE = False

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

try:
    from py_mini_racer import MiniRacer as _MiniRacer
    _MINI_RACER_AVAILABLE = True
except ImportError:
    _MINI_RACER_AVAILABLE = False

from src.monitor_model import OcrConfig

logger = logging.getLogger(__name__)

# Characters allowed in OCR output for *text* modes: letters, digits,
# whitespace, and the decimal separators '.' and ',' used by numeric
# threshold matching.
_OCR_NOISE_PATTERN = re.compile(r"[^a-zA-Z0-9\s.,]")

# ---------------------------------------------------------------------------
# RALT (radar altitude) extraction
# ---------------------------------------------------------------------------

# OCR-artifact label variants for "RALT", in longest-first order so the
# alternation engine matches the most specific option first.
_RALT_LABEL_RE = re.compile(
    r"^\s*"                              # ignore leading whitespace
    r"(?:\S{1,3}\s+)?"                  # optional 1-3 noise chars + whitespace
    r"(?:ORALT|ReALT|RALT|RAT|RAL|ALT)" # label variants (longest first)
    r"[.,]?\s+"                         # separator: optional . or , then spaces
    r"([A-Za-z0-9]+)",                  # value field (may contain OCR noise)
    re.IGNORECASE,
)

# Common OCR substitutions found inside a digit sequence.
# S/s → 5,  O (capital only) → 0,  B → 8
_DIGIT_FIXES = str.maketrans("SsOB", "5508")

# Sanity-check bounds for radar altitude readings.
_RALT_MAX_METERS = 99_999

# For *numeric* modes only keep characters that can appear in a number:
# digits, decimal separators, sign chars, and spaces (used as separators).
_NON_NUMERIC_PATTERN = re.compile(r"[^\d.,+\- ]")

# Lazily-created shared MiniRacer context (V8 isolate).  Creating one
# instance once and reusing it avoids repeated isolate-startup overhead.
_js_context: Optional["_MiniRacer"] = None


def extract_altitude(text: str) -> "int | None":
    """
    Extract a RALT (radar altitude) reading from a noisy OCR frame.

    The function searches each line of *text* for a RALT label followed by
    an altitude value.  It tolerates common OCR artefacts:

    * Label may appear as any of: RALT, RAT, RAL, ReALT, ORALT, ALT.
    * Up to three noise characters may precede the label on the same line
      (e.g. ``"x RALT 195m"``).
    * The label–value separator may be spaces, a period, or a comma+spaces
      (e.g. ``"RALT. 385m"``, ``"RALT,  397m"``).
    * The trailing ``m`` unit marker is optional and may be followed by
      punctuation (both are ignored).
    * Common digit OCR errors are corrected before parsing:
      ``S``/``s`` → ``5``, capital ``O`` → ``0``, ``B`` → ``8``.
    * The altitude must be a whole number in [0, 99999] metres; any other
      reading is rejected.

    Parameters
    ----------
    text:
        Full multi-line OCR output for one monitor frame.

    Returns
    -------
    int | None
        Altitude in metres, or ``None`` if no reliable reading is found.
    """
    for line in text.splitlines():
        m = _RALT_LABEL_RE.match(line.strip())
        if m is None:
            continue
        raw = m.group(1)
        # Strip trailing unit marker "m"/"M"; it is not part of the number.
        if raw and raw[-1] in ("m", "M"):
            raw = raw[:-1]
        corrected = raw.translate(_DIGIT_FIXES)
        if not corrected.isdigit():
            continue
        altitude = int(corrected)
        if 0 <= altitude <= _RALT_MAX_METERS:
            return altitude
    return None


def _get_js_context() -> Optional["_MiniRacer"]:
    """Return the shared MiniRacer context, creating it on first call."""
    global _js_context
    if not _MINI_RACER_AVAILABLE:
        return None
    if _js_context is None:
        _js_context = _MiniRacer()
    return _js_context


def apply_js_filter(text: str, js_code: str) -> str:
    """
    Transform *text* by running *js_code* inside a JavaScript function.

    *js_code* is treated as the **body** of a function that receives the
    OCR text in the variable ``text`` and must ``return`` the modified
    string.  Example::

        return text.replace(/[^0-9]/g, '');

    If *js_code* is empty, ``py_mini_racer`` is unavailable, or the script
    raises an error, the original *text* is returned unchanged and the
    error is logged at WARNING level so the user can diagnose mistakes.

    .. note::
        Only the user's own filter code is executed.  The OCR text is
        passed as a JSON-encoded string argument so it cannot be
        interpreted as code.

    Parameters
    ----------
    text:    Raw OCR string to transform.
    js_code: JavaScript function body.
    """
    if not js_code.strip():
        return text
    ctx = _get_js_context()
    if ctx is None:
        logger.warning(
            "JS filter is configured but py_mini_racer is not installed. "
            "Run: pip install py_mini_racer"
        )
        return text
    try:
        script = f"(function(text) {{ {js_code} }})({json.dumps(text)})"
        result = ctx.eval(script)
        return str(result) if result is not None else text
    except Exception as exc:
        logger.warning("JS filter raised an error: %s", exc)
        return text


class OcrReader:
    """
    Extracts text from a PIL image and checks whether it satisfies
    the trigger condition described by an ``OcrConfig``.
    """

    def __init__(self, tesseract_cmd: Optional[str] = None) -> None:
        """
        Parameters
        ----------
        tesseract_cmd:
            Full path to the ``tesseract`` executable, e.g.
            ``r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"``.
            Leave ``None`` to use whatever is on ``PATH``.
        """
        if _TESSERACT_AVAILABLE and tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """``True`` when both pytesseract and Tesseract-OCR are usable."""
        if not _TESSERACT_AVAILABLE or not _PIL_AVAILABLE:
            return False
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def read_text(self, img: "Image.Image") -> str:
        """
        Run OCR on *img* and return the cleaned string output.

        Non-alphanumeric characters (except whitespace and the decimal
        separators ``.`` and ``,``) are removed to filter out common OCR
        noise such as ``|``, ``!``, or ``@``, while preserving numeric
        values with decimal points.

        Returns an empty string if OCR is unavailable or fails.
        """
        if not self.available:
            return ""
        try:
            raw = pytesseract.image_to_string(img)
            return _OCR_NOISE_PATTERN.sub("", raw)
        except Exception:
            return ""

    def check(self, img: "Image.Image", config: OcrConfig) -> bool:
        """
        Return ``True`` if the OCR result from *img* satisfies *config*.

        Parameters
        ----------
        img:    PIL image of the captured region.
        config: ``OcrConfig`` describing the trigger condition.
        """
        raw = self.read_text(img)
        return self.check_text(raw, config)

    def check_text(self, raw: str, config: OcrConfig) -> bool:
        """
        Return ``True`` if *raw* (pre-read OCR text) satisfies *config*.

        This allows callers that have already obtained the raw text to
        avoid a second OCR pass.
        """
        if not raw:
            return False

        text = raw if config.case_sensitive else raw.lower()
        trigger = (
            config.trigger_text
            if config.case_sensitive
            else config.trigger_text.lower()
        )

        match config.match_type:
            case "contains":
                return bool(trigger) and trigger in text

            case "exact":
                return text.strip() == trigger.strip()

            case "regex":
                flags = 0 if config.case_sensitive else re.IGNORECASE
                try:
                    return bool(
                        re.search(config.trigger_text, raw, flags=flags)
                    )
                except re.error:
                    return False

            case "numeric_above":
                # Use the first number found; non-numeric chars are stripped
                # first so OCR artefacts (e.g. a letter inside "4O5") don't
                # prevent correct parsing.  For "above" monitors the first
                # number is the current reading; later numbers (e.g. a max
                # indicator in "45/100") are intentionally ignored.
                numeric_text = self._strip_non_numeric(raw)
                value = self._first_number(numeric_text)
                return value is not None and value > config.threshold_value

            case "numeric_below":
                numeric_text = self._strip_non_numeric(raw)
                # Use the *first* number found so that composite strings
                # like "45/100" (where 100 is the max, not the current
                # value) do not prevent the alert from firing.
                value = self._first_number(numeric_text)
                return value is not None and value < config.threshold_value

            case "numeric_outside":
                # Alert when the value is outside [threshold_value, threshold_value_high].
                numeric_text = self._strip_non_numeric(raw)
                value = self._first_number(numeric_text)
                if value is None:
                    return False
                return (
                    value < config.threshold_value
                    or value > config.threshold_value_high
                )

            case "altitude_below":
                # Find the first occurrence of "<digits>m" (e.g. "2103m",
                # "102m") and trigger when the numeric part is below the
                # threshold.  The match is case-insensitive so both "m"
                # and "M" are accepted.  The unit letter must not be
                # followed by another word character so that altitude
                # readings are not confused with words like "MHz".
                m = re.search(r"(\d+)[mM](?!\w)", raw)
                if m is None:
                    return False
                return float(m.group(1)) < config.threshold_value

            case "ralt_altitude_below":
                # Use the robust RALT extractor which handles common OCR
                # label and digit artefacts (see extract_altitude for full
                # list of noise patterns).
                alt = extract_altitude(raw)
                return alt is not None and alt < config.threshold_value

            case "ralt_contains":
                # Extract the RALT altitude and check whether trigger_text
                # exactly matches the stringified altitude value.  Use this
                # for audible altitude callouts: set trigger_text to the
                # altitude in metres you want announced (e.g. "500" fires
                # when RALT reads exactly 500 m).
                alt = extract_altitude(raw)
                if alt is None:
                    return False
                return config.trigger_text.strip() == str(alt)

            case _:
                return False

    def extract_number(self, text: str) -> Optional[float]:
        """
        Strip non-numeric characters from *text* and return the first
        number found, or ``None`` if no number is present.

        This is the same extraction used internally by the numeric match
        modes, exposed here so callers (e.g. the UI display) can show the
        value the program will actually compare against the threshold.
        """
        return self._first_number(self._strip_non_numeric(text))

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_non_numeric(text: str) -> str:
        """
        Return *text* with every character that cannot appear in a number
        removed.  Keeps digits, decimal separators (``.`` and ``,``),
        sign characters (``+`` / ``-``), and spaces.

        This is applied before number extraction in numeric match modes so
        that OCR artefacts such as stray letters embedded inside a digit
        string (e.g. ``"4O5"`` → ``"45"``) do not corrupt the reading.
        """
        return _NON_NUMERIC_PATTERN.sub("", text)

    @staticmethod
    def _largest_number(text: str) -> Optional[float]:
        """
        Extract all decimal numbers from *text* and return the largest.

        Returns ``None`` if no numbers are found.
        Supports both period (``3.14``) and comma (``3,14``) as the
        decimal separator, as OCR often confuses the two.
        """
        numbers = re.findall(r"[-+]?\d+(?:[.,]\d+)?", text)
        if not numbers:
            return None
        return max(float(n.replace(",", ".")) for n in numbers)

    @staticmethod
    def _first_number(text: str) -> Optional[float]:
        """
        Return the first decimal number found in *text*.

        Returns ``None`` if no number is found.
        Supports both period (``3.14``) and comma (``3,14``) as the
        decimal separator.
        """
        m = re.search(r"[-+]?\d+(?:[.,]\d+)?", text)
        if m is None:
            return None
        return float(m.group().replace(",", "."))
