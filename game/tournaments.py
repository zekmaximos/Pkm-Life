from __future__ import annotations

import random
from dataclasses import dataclass, field

from .battle import simulate_simple_battle
from .character import Character
from .pokemon import PokemonSpecies
from .reputation import reputation_gate_bonus
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

        name = random.choice(NPC_TRAINER_NAMES)
        while name in used_names and len(used_names) < len(NPC_TRAINER_NAMES):
            name = random.choice(NPC_TRAINER_NAMES)
        used_names.add(name)

        opponents.append(TournamentOpponent(
            name=name,
            pokemon_species=random.choice(species_pool),
            pokemon_level=npc_level,
        ))
    return opponents


def _best_team_member(character: Character, pokemon_db: dict[str, PokemonSpecies]):
    candidates = [
        pokemon for pokemon in character.team
        if pokemon.current_health > 0 and pokemon.status != "badly_injured" and pokemon.species in pokemon_db
    ]
    if not candidates:
        return character.active_pokemon()
    return max(candidates, key=lambda pokemon: pokemon.level * 2 + pokemon.combat + pokemon.healthy * 0.4)


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
        active = _best_team_member(character, pokemon_db)
        if active is None or active.species not in pokemon_db:
            log.append("Sua equipe nao conseguiu continuar.")
            break
        active_species = pokemon_db[active.species]
        opponent_species = pokemon_db.get(opponent.pokemon_species)
        if opponent_species is None:
            log.append(f"Rodada {round_num}: oponente invalido, vitoria administrativa.")
            rounds_won += 1
            continue

        log.append(
            f"Rodada {round_num}/{total_rounds}: {active.display_name()} Lv.{active.level} "
            f"vs {opponent.name} com {opponent.pokemon_species} Lv.{opponent.pokemon_level}"
        )
        won, battle_log = simulate_simple_battle(
            character,
            active,
            active_species,
            f"{opponent.name} - {opponent.pokemon_species}",
            opponent_species,
            opponent.pokemon_level,
            important=True,
            species_by_name=pokemon_db,
        )
        result_line = next((line for line in battle_log if "venceu" in line or "perdeu" in line), battle_log[-1])
        log.append(f"  {result_line}")
        if won:
            rounds_won += 1
            round_prize = int(cfg["prize_per_round"])
            total_prize += round_prize
            total_rep += 1
            log.append(f"  Vitoria! +{round_prize}P, +1 reputacao.")
        else:
            active.current_health = 0
            active.status = "badly_injured"
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
    if not character.team:
        return False, "Voce precisa de pelo menos um Pokemon para competir."
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
