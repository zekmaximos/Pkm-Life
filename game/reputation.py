from __future__ import annotations

from dataclasses import dataclass

from .utils import clamp


@dataclass(frozen=True)
class ReputationTier:
    name: str
    min_value: int
    max_value: int
    description: str
    tournament_bonus: int = 0
    income_factor: float = 1.0


REPUTATION_TIERS = [
    ReputationTier("Infame", -100, -21, "Contatos comuns evitam voce.", -20, 0.80),
    ReputationTier("Questionavel", -20, -1, "Sua imagem ainda causa desconfianca.", -5, 0.92),
    ReputationTier("Desconhecido", 0, 9, "Pouca gente conhece sua historia.", 0, 1.00),
    ReputationTier("Localmente conhecido", 10, 24, "Cidades pequenas ja reconhecem seu nome.", 4, 1.04),
    ReputationTier("Respeitado", 25, 49, "Convites e melhores trabalhos ficam mais comuns.", 8, 1.08),
    ReputationTier("Celebridade regional", 50, 79, "Seu nome circula por Kanto.", 14, 1.14),
    ReputationTier("Lenda de Kanto", 80, 100, "Voce virou referencia na regiao.", 20, 1.22),
]


def clamp_reputation(value: int) -> int:
    return int(clamp(value, -100, 100))


def reputation_tier(value: int) -> ReputationTier:
    value = clamp_reputation(value)
    for tier in REPUTATION_TIERS:
        if tier.min_value <= value <= tier.max_value:
            return tier
    return REPUTATION_TIERS[2]


def reputation_summary(value: int) -> str:
    tier = reputation_tier(value)
    return f"{value} - {tier.name}: {tier.description}"


def reputation_gate_bonus(character) -> int:
    bonus = 0
    if getattr(character, "career", None) == "Treinador":
        bonus += 3
    bonus += min(12, len(getattr(character, "badges", [])) * 2)
    rank = character.career_rank() if hasattr(character, "career_rank") else 0
    bonus += min(8, rank * 2)
    return bonus


def reputation_income_factor(value: int) -> float:
    return reputation_tier(value).income_factor


def is_banned_from_official_events(character) -> bool:
    flags = getattr(character, "flags", {})
    return bool(flags.get("official_event_ban")) or clamp_reputation(getattr(character, "reputation", 0)) <= -35


def apply_negative_reputation(character, amount: int, reason: str | None = None) -> int:
    character.reputation = clamp_reputation(getattr(character, "reputation", 0) - abs(amount))
    flags = getattr(character, "flags", {})
    suspicion = int(flags.get("suspicion", 0)) + max(1, abs(amount) // 2)
    flags["suspicion"] = suspicion
    if suspicion >= 25 or character.reputation <= -35:
        flags["official_event_ban"] = True
    if reason and hasattr(character, "add_history"):
        character.add_history(f"Sua reputacao caiu por {reason}.", ["reputation", "crime"])
    return character.reputation
