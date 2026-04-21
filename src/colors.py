"""
colors.py – Colour-threshold detection for screen regions.

Computes the percentage of pixels in a PIL image that fall within a
given Euclidean distance of a target colour.  Fires when that
percentage exceeds the configured threshold.
"""

from __future__ import annotations

from typing import Optional

try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

from src.monitor_model import ColorConfig


class ColorDetector:
    """Checks whether a screen region contains enough of a target colour."""

    def check(self, img: "Image.Image", config: ColorConfig) -> bool:
        """
        Return ``True`` when the fraction of matching pixels in *img*
        meets or exceeds ``config.threshold_percent``.

        Parameters
        ----------
        img:    PIL image of the captured region (any mode).
        config: ``ColorConfig`` with target colour, tolerance, and
                threshold percent.
        """
        pct = self.matching_percent(img, config)
        if pct is None:
            return False
        return pct >= config.threshold_percent

    def matching_percent(
        self, img: "Image.Image", config: ColorConfig
    ) -> Optional[float]:
        """
        Return the percentage (0–100) of pixels in *img* whose Euclidean
        distance from ``config.target_color`` is ≤ ``config.tolerance``.

        Returns ``None`` if the computation is not possible.
        """
        if not _PIL_AVAILABLE or not _NUMPY_AVAILABLE:
            return None

        try:
            arr = np.array(img.convert("RGB"), dtype=np.int32)
        except Exception:
            return None

        target = np.array(config.target_color[:3], dtype=np.int32)
        diff = arr - target                                # (H, W, 3)
        dist = np.sqrt(np.sum(diff ** 2, axis=2))         # (H, W)
        matching = np.sum(dist <= config.tolerance)
        total = arr.shape[0] * arr.shape[1]
        if total == 0:
            return 0.0
        return float(matching) / float(total) * 100.0

    @staticmethod
    def average_color(img: "Image.Image") -> Optional[tuple]:
        """
        Return the average (R, G, B) of *img* as a tuple of ints.

        Returns ``None`` on failure.
        """
        if not _PIL_AVAILABLE or not _NUMPY_AVAILABLE:
            return None
        try:
            arr = np.array(img.convert("RGB"), dtype=np.float32)
            avg = arr.mean(axis=(0, 1))
            return (int(avg[0]), int(avg[1]), int(avg[2]))
        except Exception:
            return None
