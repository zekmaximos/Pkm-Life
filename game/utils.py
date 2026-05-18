from __future__ import annotations

import random
from typing import TypeVar


Number = TypeVar("Number", int, float)


def clamp(value: Number, minimum: Number, maximum: Number) -> Number:
    return max(minimum, min(maximum, value))


def clamp_percent(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return clamp(value, minimum, maximum)


def roll_chance(percent_chance: float) -> bool:
    return random.random() <= clamp_percent(percent_chance) / 100


def random_stat_variation(base: int, variation: int = 10, minimum: int = 1, maximum: int = 100) -> int:
    return int(clamp(base + random.randint(-variation, variation), minimum, maximum))

