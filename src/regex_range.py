"""
regex_range.py – Generate a regular expression that matches any integer in a
numeric range.

Public API
----------
    numeric_range_to_regex(lo, hi) -> str

The returned pattern is wrapped in word boundaries (``\\b``) so that it will
not match a substring of a larger number when used with ``re.search``.

Only non-negative integers are supported; this is sufficient for the game
values (health, shield, speed …) that SC Bitching Betty monitors.

Algorithm overview
------------------
1. If *lo* and *hi* have different digit counts the range is split at each
   power-of-ten boundary and processed recursively.
2. For same-length pairs ``_range_patterns_fixed_len`` finds the longest
   common prefix, then:
   - The *low* boundary's trailing digits (from the first differing position)
     are handled by a recursive call covering  ``lo_tail … 999…``.
   - The *high* boundary's trailing digits are handled by a recursive call
     covering ``000… … hi_tail``.
   - The remaining "full" middle digits are expressed as a single digit class
     followed by ``\\d{k}`` wildcards.
"""

from __future__ import annotations

from typing import List


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def numeric_range_to_regex(lo: int, hi: int) -> str:
    """
    Return a regex pattern that matches every non-negative integer in
    ``[lo, hi]`` (inclusive) as a *whole number* (using ``\\b`` word
    boundaries).

    Parameters
    ----------
    lo:
        Lower bound (non-negative integer, <= *hi*).
    hi:
        Upper bound (non-negative integer, >= *lo*).

    Raises
    ------
    ValueError
        If either bound is negative or *lo* > *hi*.

    Examples
    --------
    >>> numeric_range_to_regex(50, 150)
    '\\\\b(?:[5-9]\\\\d|1[0-4]\\\\d|150)\\\\b'
    >>> numeric_range_to_regex(0, 9)
    '\\\\b\\\\d\\\\b'
    >>> numeric_range_to_regex(42, 42)
    '\\\\b42\\\\b'
    """
    if lo < 0 or hi < 0:
        raise ValueError("Only non-negative integers are supported.")
    if lo > hi:
        raise ValueError(f"Lower bound ({lo}) must be <= upper bound ({hi}).")

    patterns = _collect_patterns(lo, hi)
    inner = "|".join(patterns)
    if len(patterns) > 1:
        inner = f"(?:{inner})"
    return rf"\b{inner}\b"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _collect_patterns(lo: int, hi: int) -> List[str]:
    """Return a list of regex fragments (to be OR-joined) for ``[lo, hi]``."""
    if lo > hi:
        return []

    lo_s = str(lo)
    hi_s = str(hi)

    if len(lo_s) == len(hi_s):
        return _range_patterns_fixed_len(lo_s, hi_s)

    # Different digit counts – split at the first power-of-ten above lo.
    boundary = 10 ** len(lo_s)
    return _collect_patterns(lo, boundary - 1) + _collect_patterns(boundary, hi)


def _range_patterns_fixed_len(lo_s: str, hi_s: str) -> List[str]:
    """
    Generate regex fragments for all integers ``[lo_s, hi_s]`` where both
    arguments are digit strings of the *same* length.
    """
    assert len(lo_s) == len(hi_s), "strings must have equal length"

    if lo_s == hi_s:
        return [lo_s]

    n = len(lo_s)

    # Find the length of the longest common prefix.
    prefix_len = 0
    while prefix_len < n and lo_s[prefix_len] == hi_s[prefix_len]:
        prefix_len += 1

    prefix = lo_s[:prefix_len]
    lo_d = int(lo_s[prefix_len])
    hi_d = int(hi_s[prefix_len])
    lo_tail = lo_s[prefix_len + 1:]
    hi_tail = hi_s[prefix_len + 1:]
    suffix_len = n - prefix_len - 1  # length of lo_tail / hi_tail

    # Base case: no further varying digits.
    if suffix_len == 0:
        return [prefix + _digit_class(lo_d, hi_d)]

    all_zeros = "0" * suffix_len
    all_nines = "9" * suffix_len

    patterns: List[str] = []
    lo_full_d = lo_d  # first digit that may contribute "full" suffix ranges

    # Handle lo_d's partial suffix (lo_tail doesn't start at 000…).
    if lo_tail != all_zeros:
        for sub in _range_patterns_fixed_len(lo_tail, all_nines):
            patterns.append(prefix + str(lo_d) + sub)
        lo_full_d = lo_d + 1

    # Handle hi_d's partial suffix (hi_tail doesn't end at 999…).
    hi_partial: List[str] = []
    hi_full_d = hi_d
    if hi_tail != all_nines:
        for sub in _range_patterns_fixed_len(all_zeros, hi_tail):
            hi_partial.append(prefix + str(hi_d) + sub)
        hi_full_d = hi_d - 1

    # Middle: digits [lo_full_d … hi_full_d] with any suffix.
    if lo_full_d <= hi_full_d:
        patterns.append(prefix + _digit_class(lo_full_d, hi_full_d) + r"\d" * suffix_len)

    patterns.extend(hi_partial)
    return patterns


def _digit_class(lo_d: int, hi_d: int) -> str:
    """Return the shortest regex fragment matching digits in ``[lo_d, hi_d]``."""
    if lo_d == hi_d:
        return str(lo_d)
    if lo_d == 0 and hi_d == 9:
        return r"\d"
    return f"[{lo_d}-{hi_d}]"
