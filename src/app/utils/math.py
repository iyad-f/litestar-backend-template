from __future__ import annotations

import math

__all__ = ("round_up",)


def round_up(value: float, decimals: int = 2) -> float:
    """Round a number upward to a given number of decimal places.

    Unlike the built-in :func:`round`, this function always rounds
    toward positive infinity at the specified decimal precision.

    Parameters
    ----------
    value : float
        The number to round.
    decimals : int, optional
        Number of decimal places to keep (the default is 2).

    Returns
    -------
    float
        The rounded number.
    """
    factor = 10**decimals
    return math.ceil(value * factor) / factor
