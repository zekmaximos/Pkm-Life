from __future__ import annotations

import random
from dataclasses import dataclass, field

from .character import Character
from .names import NameDatabase
from .pokemon import PokemonSpecies
from .reputation import is_banned_from_official_events, reputation_gate_bonus
from .series_battle import SeriesOpponent, run_team_series
from .utils import clamp


NPC_TRAINER_NAMES = [
    "Ash", "Gary", "Misty", "Brock", "Erika", "Sabrina", "Blaine", "Giovanni",
    "Lorelei", "Bruno", "Agatha", "Lance", "Blue", "Silver", "Ethan", "Lyra",
    "Lt. Surge", "Koga", "Ritchie", "Casey", "Duplica", "Todd", "Janine",
    "Elaine", "Trace", "Green", "Leaf", "Chase", "Sora", "Rina", "Hiro",
]

TOURNAMENT_KINDS = {
    "city": {
        "label": "Torneio de Cidade",
        "rounds": 3,
        "base_prize": 400,
        "prize_per_round": 200,
        "entry_fee": 100,
        "rep_reward": 2,
        "level_spread": 3,
        "min_badges": 0,
        "min_reputation": 0,
        "fixed_level_range": None,
    },
    "regional": {
        "label": "Torneio Regional",
        "rounds": 5,
        "base_prize": 1200,
        "prize_per_round": 500,
        "entry_fee": 300,
        "rep_reward": 6,
        "level_spread": 5,
        "min_badges": 2,
        "min_reputation": 10,
        "fixed_level_range": None,
    },
    "kanto_league": {
        "label": "Liga Pokemon de Kanto",
        "rounds": 16,
        "base_prize": 12000,
        "prize_per_round": 900,
        "entry_fee": 1500,
        "rep_reward": 25,
        "level_spread": 0,
        "min_badges": 8,
        "min_reputation": 30,
        "fixed_level_range": [50, 60],
    },
}


@dataclass
class TournamentOpponent:
    name: str
    pokemon_species: str
    pokemon_level: int
    team: list[dict] = field(default_factory=list)


@dataclass
class TournamentResult:
    kind: str
    rounds_won: int
    total_rounds: int
    prize_money: int
    rep_gained: int
    champion: bool
    log: list[str] = field(default_factory=list)


def _available_species_for_tournament(
    pokemon_db: dict[str, PokemonSpecies],
    kind: str,
) -> list[str]:
    allowed_rarities = {"common", "uncommon", "rare"}
    if kind == "kanto_league":
        allowed_rarities.add("very_rare")
    candidates = [
        name for name, species in pokemon_db.items()
        if species.can_be_wild
        and not species.is_legendary
        and not species.is_mythic
        and species.rarity in allowed_rarities
    ]
    return candidates or list(pokemon_db.keys())[:20]


