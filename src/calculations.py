from __future__ import annotations

def percent_change(current: float, previous: float | None) -> float | None:
    return None if previous in (None, 0) else (current / previous - 1) * 100

