from __future__ import annotations

from dataclasses import dataclass

from .attributes import PlayerAttributes
from .economy import calculate_money_gain
from .utils import clamp


CAREER_STUDENT = "Estudante da academia"
CAREER_TRAINER = "Treinador"
CAREER_BREEDER = "Criador"
CAREER_COORDINATOR = "Coordenador"

CAREERS = (CAREER_STUDENT, CAREER_TRAINER, CAREER_BREEDER, CAREER_COORDINATOR)

CAREER_RANK_XP = [30, 60, 100, 150, 220]

CAREER_RANK_LABELS = {
    0: "Iniciante",
    1: "Novato",
    2: "Intermediario",
    3: "Avancado",
    4: "Expert",
    5: "Mestre",
}


@dataclass(frozen=True)
class CareerProgress:
    attribute_changes: dict[str, int]
    money_gain: int
    reputation_change: int
    pokemon_xp_bonus: int
    pokemon_happiness_bonus: int
    pokemon_health_bonus: int
    pokemon_beauty_bonus: int
    note: str


def available_careers(age: int, has_pokemon: bool) -> list[str]:
    if age < 10:
        return [CAREER_STUDENT]
    careers = [CAREER_STUDENT]
    if has_pokemon:
        careers.extend([CAREER_TRAINER, CAREER_BREEDER, CAREER_COORDINATOR])
    return careers


def default_career_for_age(age: int) -> str | None:
    if 5 <= age <= 15:
        return CAREER_STUDENT
    return None


def rank_money_multiplier(rank: int) -> float:
    return 1.0 + min(rank, 5) * 0.25


def career_progress(
    career: str | None,
    attributes: PlayerAttributes,
    age: int,
    career_rank: int = 0,
) -> CareerProgress:
    if attributes is None:
        from .attributes import generate_initial_attributes
        attributes = generate_initial_attributes()

    rank_mult = rank_money_multiplier(career_rank)

    if career == CAREER_STUDENT:
        allowance = int(20 * (1 + career_rank * 0.5))
        return CareerProgress(
            attribute_changes={"MEN": 1, "POK": 2 if age <= 15 else 1},
            money_gain=allowance,
            reputation_change=0,
            pokemon_xp_bonus=1 + career_rank,
            pokemon_happiness_bonus=1,
            pokemon_health_bonus=0,
            pokemon_beauty_bonus=0,
            note="Os estudos na academia melhoraram sua leitura sobre Pokemon.",
        )
    if career == CAREER_TRAINER:
        base = calculate_money_gain(110, attributes, specialty_factor=_trainer_specialty(attributes))
        money = int(base * rank_mult)
        return CareerProgress(
            attribute_changes={"PHY": 1, "POK": 1},
            money_gain=money,
            reputation_change=1 + (career_rank // 3),
            pokemon_xp_bonus=12 + attributes.POK // 10 + career_rank * 3,
            pokemon_happiness_bonus=1,
            pokemon_health_bonus=-1,
            pokemon_beauty_bonus=0,
            note="Treinos e pequenas batalhas deixaram sua equipe mais experiente.",
        )
    if career == CAREER_BREEDER:
        base = calculate_money_gain(90, attributes, specialty_factor=1 + ((attributes.POK + attributes.MEN) / 350))
        money = int(base * rank_mult)
        return CareerProgress(
            attribute_changes={"POK": 1, "MEN": 1},
            money_gain=money,
            reputation_change=1,
            pokemon_xp_bonus=4 + career_rank,
            pokemon_happiness_bonus=3 + career_rank,
            pokemon_health_bonus=3 + career_rank,
            pokemon_beauty_bonus=1,
            note="Cuidado constante fortaleceu a saude e o vinculo dos Pokemon.",
        )
    if career == CAREER_COORDINATOR:
        base = calculate_money_gain(95, attributes, specialty_factor=1 + ((attributes.POK + attributes.LUK) / 400))
        money = int(base * rank_mult)
        return CareerProgress(
            attribute_changes={"POK": 1, "LUK": 1},
            money_gain=money,
            reputation_change=2 + (career_rank // 2),
            pokemon_xp_bonus=5 + career_rank,
            pokemon_happiness_bonus=2,
            pokemon_health_bonus=0,
            pokemon_beauty_bonus=3 + career_rank,
            note="Ensaios e apresentacoes melhoraram a presenca da sua equipe.",
        )
    return CareerProgress({}, 0, 0, 0, 0, 0, 0, "Voce passou o ano sem uma rotina definida.")


def try_career_rank_up(
    career: str,
    career_ranks: dict[str, int],
    career_xp: dict[str, int],
    xp_gained: int,
) -> tuple[dict[str, int], dict[str, int], str | None]:
    rank = int(career_ranks.get(career, 0))
    if rank >= 5:
        return career_ranks, career_xp, None
    xp = int(career_xp.get(career, 0)) + xp_gained
    needed = CAREER_RANK_XP[rank]
    message = None
    if xp >= needed:
        xp -= needed
        rank += 1
        career_ranks = {**career_ranks, career: rank}
        message = f"Sua dedicacao como {career} rendeu frutos: rank {CAREER_RANK_LABELS[rank]}!"
    career_xp = {**career_xp, career: xp}
    return career_ranks, career_xp, message


def career_rank_label(career: str, career_ranks: dict[str, int]) -> str:
    rank = int(career_ranks.get(career, 0))
    return CAREER_RANK_LABELS.get(rank, "Iniciante")


def _trainer_specialty(attributes: PlayerAttributes) -> float:
    return float(clamp(0.85 + (attributes.POK + attributes.PHY + attributes.LUK) / 420, 0.85, 1.55))
