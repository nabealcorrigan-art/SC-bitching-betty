"""
ocr.py – OCR text extraction and threshold checking.

Wraps *pytesseract* and provides helper logic for matching OCR results
against the conditions defined in ``OcrConfig``.
"""

from __future__ import annotations

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

from src.monitor_model import OcrConfig


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
            return re.sub(r"[^a-zA-Z0-9\s.,]", "", raw)
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
                value = self._largest_number(raw)
                return value is not None and value > config.threshold_value

            case "numeric_below":
                # Use the *first* number found so that composite strings
                # like "45/100" (where 100 is the max, not the current
                # value) do not prevent the alert from firing.
                value = self._first_number(raw)
                return value is not None and value < config.threshold_value

            case _:
                return False

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

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