def generate_tournament(
    character: Character,
    pokemon_db: dict[str, PokemonSpecies],
    kind: str = "city",
    names: NameDatabase | None = None,
) -> list[TournamentOpponent]:
    cfg = TOURNAMENT_KINDS.get(kind, TOURNAMENT_KINDS["city"])
    total_rounds = int(cfg["rounds"])
    fixed_range = cfg.get("fixed_level_range")
    spread = int(cfg["level_spread"])

    team_levels = [pokemon.level for pokemon in character.team]
    player_peak = max(team_levels) if team_levels else 10
    species_pool = _available_species_for_tournament(pokemon_db, kind)

    opponents: list[TournamentOpponent] = []
    used_names: set[str] = set()
    for round_num in range(total_rounds):
        if fixed_range:
            min_level, max_level = fixed_range
            npc_level = random.randint(int(min_level), int(max_level))
        else:
            level_offset = round_num - (total_rounds // 2)
            npc_level = int(clamp(player_peak + level_offset + random.randint(-spread, spread), 5, 100))

        if names:
            name = names.random_full_name(used_names)
        else:
            name = random.choice(NPC_TRAINER_NAMES)
            while name in used_names and len(used_names) < len(NPC_TRAINER_NAMES):
                name = random.choice(NPC_TRAINER_NAMES)
        used_names.add(name)

        team = []
        for _ in range(3):
            level = npc_level + random.randint(-2, 2)
            if fixed_range:
                level = int(clamp(level, int(fixed_range[0]), int(fixed_range[1])))
            else:
                level = int(clamp(level, 5, 100))
            team.append({"species": random.choice(species_pool), "level": level})
        opponents.append(TournamentOpponent(name=name, pokemon_species=team[0]["species"], pokemon_level=team[0]["level"], team=team))
    return opponents


def run_tournament(
    character: Character,
    opponents: list[TournamentOpponent],
    pokemon_db: dict[str, PokemonSpecies],
    kind: str = "city",
) -> TournamentResult:
    cfg = TOURNAMENT_KINDS.get(kind, TOURNAMENT_KINDS["city"])
    total_rounds = len(opponents)
    log: list[str] = [f"=== {cfg['label']} ==="]
    rounds_won = 0
    total_prize = 0
    total_rep = 0

    if not character.team:
        return TournamentResult(kind, 0, total_rounds, 0, 0, False, ["Voce nao tem Pokemon para competir."])

    for round_num, opponent in enumerate(opponents, start=1):
        opponent_team = opponent.team or [{"species": opponent.pokemon_species, "level": opponent.pokemon_level}]
        series = [
            SeriesOpponent(opponent.name, member["species"], int(member["level"]))
            for member in opponent_team[:3]
        ]
        log.append(f"Rodada {round_num}/{total_rounds}: melhor de 3 contra {opponent.name}.")
        result = run_team_series(
            character,
            series,
            pokemon_db,
            wins_required=2,
            important=True,
            title=f"Melhor de 3 - {opponent.name}",
        )
        log.extend("  " + line for line in result.log[1:])
        if result.won:
            rounds_won += 1
            round_prize = int(cfg["prize_per_round"])
            total_prize += round_prize
            total_rep += 1
            log.append(f"  Vitoria na rodada! +{round_prize}P, +1 reputacao.")
        else:
            log.append("  Derrota. Eliminado da eliminatoria.")
            break

    champion = rounds_won == total_rounds
    if champion:
        champion_bonus = int(cfg["base_prize"])
        total_prize += champion_bonus
        total_rep += int(cfg["rep_reward"])
        log.append(f"CAMPEAO: premio extra +{champion_bonus}P, reputacao total +{total_rep}.")
    else:
        log.append(f"Resultado final: {rounds_won}/{total_rounds} vitoria(s), +{total_prize}P, +{total_rep} reputacao.")

    return TournamentResult(kind, rounds_won, total_rounds, total_prize, total_rep, champion, log)


def can_enter_tournament(character: Character, kind: str = "city") -> tuple[bool, str]:
    cfg = TOURNAMENT_KINDS.get(kind)
    if not cfg:
        return False, "Torneio desconhecido."
    if character.flags.get("dead"):
        return False, "Game over: o personagem morreu."
    if not character.team:
        return False, "Voce precisa de pelo menos um Pokemon para competir."
    if character.flags.get("in_prison"):
        return False, "Voce nao pode competir enquanto esta preso."
    if is_banned_from_official_events(character):
        return False, "Voce esta banido de eventos oficiais por reputacao negativa ou investigacao."
    if character.age < 10:
        return False, "Voce ainda e jovem demais para torneios."
    min_badges = int(cfg.get("min_badges", 0))
    if len(character.badges) < min_badges:
        return False, f"Voce precisa de pelo menos {min_badges} insignia(s) para este torneio."
    min_reputation = int(cfg.get("min_reputation", 0))
    if character.reputation + reputation_gate_bonus(character) < min_reputation:
        return False, f"Sua reputacao precisa chegar a {min_reputation} para receber convite."
    entry_fee = int(cfg["entry_fee"])
    if character.money < entry_fee:
        return False, f"Inscricao custa {entry_fee}P. Voce tem {character.money}P."
    return True, "ok"
