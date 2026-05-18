from __future__ import annotations

from .attributes import PlayerAttributes


def calculate_money_gain(
    base_income: int,
    player_attributes: PlayerAttributes,
    specialty_factor: float = 1.0,
) -> int:
    men_factor = 0.75 + (player_attributes.MEN / 200)
    luk_factor = 0.90 + (player_attributes.LUK / 500)
    return max(0, int(base_income * men_factor * luk_factor * specialty_factor))

