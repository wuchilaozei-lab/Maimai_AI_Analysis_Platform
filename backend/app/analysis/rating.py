from __future__ import annotations

from math import ceil, floor


RATING_FACTOR_TABLE: tuple[tuple[float, float], ...] = (
    (100.5, 0.224),
    (100.0, 0.216),
    (99.9999, 0.214),
    (99.5, 0.211),
    (99.0, 0.208),
    (98.0, 0.203),
    (97.0, 0.200),
    (94.0, 0.168),
    (90.0, 0.152),
    (80.0, 0.136),
    (75.0, 0.120),
    (70.0, 0.112),
    (60.0, 0.096),
    (50.0, 0.080),
    (40.0, 0.064),
    (30.0, 0.048),
    (20.0, 0.032),
    (10.0, 0.016),
    (0.0, 0.000),
)


def rating_factor(achievement: float) -> float:
    for threshold, factor in RATING_FACTOR_TABLE:
        if achievement >= threshold:
            return factor
    return 0.0


def chart_rating(ds: float, achievement: float) -> int:
    return floor(ds * achievement * rating_factor(achievement))


def achievement_for_target_rating(ds: float, target_rating: int, floor_achievement: float = 97.0) -> float | None:
    if ds <= 0:
        return None
    for idx in range(len(RATING_FACTOR_TABLE) - 1, -1, -1):
        lower, factor = RATING_FACTOR_TABLE[idx]
        if factor <= 0:
            continue
        upper = 100.5 if idx == 0 else RATING_FACTOR_TABLE[idx - 1][0] - 0.0001
        lower = max(lower, floor_achievement)
        if lower > upper:
            continue
        needed = target_rating / (ds * factor)
        candidate = max(lower, needed)
        candidate = ceil(candidate * 10000) / 10000
        if candidate <= upper and chart_rating(ds, candidate) >= target_rating:
            return round(candidate, 4)
    return None
