from __future__ import annotations

import random
from dataclasses import dataclass, field

from .battle import simulate_simple_battle
from .character import Character
from .pokemon import OwnedPokemon, PokemonSpecies, create_owned_pokemon
from .utils import clamp


# Nomes de treinadores NPC para torneios
NPC_TRAINER_NAMES = [
    "Ash", "Gary", "Misty", "Brock", "Erika", "Sabrina", "Blaine", "Giovanni",
    "Lorelei", "Bruno", "Agatha", "Lance", "Blue", "Silver", "Ethan", "Lyra",
    "Lt. Surge", "Koga", "Bugsy", "Whitney", "Morty", "Chuck", "Jasmine",
    "Rui", "Casey", "Duplica", "Todd", "Ritchie", "Falkner", "Pryce",
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


def _available_species_for_level(
    pokemon_db: dict[str, PokemonSpecies],
    target_level: int,
) -> list[str]:
    """Retorna espécies wild/não-lendárias adequadas para o nível alvo."""
    candidates = [
        name for name, sp in pokemon_db.items()
        if sp.can_be_wild and not sp.is_legendary and sp.rarity in {"common", "uncommon", "rare"}
    ]
    return candidates or list(pokemon_db.keys())[:20]


def generate_tournament(
    character: Character,
    pokemon_db: dict[str, PokemonSpecies],
    kind: str = "city",
) -> list[TournamentOpponent]:
    """Gera os oponentes do torneio escalados em relação ao pokémon mais forte do jogador."""
    cfg = TOURNAMENT_KINDS.get(kind, TOURNAMENT_KINDS["city"])
    spread = int(cfg["level_spread"])
    total_rounds = int(cfg["rounds"])

    team_levels = [p.level for p in character.team]
    player_peak = max(team_levels) if team_levels else 10

    species_pool = _available_species_for_level(pokemon_db, player_peak)

    opponents: list[TournamentOpponent] = []
    used_names: set[str] = set()
    for round_num in range(total_rounds):
        # Cada rodada fica ligeiramente mais difícil
        level_offset = round_num - (total_rounds // 2)  # negativo nas primeiras rodadas
        npc_level = int(clamp(player_peak + level_offset, 5, 100))
        # Spread ±spread em torno de npc_level
        npc_level = int(clamp(
            npc_level + random.randint(-spread, spread),
            max(5, player_peak - spread),
            min(100, player_peak + spread + round_num),
        ))

        name = random.choice(NPC_TRAINER_NAMES)
        while name in used_names and len(used_names) < len(NPC_TRAINER_NAMES):
            name = random.choice(NPC_TRAINER_NAMES)
        used_names.add(name)

        species_name = random.choice(species_pool)
        opponents.append(TournamentOpponent(
            name=name,
            pokemon_species=species_name,
            pokemon_level=npc_level,
        ))

    return opponents


def run_tournament(
    character: Character,
    opponents: list[TournamentOpponent],
    pokemon_db: dict[str, PokemonSpecies],
    kind: str = "city",
) -> TournamentResult:
    """Simula o torneio completo. O personagem usa seu pokémon ativo."""
    cfg = TOURNAMENT_KINDS.get(kind, TOURNAMENT_KINDS["city"])
    total_rounds = len(opponents)
    active = character.active_pokemon()

    if active is None:
        return TournamentResult(
            kind=kind,
            rounds_won=0,
            total_rounds=total_rounds,
            prize_money=0,
            rep_gained=0,
            champion=False,
            log=["Voce nao tem nenhum Pokemon ativo para participar do torneio."],
        )

    active_species = pokemon_db.get(active.species)
    if active_species is None:
        return TournamentResult(
            kind=kind, rounds_won=0, total_rounds=total_rounds,
            prize_money=0, rep_gained=0, champion=False,
            log=["Especie do seu Pokemon ativo nao encontrada."],
        )

    log: list[str] = []
    rounds_won = 0
    total_prize = 0
    total_rep = 0
    label = TOURNAMENT_KINDS[kind]["label"]

    log.append(f"=== {label} ===")
    log.append(f"Seu Pokemon: {active.display_name()} Lv.{active.level}")

    for round_num, opponent in enumerate(opponents, start=1):
        opp_species = pokemon_db.get(opponent.pokemon_species)
        if opp_species is None:
            log.append(f"Rodada {round_num}: oponente inválido, pulando.")
            rounds_won += 1
            continue

        log.append(f"\nRodada {round_num}/{total_rounds} — vs {opponent.name} ({opponent.pokemon_species} Lv.{opponent.pokemon_level})")

        won, battle_log = simulate_simple_battle(
            character,
            active,
            active_species,
            f"{opponent.name} - {opponent.pokemon_species}",
            opp_species,
            opponent.pokemon_level,
            important=True,
            species_by_name=pokemon_db,
        )

        # Mostra só o resultado resumido (não todos os scores)
        result_line = next((l for l in battle_log if "venceu" in l or "perdeu" in l), battle_log[-1])
        log.append(f"  {result_line}")

        if won:
            rounds_won += 1
            round_prize = int(cfg["prize_per_round"])
            total_prize += round_prize
            total_rep += 1
            log.append(f"  Vitória! +{round_prize}P")
        else:
            log.append("  Derrota. Eliminado do torneio.")
            break

    champion = rounds_won == total_rounds
    if champion:
        champion_bonus = int(cfg["base_prize"])
        total_prize += champion_bonus
        total_rep += int(cfg["rep_reward"])
        log.append(f"\n🏆 CAMPEÃO DO {label.upper()}! Bônus: +{champion_bonus}P, +{total_rep} reputação.")
    else:
        log.append(f"\nResultado: {rounds_won}/{total_rounds} rodadas vencidas. +{total_prize}P, +{total_rep} reputação.")

    character.money += total_prize
    character.reputation += total_rep

    return TournamentResult(
        kind=kind,
        rounds_won=rounds_won,
        total_rounds=total_rounds,
        prize_money=total_prize,
        rep_gained=total_rep,
        champion=champion,
        log=log,
    )


def can_enter_tournament(character: Character, kind: str = "city") -> tuple[bool, str]:
    cfg = TOURNAMENT_KINDS.get(kind)
    if not cfg:
        return False, "Torneio desconhecido."
    if not character.team:
        return False, "Voce precisa de pelo menos um Pokemon para competir."
    if character.age < 10:
        return False, "Voce ainda e jovem demais para torneios."
    min_badges = int(cfg["min_badges"])
    if len(character.badges) < min_badges:
        return False, f"Voce precisa de pelo menos {min_badges} insignia(s) para este torneio."
    entry_fee = int(cfg["entry_fee"])
    if character.money < entry_fee:
        return False, f"Inscricao custa {entry_fee}P. Voce tem {character.money}P."
    return True, "ok"
