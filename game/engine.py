from __future__ import annotations

import json
from pathlib import Path
import random
from dataclasses import dataclass

from .academy import apply_focus_progress, focus_choices, focus_label, set_focus
from .battle import get_type_factor, simulate_simple_battle
from .auto_year import automatic_encounter_chance, decide_auto_encounter_action
from .careers import available_careers, career_progress, try_career_rank_up, career_rank_label
from .capture import try_capture
from .character import Character
from .city import CityServices
from .contests import ContestResult, run_contest
from .breeding import breed_success_chance, create_bred_egg
from .eggs import choose_egg_tier, create_random_egg
from .events import LifeEvent, apply_choice_result, choose_weighted_event, should_roll_life_event
from .gyms import GymTemplate, generate_gyms
from .inventory import Item, add_item, consume_item
from .locations import Location
from .lifestyle import (
    BLACK_MARKET_RARITY_MULT,
    COURSES,
    LIFESTYLE_OFFERS,
    TRIPS,
    city_economy_tier,
    course_effect_percent,
    courses_for_tier,
    egg_sell_price,
    item_sell_price,
    offers_for_tier,
    pokemon_market_value,
    trips_for_tier,
)
from .map_grid import KantoGrid, load_grid
from .names import NameDatabase
from .mortality import check_mortality, is_dead
from .pokemon import PokemonSpecies, assign_evolution_stages, create_owned_pokemon, coherent_pokemon_level, minimum_level_for_species
from .prison import imprison, progress_prison_time
from .progression import progress_year
from .progression import grant_pokemon_xp
from .reputation import apply_negative_reputation, clamp_reputation, reputation_summary
from .series_battle import SeriesOpponent, estimate_series_chance, run_team_series
from .year_simulation import simulate_year_activities, apply_activity_results
from .economy import calculate_money_gain
from .tournaments import (
    generate_tournament, run_tournament, can_enter_tournament,
    TOURNAMENT_KINDS, TournamentResult,
)


DATA_DIR = Path("data")
MIN_CHILD_ACTION_AGE = 5
MIN_JOURNEY_ACTION_AGE = 10


def _contest_ribbon_label(category: str, difficulty: str) -> str:
    symbols = {
        "beauty": "✦",
        "cute": "♡",
        "cool": "◆",
        "smart": "◇",
        "mysterious": "☾",
    }
    names = {
        "beauty": "Beauty",
        "cute": "Cute",
        "cool": "Cool",
        "smart": "Smart",
        "mysterious": "Mysterious",
    }
    symbol = symbols.get(category, "✦")
    name = names.get(category, category.title())
    return f"{symbol} Ribbon {name} {difficulty.title()}"


@dataclass(frozen=True)
class TravelResult:
    ok: bool
    message: str

    def __bool__(self) -> bool:
        return self.ok

    def __iter__(self):
        yield self.ok
        yield self.message


class GameEngine:
    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        self.data_dir = data_dir
        self.pokemon: dict[str, PokemonSpecies] = {}
        self.childhood_events: list[LifeEvent] = []
        self.journey_events: list[LifeEvent] = []
        self.cities: list[dict] = []
        self.gym_templates: list[GymTemplate] = []
        self.starters: list[str] = []
        self.items: dict[str, Item] = {}
        self.encounters: dict[str, dict] = {}
        self.locations: dict[str, Location] = {}
        self.location_ids_by_name: dict[str, str] = {}
        self.city_services: dict[str, CityServices] = {}
        self.name_database: NameDatabase | None = None
        self.grid: KantoGrid | None = None
        self.load_data()

    def load_data(self) -> None:
        self.pokemon = {
            item["name"]: PokemonSpecies.from_dict(item)
            for item in self._load_json("pokemon_kanto.json")
        }
        assign_evolution_stages(self.pokemon)
        self.childhood_events = [LifeEvent.from_dict(item) for item in self._load_json("events_childhood.json")]
        self.journey_events = [LifeEvent.from_dict(item) for item in self._load_json("events_journey.json")]
        self.cities = self._load_json("cities_kanto.json")
        self.gym_templates = [GymTemplate.from_dict(item) for item in self._load_json("gyms_kanto.json")]
        self.starters = self._load_json("starters.json")
        self.name_database = NameDatabase.from_dict(self._load_json_object("name_database.json"))
        self.locations = {
            location.location_id: location
            for location in (Location.from_dict(item) for item in self._load_json("locations_kanto.json"))
        }
        self.location_ids_by_name = {location.name: location_id for location_id, location in self.locations.items()}
        self.encounters = {
            location.get("location_id", location["id"]): location
            for location in self._load_json("encounters_kanto.json")
        }
        self.items = {
            item.name: item
            for item in (Item.from_dict(item_data) for item_data in self._load_json("items.json"))
        }
        self.city_services = {
            services.city: services
            for services in (CityServices.from_dict(item) for item in self._load_json("city_services_kanto.json"))
        }
        self.grid = load_grid(self.data_dir)

    def _load_json(self, filename: str) -> list[dict] | list[str]:
        path = self.data_dir / filename
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_json_object(self, filename: str) -> dict:
        path = self.data_dir / filename
        return json.loads(path.read_text(encoding="utf-8"))

    def create_character(self, name: str, hometown: str = "Pallet Town") -> Character:
        character = Character(name=name.strip() or "Red", hometown=hometown, current_city=hometown)
        self.ensure_world_generated(character)
        character.set_attr_soft_caps()
        character.add_history(f"Voce nasceu em {hometown}, na regiao de Kanto.", ["birth"])
        return character

    def ensure_world_generated(self, character: Character) -> None:
        if character.generated_gyms:
            return
        if self.name_database is None:
            raise RuntimeError("Name database was not loaded.")
        character.generated_gyms = generate_gyms(self.gym_templates, self.pokemon, self.name_database)

    def advance_time(self, character: Character, months: int = 12) -> LifeEvent | None:
        if months not in {3, 6, 12}:
            raise ValueError("O avanço de tempo deve ser de 3, 6 ou 12 meses.")
        if is_dead(character):
            character.flags["last_year_report"] = self._death_report(character)
            return None
        self._reset_period_action_flags(character)
        character.flags["current_period_months"] = months
        if character.flags.get("in_prison"):
            before = self._year_snapshot(character)
            handled, prison_note = progress_prison_time(character, months)
            mortality = check_mortality(character, months, "prison", character.health - int(before["health"]))
            if months == 12:
                character.age += 1
            else:
                progress = int(character.flags.get("age_month_progress", 0)) + months
                while progress >= 12:
                    progress -= 12
                    character.age += 1
                character.flags["age_month_progress"] = progress
            notes = [prison_note] if prison_note else []
            if mortality.died:
                notes.append(f"Game over: morte por {mortality.cause}.")
            report = self.build_annual_report(character, before, notes, {"health_reasons": [{"delta": character.health - before["health"], "reason": "tempo na prisao"}]})
            character.flags["last_year_report"] = report.replace("Resumo anual", f"Resumo de {months} meses", 1)
            return None
        if months == 12 and int(character.flags.get("age_month_progress", 0)) == 0:
            return self.advance_year(character)

        if character.health <= 0:
            collapse = check_mortality(character, months, "illness", -30)
            if collapse.died:
                character.flags["last_year_report"] = self._death_report(character)
                return None
            hosp_note = self._apply_hospitalization(character)
            character.add_history(hosp_note, ["health", "hospitalization"])

        before = self._year_snapshot(character)
        old_age = character.age
        month_progress = int(character.flags.get("age_month_progress", 0)) + months
        while month_progress >= 12:
            month_progress -= 12
            character.age += 1
            if character.age in {5, 10, 15, 18, 20, 25, 30, 40, 50, 60, 70}:
                character.add_history(f"Voce completou {character.age} anos.", ["age", "milestone"])
        character.flags["age_month_progress"] = month_progress

        period_notes: list[str] = []
        period_notes.extend(self._progress_partial_period(character, months))
        partial_hatches = character.flags.pop("last_hatched_eggs", [])
        if character.career and character.age > old_age:
            self._increment_career_year(character)
            character.career_ranks, character.career_xp, rank_msg = try_career_rank_up(
                character.career, character.career_ranks, character.career_xp, 1 + months // 6
            )
            if rank_msg:
                period_notes.append(rank_msg)
                character.add_history(rank_msg, ["career", "rank_up"])

        if character.age >= 10 and not character.flags.get("oak_event_done") and not self.character_has_pokemon(character):
            report = self.build_annual_report(character, before, period_notes)
            character.flags["last_year_report"] = report.replace("Resumo anual", f"Resumo de {months} meses", 1)
            return self.professor_oak_event()

        activities = simulate_year_activities(character, self.pokemon, months=months)
        activity_notes, activity_report = apply_activity_results(character, activities, self.pokemon)
        mortality = check_mortality(
            character,
            months,
            self._mortality_context(activity_report),
            character.health - int(before["health"]),
        )
        if mortality.died:
            period_notes.append(f"Game over: morte por {mortality.cause}.")
        elif character.health <= 0:
            hosp_note = self._apply_hospitalization(character)
            period_notes.append(hosp_note)
            character.add_history(hosp_note, ["health", "hospitalization"])
            activity_report.setdefault("health_reasons", []).append({"delta": 30, "reason": "hospitalizacao apos colapso"})
        if partial_hatches:
            activity_report.setdefault("eggs", []).extend(partial_hatches)
        for note in activity_notes:
            period_notes.append(note)
            if _is_history_worthy(note):
                character.add_history(note, ["activity"])
        for note in self._maybe_breeder_auto_egg(character, months):
            period_notes.append(note)
            egg_entry = character.flags.pop("last_breeding_egg", None)
            activity_report.setdefault("eggs", []).append(egg_entry or {"note": note})

        if months == 12:
            for note in self._apply_career_expenses_and_business(character):
                period_notes.append(note)
            for note in self._apply_career_goal_milestones(character):
                period_notes.append(note)
                character.add_history(note, ["career", "milestone"])

        gym_invite = self.resolve_automatic_gym_invite(character)
        if gym_invite:
            period_notes.append(gym_invite)
            character.add_history(gym_invite, ["gym", "invite"])

        report = self.build_annual_report(character, before, period_notes, activity_report)
        character.flags["last_year_report"] = report.replace("Resumo anual", f"Resumo de {months} meses", 1)
        character.flags["last_year_activity_report"] = activity_report
        if mortality.died:
            return None

        event_pool = self.childhood_events if character.age < 10 else self.journey_events
        city_focus = self._event_focus_for(character)
        if random.random() > months / 12:
            return None
        if not should_roll_life_event(character, event_pool, city_focus):
            return None
        return choose_weighted_event(character, event_pool, city_focus)

    def _progress_partial_period(self, character: Character, months: int) -> list[str]:
        notes: list[str] = []
        fraction = months / 12
        if character.career is None:
            from .careers import default_career_for_age
            default_career = default_career_for_age(character.age)
            if default_career:
                character.career = default_career
                notes.append(f"Voce entrou na rotina de {default_career}.")

        focus_note = apply_focus_progress(character, months)
        if focus_note:
            notes.append(focus_note)

        career = career_progress(character.career, character.attributes, character.age, character.career_rank())
        scaled_money = int(career.money_gain * fraction)
        if scaled_money:
            character.money = max(0, character.money + scaled_money)
            notes.append(f"Voce ganhou {scaled_money} Pokedollar no periodo.")
        scaled_rep = int(career.reputation_change * fraction)
        if scaled_rep:
            character.reputation = clamp_reputation(character.reputation + scaled_rep)

        attr_deltas = {
            key: max(1, int(round(value * fraction)))
            for key, value in career.attribute_changes.items()
            if value > 0 and random.random() <= max(fraction, 0.30)
        }
        character.modify_attributes(attr_deltas)

        for pokemon in character.team:
            xp = int((career.pokemon_xp_bonus + 18 + character.attributes.POK // 6) * fraction)
            if character.career == "Treinador":
                xp += int((12 + character.attributes.PHY // 8) * fraction)
            elif character.career == "Criador":
                xp += int((6 + character.attributes.MEN // 12) * fraction)
                pokemon.happiness = min(100, pokemon.happiness + max(1, int(2 * fraction)))
                pokemon.healthy = min(100, pokemon.healthy + max(1, int(2 * fraction)))
            elif character.career == "Coordenador":
                xp += int((8 + character.attributes.LUK // 12) * fraction)
                pokemon.beauty = min(100, pokemon.beauty + max(1, int(2 * fraction)))
            for level_note in grant_pokemon_xp(pokemon, xp, self.pokemon):
                notes.append(level_note)

        notes.extend(self._progress_eggs_by_months(character, months))
        return notes

    def _progress_eggs_by_months(self, character: Character, months: int) -> list[str]:
        notes: list[str] = []
        if not character.eggs:
            return notes
        egg_months = dict(character.flags.get("egg_month_progress", {}))
        hatch_report = list(character.flags.get("last_hatched_eggs", []))
        remaining = []
        for egg in character.eggs:
            accrued = int(egg_months.get(egg.egg_id, 0)) + months
            while accrued >= 12:
                accrued -= 12
                egg.progress += 1
            if egg.progress >= egg.years_to_hatch:
                species = self.pokemon.get(egg.species)
                if species:
                    pokemon = create_owned_pokemon(species, level=1, origin=f"chocado de ovo: {egg.origin}", species_by_name=self.pokemon)
                    destination = character.add_pokemon(pokemon)
                    location = "equipe" if destination == "team" else "Box"
                    character.register_caught(species.name)
                    notes.append(f"Um ovo {egg.color} chocou e revelou {pokemon.species}, enviado para {location}.")
                    hatch_report.append({
                        "action": "hatched",
                        "species": pokemon.species,
                        "destination": location,
                        "source": egg.origin,
                        "tier": egg.rarity_tier,
                    })
                egg_months.pop(egg.egg_id, None)
            else:
                egg_months[egg.egg_id] = accrued
                remaining.append(egg)
        character.eggs = remaining
        character.flags["egg_month_progress"] = egg_months
        if hatch_report:
            character.flags["last_hatched_eggs"] = hatch_report
        return notes

    def advance_year(self, character: Character) -> LifeEvent | None:
        character.flags["current_period_months"] = 12
        if is_dead(character):
            character.flags["last_year_report"] = self._death_report(character)
            return None
        self._reset_period_action_flags(character)
        if character.flags.get("in_prison"):
            return self.advance_time(character, 12)
        # --- Verifica hospitalização por saúde zerada ---
        if character.health <= 0:
            collapse = check_mortality(character, 12, "illness", -30)
            if collapse.died:
                character.flags["last_year_report"] = self._death_report(character)
                return None
            hosp_note = self._apply_hospitalization(character)
            character.add_history(hosp_note, ["health", "hospitalization"])

        before = self._year_snapshot(character)
        character.age += 1
        # Marcos de idade relevantes entram no histórico; anos comuns, não
        if character.age in {5, 10, 15, 18, 20, 25, 30, 40, 50, 60, 70}:
            character.add_history(f"Voce completou {character.age} anos.", ["age", "milestone"])

        year_notes: list[str] = []
        # Passa rank de carreira para progress_year via career_progress
        for note in progress_year(character, self.pokemon):
            year_notes.append(note)
            if _is_history_worthy(note):
                character.add_history(note, ["progression"])
        yearly_hatches = character.flags.pop("last_hatched_eggs", [])

        # XP de carreira automático por passar o ano
        if character.career:
            self._increment_career_year(character)
            rank_xp = 3 + (1 if character.career != "Estudante da academia" else 0)
            character.career_ranks, character.career_xp, rank_msg = try_career_rank_up(
                character.career, character.career_ranks, character.career_xp, rank_xp
            )
            if rank_msg:
                year_notes.append(rank_msg)
                character.add_history(rank_msg, ["career", "rank_up"])

        for note in self._apply_career_expenses_and_business(character):
            year_notes.append(note)
        for note in self._apply_career_goal_milestones(character):
            year_notes.append(note)
            character.add_history(note, ["career", "milestone"])

        if character.age == 10 and not character.flags.get("oak_event_done") and not self.character_has_pokemon(character):
            report = self.build_annual_report(character, before, year_notes)
            character.flags["last_year_report"] = report
            return self.professor_oak_event()

        # Simula todas as atividades do ano (batalhas, treinos, trabalho, capturas)
        activities = simulate_year_activities(character, self.pokemon)
        activity_notes, activity_report = apply_activity_results(character, activities, self.pokemon)
        mortality = check_mortality(
            character,
            12,
            self._mortality_context(activity_report),
            character.health - int(before["health"]),
        )
        if mortality.died:
            year_notes.append(f"Game over: morte por {mortality.cause}.")
        elif character.health <= 0:
            hosp_note = self._apply_hospitalization(character)
            year_notes.append(hosp_note)
            character.add_history(hosp_note, ["health", "hospitalization"])
            activity_report.setdefault("health_reasons", []).append({"delta": 30, "reason": "hospitalizacao apos colapso"})
        if yearly_hatches:
            activity_report.setdefault("eggs", []).extend(yearly_hatches)
        for note in activity_notes:
            year_notes.append(note)
            if _is_history_worthy(note):
                character.add_history(note, ["activity"])
        for note in self._maybe_breeder_auto_egg(character, 12):
            year_notes.append(note)
            egg_entry = character.flags.pop("last_breeding_egg", None)
            activity_report.setdefault("eggs", []).append(egg_entry or {"note": note})

        gym_invite = self.resolve_automatic_gym_invite(character)
        if gym_invite:
            year_notes.append(gym_invite)
            character.add_history(gym_invite, ["gym", "invite"])

        report = self.build_annual_report(character, before, year_notes, activity_report)
        character.flags["last_year_report"] = report
        character.flags["last_year_activity_report"] = activity_report
        if mortality.died:
            return None
        # Relatório anual fica SOMENTE em flags, não polui o histórico

        event_pool = self.childhood_events if character.age < 10 else self.journey_events
        city_focus = self._event_focus_for(character)
        if not should_roll_life_event(character, event_pool, city_focus):
            return None
        return choose_weighted_event(character, event_pool, city_focus)

    def _mortality_context(self, activity_report: dict) -> str:
        battles = activity_report.get("battles", {})
        health_delta = int(activity_report.get("health_delta", 0))
        if int(battles.get("losses", 0)) > 0 and health_delta <= -35:
            return "fight"
        reasons = " ".join(str(item.get("reason", "")) for item in activity_report.get("health_reasons", []))
        if "doenca" in reasons or "sick" in reasons:
            return "illness"
        return "life"

    def _death_report(self, character: Character) -> str:
        cause = character.flags.get("death_cause", "morte")
        age = character.flags.get("death_age", character.age)
        return f"Game over\n{character.name} morreu aos {age} anos por {cause}."

    def _apply_hospitalization(self, character: Character) -> str:
        """Aplica penalidades de hospitalização quando saúde chega a 0."""
        cost = min(character.money, 200 + len(character.team) * 50)
        character.money = max(0, character.money - cost)
        character.health = 30  # recuperação mínima
        for pokemon in character.team:
            pokemon.healthy = max(1, pokemon.healthy - 10)
            if pokemon.status == "healthy":
                pokemon.status = "tired"
        note = (
            f"Sua saude colapsou completamente. Voce foi hospitalizado, "
            f"perdeu {cost} Pokedollar em tratamentos e sua equipe ficou abalada."
        )
        return note

    def resolve_automatic_year_encounter(self, character: Character) -> list[str]:
        location = self.get_location(character.current_city)
        has_encounters = bool(location and location.encounter_enabled)
        if random.random() > automatic_encounter_chance(character, has_encounters):
            return []
        encounter = self._choose_encounter(character.current_city)
        if not encounter:
            return []
        species = self.pokemon[encounter["species"]]
        level = coherent_pokemon_level(species, random.randint(encounter["min_level"], encounter["max_level"]), self.pokemon)
        notes = [f"Durante o ano, voce encontrou um {species.name} selvagem de nivel {level} em {character.current_city}."]
        if not character.team:
            health_loss = random.randint(2, 7)
            character.health = max(1, character.health - health_loss)
            character.register_seen(species.name)
            notes.append(
                f"Sem Pokemon para se defender, voce fugiu do {species.name} e recebeu alguns golpes. Saude -{health_loss}."
            )
            return notes
        has_ball = any(
            amount > 0 and name in self.items and self.items[name].item_type == "capture"
            for name, amount in character.inventory.items()
        )
        action = decide_auto_encounter_action(character, species, level, has_ball)
        if action == "capture":
            success, message = self.capture_wild(character, species.name, level)
            notes.append(f"Captura automatica: {message}")
        elif action == "battle":
            won, log = self.battle_wild(character, species.name, level)
            notes.append(f"Batalha automatica: {log[-2] if len(log) >= 2 else log[-1]}")
        else:
            character.modify_attributes({"POK": 1})
            notes.append(f"Voce observou {species.name} e aprendeu sobre seu comportamento. POK +1.")
        return notes

    def _maybe_breeder_auto_egg(self, character: Character, months: int) -> list[str]:
        if character.career != "Criador" or len(character.team) < 2:
            return []
        chance = (0.12 + character.attributes.POK * 0.001 + character.career_rank("Criador") * 0.025) * (months / 12)
        if random.random() > min(0.42, chance):
            return []
        first, second = random.sample(character.team, 2)
        success, egg, message = create_bred_egg(character, first, second, self.pokemon)
        if success and egg:
            character.eggs.append(egg)
            character.reputation = clamp_reputation(character.reputation + 1)
            character.add_history(message, ["breeding", "egg"])
            character.flags["last_breeding_egg"] = {
                "action": "created",
                "species": egg.species,
                "tier": egg.rarity_tier,
                "color": egg.color,
                "source": "criacao automatica",
                "parents": [first.species, second.species],
            }
            return [message]
        return []

    def resolve_automatic_gym_invite(self, character: Character) -> str | None:
        gym = self.get_city_gym(character)
        if not gym or not character.team or gym["badge"] in character.badges:
            return None
        if character.flags.get(f"gym_invite_{gym['id']}_age") == character.age:
            return None
        strongest = max(pokemon.level for pokemon in character.team)
        recommended = int(gym["recommended_level"])
        gap = recommended - strongest
        chance = 0.18
        if abs(gap) <= 3:
            chance += 0.22
        if character.career == "Treinador":
            chance += 0.12
        if character.reputation > 5:
            chance += 0.05
        if gap > 8:
            chance *= 0.35
        if random.random() > min(0.65, chance):
            return None
        character.flags[f"gym_invite_{gym['id']}_age"] = character.age
        if gap > 5:
            advice = "O assistente avisou que sua equipe talvez precise de mais preparo."
        elif gap < -6:
            advice = "O assistente comentou que o lider ajustaria o desafio ao seu nivel atual."
        else:
            advice = "O assistente disse que sua equipe parece pronta para tentar."
        return f"Convite de ginasio em {gym['city']}: {gym['leader']} aceita seu desafio pela {gym['badge']}. {advice}"

    def _year_snapshot(self, character: Character) -> dict:
        return {
            "money": character.money,
            "team_count": len(character.team),
            "box_count": len(character.box),
            "egg_count": len(character.eggs),
            "badges": len(character.badges),
            "levels": {id(pokemon): pokemon.level for pokemon in character.team + character.box},
            "species": {id(pokemon): pokemon.species for pokemon in character.team + character.box},
            "health": character.health,
            "city": character.current_city,
        }

    def build_annual_report(self, character: Character, before: dict, notes: list[str], activity_report: dict | None = None) -> str:
        activity_report = activity_report or {}
        money_delta = character.money - int(before["money"])
        health_delta = character.health - int(before["health"])
        new_pokemon = (len(character.team) + len(character.box)) - int(before["team_count"]) - int(before["box_count"])
        egg_delta = len(character.eggs) - int(before["egg_count"])
        badge_delta = len(character.badges) - int(before["badges"])
        level_ups = 0
        evolutions: list[str] = []
        for pokemon in character.team + character.box:
            previous = before["levels"].get(id(pokemon), pokemon.level)
            level_ups += max(0, pokemon.level - previous)
            previous_species = before["species"].get(id(pokemon), pokemon.species)
            if previous_species != pokemon.species:
                evolutions.append(f"{previous_species} -> {pokemon.species}")
        battle_report = activity_report.get("battles", {})
        battles = int(battle_report.get("wins", 0)) + int(battle_report.get("losses", 0))
        captures = len(activity_report.get("captures", []))
        capture_failures = len(activity_report.get("capture_failures", []))
        observations = sum(1 for note in notes if "observou" in note)
        training_report = activity_report.setdefault("training", {})
        training_report["level_ups"] = max(int(training_report.get("level_ups", 0)), level_ups)
        activity_report["money"] = money_delta
        activity_report["eggs_delta"] = egg_delta
        activity_report["badges_delta"] = badge_delta
        activity_report["travel"] = []
        if before["city"] != character.current_city:
            activity_report["travel"].append({
                "from": self.display_location_name(str(before["city"])),
                "to": self.display_location_name(character.current_city),
            })
        if evolutions:
            existing_evolutions = activity_report.setdefault("evolutions", [])
            for evolution in evolutions:
                if evolution not in existing_evolutions:
                    existing_evolutions.append(evolution)
        lines = [f"Resumo anual aos {character.age} anos"]
        before_city = self.display_location_name(str(before["city"]))
        current_city = self.display_location_name(character.current_city)
        lines.append(f"Local: {before_city}." if before_city == current_city else f"Local: {before_city} -> {current_city}.")
        if level_ups:
            lines.append(f"Treino: sua equipe ganhou {level_ups} nivel(is).")
        else:
            lines.append("Treino: nenhum nivel ganho.")
        pokemon_parts = []
        if new_pokemon > 0:
            captured_details = [
                f"{item.get('species')} Lv.{item.get('level')} -> {item.get('destination') or 'equipe/Box'}"
                for item in activity_report.get("captures", [])
                if item.get("species")
            ]
            hatched_details = [
                f"{item.get('species')} -> {item.get('destination')}"
                for item in activity_report.get("eggs", [])
                if item.get("action") == "hatched" and item.get("species")
            ]
            details = captured_details + hatched_details
            if details:
                pokemon_parts.append(f"{new_pokemon} novo(s) Pokemon: " + ", ".join(details))
            else:
                pokemon_parts.append(f"{new_pokemon} novo(s) Pokemon")
        if evolutions:
            pokemon_parts.append("evolucoes: " + ", ".join(evolutions))
        if not pokemon_parts:
            pokemon_parts.append("sem novas capturas ou evolucoes")
        lines.append("Pokemon: " + "; ".join(pokemon_parts) + ".")
        encounter_parts = []
        if captures:
            encounter_parts.append(f"{captures} captura(s)")
        if capture_failures:
            encounter_parts.append(f"{capture_failures} tentativa(s) frustrada(s)")
        if battles:
            wins = int(battle_report.get("wins", 0))
            losses = int(battle_report.get("losses", 0))
            encounter_parts.append(f"{battles} batalha(s): {wins} vitoria(s), {losses} derrota(s)")
        if observations:
            encounter_parts.append(f"{observations} observacao(oes)")
        lines.append("Encontros: " + (", ".join(encounter_parts) if encounter_parts else "nenhum encontro marcante") + ".")
        if money_delta:
            action = "ganhou" if money_delta > 0 else "gastou/perdeu"
            lines.append(f"Dinheiro: voce {action} {abs(money_delta)} Pokedollar.")
        else:
            lines.append("Dinheiro: sem mudanca.")
        career_missions = activity_report.get("career_missions", [])
        if career_missions:
            successes = sum(1 for mission in career_missions if mission.get("success"))
            mission_money = sum(int(mission.get("money", 0)) for mission in career_missions)
            lines.append(
                f"Profissao: {successes}/{len(career_missions)} missao(oes) concluida(s), "
                f"saldo {mission_money} Pokedollar."
            )
        item_report = activity_report.get("items", {})
        if item_report:
            item_parts = [f"{name} x{amount}" for name, amount in item_report.items() if amount > 0]
            if item_parts:
                lines.append("Itens: voce recebeu " + ", ".join(item_parts) + ".")
        rep_delta = int(activity_report.get("reputation_delta", 0))
        if rep_delta:
            action = "subiu" if rep_delta > 0 else "caiu"
            lines.append(f"Reputacao: {action} {abs(rep_delta)} ponto(s) neste periodo.")
        egg_report = activity_report.get("eggs", [])
        egg_created = [
            f"{item.get('species', 'Pokemon')} ({item.get('tier', '?')}) por {item.get('source', 'evento')}"
            for item in egg_report
            if item.get("action") == "created"
        ]
        egg_hatched = [
            f"{item.get('species', 'Pokemon')} -> {item.get('destination', 'equipe/Box')}"
            for item in egg_report
            if item.get("action") == "hatched"
        ]
        if egg_created or egg_hatched:
            parts = []
            if egg_created:
                parts.append("gerados/recebidos: " + ", ".join(egg_created[:4]))
            if egg_hatched:
                parts.append("chocados: " + ", ".join(egg_hatched[:4]))
            lines.append("Ovos: " + "; ".join(parts) + ".")
        elif egg_delta > 0:
            lines.append(f"Ovos: voce recebeu/encontrou {egg_delta} ovo(s).")
        elif egg_delta < 0:
            lines.append(f"Ovos: {abs(egg_delta)} ovo(s) chocaram ou sairam da incubacao.")
        else:
            lines.append("Ovos: sem mudanca.")
        if badge_delta:
            lines.append(f"Ginasios: voce conquistou {badge_delta} insignia(s).")
        else:
            gym_notice = self.gym_opportunity_notice(character)
            if gym_notice:
                lines.append(f"Ginasios: nenhuma insignia nova. {gym_notice}")
            else:
                lines.append("Ginasios: nenhuma insignia nova.")
        health_reasons = activity_report.get("health_reasons", [])
        activity_report["health_delta"] = health_delta
        if health_delta <= -10:
            reason_totals: dict[str, int] = {}
            for item in health_reasons:
                delta = int(item.get("delta", 0))
                reason = str(item.get("reason", ""))
                if delta < 0 and reason:
                    reason_totals[reason] = reason_totals.get(reason, 0) + abs(delta)
            reasons = [
                reason
                for reason, _ in sorted(reason_totals.items(), key=lambda item: item[1], reverse=True)
            ]
            reason_text = "; ".join(reasons[:3])
            if reason_text:
                lines.append(f"Saude: caiu {abs(health_delta)} ponto(s) por {reason_text}.")
            else:
                lines.append(f"Saude: caiu {abs(health_delta)} ponto(s).")
        elif health_delta >= 10:
            lines.append(f"Saude: recuperou {health_delta} ponto(s).")
        if notes:
            lines.append("Registro: " + " | ".join(_clean_sentence(note) for note in notes[:4]) + ".")
        else:
            lines.append("Registro: nada marcante mudou alem da passagem do tempo.")
        return "\n".join(lines)

    def gym_opportunity_notice(self, character: Character) -> str | None:
        gym = self.get_city_gym(character)
        if not gym or not character.team or gym["badge"] in character.badges:
            return None
        preview = self.gym_risk_preview(character)
        if not preview:
            return None
        if preview["risk"] in {"baixo", "moderado"}:
            return (
                f"O ginasio local parece uma oportunidade opcional: risco {preview['risk']}, "
                f"chance estimada {preview['estimated_win_chance']}%."
            )
        return None

    def professor_oak_event(self) -> LifeEvent:
        return LifeEvent(
            event_id="oak_starter",
            title="Professor Oak chama voce",
            text=(
                "O Professor Oak aparece na sua porta. Ele diz que Kanto e grande demais para ser "
                "entendida so pelos livros e oferece um primeiro companheiro Pokemon."
            ),
            min_age=10,
            max_age=10,
            phase="inicio da jornada",
            region="Kanto",
            city="Pallet Town",
            once=True,
            choices=[],
        )

    def character_has_pokemon(self, character: Character) -> bool:
        return bool(character.team or character.box)

    def oak_pokemon_options_for_career(self, career: str) -> list[str]:
        if career == "Treinador":
            return ["Bulbasaur", "Charmander", "Squirtle"]
        common_species = [
            species.name
            for species in self.pokemon.values()
            if species.can_be_wild
            and species.rarity == "common"
            and not species.is_legendary
            and not species.is_mythic
            and not species.is_starter
        ]
        if not common_species:
            common_species = ["Pidgey", "Rattata", "Caterpie"]
        count = 3 if career == "Criador" else 2
        rng = random.Random(f"{career}:{len(common_species)}:{self.data_dir}")
        return rng.sample(common_species, k=min(count, len(common_species)))

    def choose_starter(self, character: Character, starter_name: str | None, career: str | None = None) -> str:
        character.flags["oak_event_done"] = True
        allowed_careers = {"Treinador", "Criador", "Coordenador"}
        if starter_name is None:
            if career == "Estudante da academia":
                character.career = "Estudante da academia"
                history = "Aos 10 anos, voce decidiu continuar como estudante da academia."
                character.add_history(history, ["oak", "academy"])
                self._append_to_annual_report(character, history)
                return "Voce continuou como Estudante da academia. Escolha um foco de estudo para guiar seus proximos anos."
            history = "Aos 10 anos, voce recusou iniciar uma jornada Pokemon por enquanto."
            character.add_history(history, ["oak"])
            self._append_to_annual_report(character, history)
            return "Voce decidiu esperar antes de iniciar uma jornada Pokemon."
        if career not in allowed_careers:
            history = "Aos 10 anos, voce conversou com o Professor Oak, mas nao escolheu uma profissao Pokemon."
            character.add_history(history, ["oak"])
            self._append_to_annual_report(character, history)
            return "Professor Oak decidiu esperar ate voce escolher uma profissao ligada a Pokemon."
        species = self.pokemon[starter_name]
        pokemon = create_owned_pokemon(species, level=5, origin="presente do Professor Oak", species_by_name=self.pokemon)
        character.add_pokemon(pokemon)
        character.career = career
        history = f"Aos 10 anos, voce decidiu ser {career} e recebeu um {starter_name} do Professor Oak."
        character.add_history(history, ["oak", "starter"])
        self._append_to_annual_report(character, history)
        return f"{starter_name} entrou para sua equipe. Profissao escolhida: {career}."

    def receive_oak_supplies(self, character: Character) -> str:
        character.flags["oak_event_done"] = True
        character.inventory["Poke Ball"] = character.inventory.get("Poke Ball", 0) + 5
        character.inventory["Potion"] = character.inventory.get("Potion", 0) + 2
        history = "Aos 10 anos, o Professor Oak reconheceu seu companheiro Pokemon e entregou suprimentos."
        character.add_history(history, ["oak", "items"])
        self._append_to_annual_report(character, history)
        return "Professor Oak entregou 5 Poke Balls e 2 Potions para sua jornada."

    def set_career(self, character: Character, career: str) -> bool:
        if character.age < MIN_CHILD_ACTION_AGE:
            return False
        if career not in self.available_careers_for_character(character):
            return False
        if character.career != career:
            character.career = career
            character.add_history(f"Voce passou a seguir a profissao de {career}.", ["career"])
            if career != "Estudante da academia":
                character.flags.pop("academy_focus", None)
                character.flags.pop("academy_studied_type", None)
        return True

    def academy_focus_options(self) -> list[dict[str, str]]:
        return [
            {
                "id": focus.focus_id,
                "name": focus.name,
                "description": focus.description,
            }
            for focus in focus_choices()
        ]

    def set_academy_focus(self, character: Character, focus_id: str, studied_type: str | None = None) -> tuple[bool, str]:
        if character.career != "Estudante da academia" or character.age < 10:
            return False, "O foco academico fica disponivel para estudantes a partir dos 10 anos."
        if not set_focus(character, focus_id, studied_type):
            return False, "Foco academico invalido."
        message = f"Voce definiu seu foco academico: {focus_label(character)}."
        character.add_history(message, ["academy", "focus"])
        return True, message

    def academy_focus_info(self, character: Character) -> str:
        if character.career != "Estudante da academia":
            return "Sem foco academico ativo."
        return f"Foco academico: {focus_label(character)}."

    def available_careers_for_character(self, character: Character) -> list[str]:
        base = available_careers(character.age, bool(character.team))
        city = self.get_city_services(character.current_city)
        if not city:
            return base
        return [career for career in city.careers if career in base]

    def health_status(self, character: Character) -> str:
        if is_dead(character):
            return "falecido"
        if character.health <= 0:
            return "colapsado"
        if character.health < 25:
            return "critico"
        if character.health < 50:
            return "fragil"
        if character.health < 75:
            return "cansado"
        return "estavel"

    def _increment_career_year(self, character: Character) -> None:
        years = dict(character.flags.get("career_years", {}))
        career = character.career or ""
        years[career] = int(years.get(career, 0)) + 1
        character.flags["career_years"] = years

    def _apply_career_expenses_and_business(self, character: Character) -> list[str]:
        if not character.career:
            return []
        notes: list[str] = []
        rank = character.career_rank()
        expense_base = {
            "Treinador": 90,
            "Criador": 70,
            "Coordenador": 110,
            "Pesquisador": 160,
            "Explorador": 130,
            "Cientista": 220,
            "Coletor de Berrys": 45,
            "Construtor de Pokebolas": 150,
            "Cuidador de Fazenda": 60,
            "Construtor": 120,
            "Comerciante": 180,
        }.get(character.career, 40)
        expense = min(character.money, int(expense_base * (1 + rank * 0.18)))
        if expense:
            character.money -= expense
            notes.append(f"Gastos de carreira: {expense} Pokedollar em manutencao, ferramentas e rotina profissional.")
        businesses = dict(character.flags.get("businesses", {}))
        if character.career in businesses:
            income = int((700 + rank * 260 + character.reputation * 20) * (1 + character.attributes.MEN / 250))
            character.money += income
            notes.append(f"Seu negocio proprio de {character.career} rendeu {income} Pokedollar.")
        pension = int(character.flags.get("retirement_pension", 0))
        if pension:
            character.money += pension
            notes.append(f"Aposentadoria profissional pagou {pension} Pokedollar.")
        return notes

    def _apply_career_goal_milestones(self, character: Character) -> list[str]:
        if not character.career:
            return []
        notes: list[str] = []
        years = dict(character.flags.get("career_years", {}))
        career_years = int(years.get(character.career, 0))
        rank = character.career_rank()
        milestones = set(character.flags.get("career_milestones", []))
        key_prefix = f"{character.career}:"
        if rank >= 2 and f"{key_prefix}promoted" not in milestones:
            milestones.add(f"{key_prefix}promoted")
            character.reputation += 2
            notes.append(f"Promocao: voce se consolidou como profissional reconhecido em {character.career}.")
        if rank >= 4 and career_years >= 10 and f"{key_prefix}business_ready" not in milestones:
            milestones.add(f"{key_prefix}business_ready")
            character.flags["business_offer"] = character.career
            notes.append(f"Meta de carreira: voce ja tem reputacao para abrir um negocio proprio de {character.career}.")
        if character.age >= 60 and career_years >= 20 and f"{key_prefix}retirement_ready" not in milestones:
            milestones.add(f"{key_prefix}retirement_ready")
            character.flags["retirement_offer"] = character.career
            notes.append(f"Meta de carreira: voce ja pode se aposentar com legado em {character.career}.")
        character.flags["career_milestones"] = sorted(milestones)
        return notes

    def get_city_services(self, city_name: str) -> CityServices | None:
        location = self.get_location(city_name)
        if not location or location.kind != "city":
            return None
        return self.city_services.get(location.name)

    def _event_focus_for(self, character: Character) -> list[str]:
        city = self.get_city_services(character.current_city)
        if city and city.event_focus:
            return city.event_focus
        location = self.get_location(character.current_city)
        return [location.kind] if location else []

    def city_shop_items(self, character: Character) -> list[tuple[Item, int]]:
        city = self.get_city_services(character.current_city)
        if not city:
            return []
        items = []
        for item_name in city.shop_inventory:
            item = self.items.get(item_name)
            if item and item.price > 0:
                items.append((item, item.price))
        return items

    def buy_item(self, character: Character, item_name: str, quantity: int = 1) -> tuple[bool, str]:
        if character.age < MIN_CHILD_ACTION_AGE:
            return False, "Voce ainda e muito novo para comprar itens sozinho."
        city = self.get_city_services(character.current_city)
        if not city or item_name not in city.shop_inventory:
            return False, f"{item_name} nao esta disponivel em {character.current_city}."
        item = self.items.get(item_name)
        if not item or item.price <= 0:
            return False, f"{item_name} nao pode ser comprado aqui."
        total = item.price * max(1, quantity)
        if character.money < total:
            return False, f"Voce precisa de {total} Pokedollar para comprar {quantity}x {item_name}."
        character.money -= total
        if item_name == "Mapa de Kanto":
            character.flags["has_kanto_map"] = True
        if item.item_type == "egg":
            for _ in range(max(1, quantity)):
                egg = create_random_egg(
                    self.pokemon,
                    tier="C",
                    origin=f"comprado em {character.current_city}",
                )
                character.eggs.append(egg)
            character.add_history(f"Voce comprou {quantity}x {item_name} em {character.current_city}.", ["shop", "egg"])
            return True, f"Compra feita: {quantity}x {item_name} por {total} Pokedollar. O ovo foi guardado com cuidado."
        add_item(character.inventory, item_name, quantity)
        character.add_history(f"Voce comprou {quantity}x {item_name} em {character.current_city}.", ["shop"])
        return True, f"Compra feita: {quantity}x {item_name} por {total} Pokedollar."

    def use_item(self, character: Character, item_name: str) -> tuple[bool, str]:
        if character.age < MIN_CHILD_ACTION_AGE:
            return False, "Voce ainda e muito novo para usar itens sozinho."
        item = self.items.get(item_name)
        if not item:
            return False, f"{item_name} nao existe."
        if character.inventory.get(item_name, 0) <= 0:
            return False, f"Voce nao tem {item_name}."
        active = character.active_pokemon()

        if item.healing:
            if active is None:
                return False, "Voce precisa de um Pokemon ativo para usar este item."
            consume_item(character.inventory, item_name)
            species = self.pokemon.get(active.species)
            active.heal(item.healing, species)
            if active.health_percent(species) >= 0.75 and active.status in {"tired", "injured", "badly_injured"}:
                active.status = "healthy"
            return True, f"{active.display_name()} recuperou {item.healing} de saude."

        effect = item.effect
        if effect in {"level_up_active", "boost_combat", "boost_occult", "boost_beauty_happiness"} and active is None:
            return False, "Voce precisa de um Pokemon ativo para usar este item."

        consume_item(character.inventory, item_name)
        if effect == "cure_sick":
            if active is None:
                return False, "Voce precisa de um Pokemon ativo para usar este item."
            active.status = "healthy"
            return True, f"{active.display_name()} foi curado."
        if effect == "reduce_wild_events":
            character.flags["repel_years"] = int(character.flags.get("repel_years", 0)) + 1
            return True, "Repel ativo: encontros selvagens ficarao menos provaveis neste ano."
        if effect == "level_up_active":
            active.level = min(100, active.level + 1)
            active.heal_full(self.pokemon.get(active.species))
            return True, f"{active.display_name()} subiu para o nivel {active.level}."
        if effect == "boost_combat":
            active.combat = min(100, active.combat + 3)
            return True, f"{active.display_name()} ficou mais forte. COMBAT +3."
        if effect == "boost_occult":
            active.occult = min(100, active.occult + 3)
            return True, f"{active.display_name()} refinou energia especial. OCCULT +3."
        if effect == "boost_beauty_happiness":
            active.beauty = min(100, active.beauty + 2)
            active.happiness = min(100, active.happiness + 5)
            return True, f"{active.display_name()} ficou mais confiante. BEAUTY +2, felicidade +5."
        if effect == "boost_luck":
            character.modify_attributes({"LUK": 2})
            return True, "Voce se sente mais confiante. LUK +2."
        if effect == "boost_phy":
            character.modify_attributes({"PHY": 2})
            return True, "O equipamento ajudou sua resistencia. PHY +2."
        if effect == "boost_men":
            character.modify_attributes({"MEN": 2})
            return True, "Voce organizou melhor seus estudos. MEN +2."
        if effect == "boost_pok":
            character.modify_attributes({"POK": 2})
            return True, "Voce aprendeu detalhes uteis sobre Pokemon. POK +2."
        if effect == "boost_work_phy":
            character.modify_attributes({"PHY": 1})
            character.flags["work_safety_years"] = int(character.flags.get("work_safety_years", 0)) + 1
            return True, "Luvas de trabalho equipadas: pequenos riscos de trabalho ficam menores neste ano. PHY +1."
        if effect == "career_focus":
            character.flags["career_focus_years"] = int(character.flags.get("career_focus_years", 0)) + 1
            return True, "Ferramentas preparadas: sua proxima rotina profissional tera mais foco."
        if effect == "business_focus":
            character.modify_attributes({"MEN": 1, "LUK": 1})
            character.flags["business_focus_years"] = int(character.flags.get("business_focus_years", 0)) + 1
            return True, "Voce revisou contas e contatos. MEN +1, LUK +1."
        if effect == "research_focus":
            character.modify_attributes({"MEN": 1, "POK": 1})
            return True, "Acesso tecnico ampliou sua pesquisa. MEN +1, POK +1."
        if effect == "minor_rest":
            character.health = min(100, character.health + 12)
            return True, "A viagem curta ajudou voce a descansar. Saude +12."
        if effect == "unlock_black_market":
            character.flags["black_market_contact"] = True
            return True, "Contato desbloqueado: mercados clandestinos podem aparecer em cidades maiores."
        if effect == "safe_return":
            if character.age >= 10:
                character.current_city = character.hometown
                return True, f"Voce voltou em seguranca para {character.hometown}."
            return True, "Voce guardou o item; ainda e cedo para viajar sozinho."
        if effect == "reveal_map":
            character.flags["has_kanto_map"] = True
            return True, "Mapa de Kanto ativado! Agora voce ve descricoes e servicos de cada cidade ao viajar."
        if effect == "create_common_egg":
            egg = create_random_egg(
                self.pokemon,
                tier="C",
                origin=f"ovo comprado em {character.current_city}",
            )
            character.eggs.append(egg)
            return True, f"O ovo foi incubado com cuidado. Um ovo {egg.color} ({egg.rarity_label}) foi adicionado."
        return False, f"{item_name} nao tem uso implementado."

    def heal_team_in_city(self, character: Character) -> str:
        if character.age < MIN_CHILD_ACTION_AGE:
            return "Voce ainda depende de adultos para usar servicos da cidade."
        city = self.get_city_services(character.current_city)
        if not city or not city.has_service("pokemon_center"):
            return "Esta cidade nao tem Pokemon Center disponivel."
        for pokemon in character.team:
            pokemon.heal_full(self.pokemon.get(pokemon.species))
            pokemon.status = "healthy"
        character.add_history(f"Sua equipe descansou no Pokemon Center de {character.current_city}.", ["city", "heal"])
        return "Sua equipe foi curada."

    # ── Hospital ────────────────────────────────────────────────────────────────

    _HOSPITAL_OPTIONS: dict[str, dict] = {
        "leve": {
            "label": "Tratamento leve (3 meses)",
            "months": 3,
            "cost": 150,
            "heal": 20,
            "min_health": 0,
            "description": "Consultas e repouso. Recupera saúde moderadamente.",
        },
        "completo": {
            "label": "Tratamento completo (6 meses)",
            "months": 6,
            "cost": 350,
            "heal": 40,
            "min_health": 0,
            "description": "Internação parcial. Cura status negativos e recupera bem.",
        },
        "internacao": {
            "label": "Internação prolongada (12 meses)",
            "months": 12,
            "cost": 700,
            "heal": 75,
            "min_health": 70,
            "description": "Tratamento completo. Garante saúde mínima de 70 ao sair.",
        },
    }

    def hospital_options(self, character: Character) -> list[dict]:
        """Retorna opções de hospital disponíveis com custo e efeito."""
        opts = []
        for key, opt in self._HOSPITAL_OPTIONS.items():
            can_afford = character.money >= opt["cost"]
            opts.append({
                "key": key,
                "label": opt["label"],
                "cost": opt["cost"],
                "months": opt["months"],
                "heal": opt["heal"],
                "can_afford": can_afford,
                "description": opt["description"],
            })
        return opts

    def go_to_hospital(self, character: Character, option_key: str) -> tuple[bool, str]:
        """Internar o personagem no hospital. Cura saúde e trata status negativos."""
        if is_dead(character):
            return False, "Game over: personagem falecido."
        if character.flags.get("in_prison"):
            return False, "Voce nao pode escolher hospital enquanto esta preso."
        opt = self._HOSPITAL_OPTIONS.get(option_key)
        if not opt:
            return False, "Opção de internação inválida."
        cost = opt["cost"]
        if character.money < cost:
            return False, f"{opt['label']} custa {cost}P. Você tem {character.money}P."

        character.money -= cost
        old_health = character.health
        healed = opt["heal"]

        months = opt["months"]
        character.flags["current_period_months"] = months
        age_progress = int(character.flags.get("age_month_progress", 0)) + months
        aged_years = 0
        while age_progress >= 12:
            age_progress -= 12
            character.age += 1
            aged_years += 1
            if character.age in {5, 10, 15, 18, 20, 25, 30, 40, 50, 60, 70}:
                character.add_history(f"Voce completou {character.age} anos durante recuperacao hospitalar.", ["age", "milestone"])
        character.flags["age_month_progress"] = age_progress

        character.health = min(100, character.health + healed)
        if opt["min_health"] > 0:
            character.health = max(opt["min_health"], character.health)

        if months >= 6:
            for pokemon in character.team + list(character.box):
                if pokemon.status in ("injured", "sick", "tired"):
                    pokemon.status = "healthy"
        if months >= 12:
            for pokemon in character.team + list(character.box):
                if pokemon.status == "badly_injured":
                    pokemon.status = "healthy"

        egg_notes = self._progress_eggs_by_months(character, months)
        self._reset_period_action_flags(character)

        health_change = character.health - old_health
        health_indicator = "↑↑↑" if health_change >= 60 else "↑↑" if health_change >= 30 else "↑"
        msg_parts = [
            f"HOSPITAL|{opt['label']}|{months}|{cost}|{old_health}|{character.health}",
            f"Você passou {months} meses se recuperando.",
            f"Saúde: {old_health} → {character.health} {health_indicator}",
        ]
        if aged_years:
            msg_parts.append(f"O tempo passou: agora voce tem {character.age} anos.")
        if months >= 6:
            msg_parts.append("Status dos Pokémon tratados.")
        if months >= 12:
            msg_parts.append("Recuperação total garantida.")
        msg_parts.extend(egg_notes)

        msg = "\n".join(msg_parts)
        character.add_history(
            f"Internação hospitalar de {months} meses. Saúde: {old_health}→{character.health}.",
            ["health", "hospital"],
        )
        character.flags["last_year_report"] = (
            f"Resumo de {months} meses aos {character.age} anos\n"
            f"SAUDE tratamento hospitalar: {old_health} -> {character.health}.\n"
            f"DINHEIRO voce gastou {cost} Pokedollar.\n"
            + ("\n".join(egg_notes) if egg_notes else "REGISTRO periodo dedicado a recuperacao.")
        )
        return True, msg

    def current_city_economy_tier(self, character: Character) -> int:
        return city_economy_tier(self.display_location_name(character.current_city))

    def lifestyle_offers(self, character: Character, category: str | None = None) -> list:
        return offers_for_tier(self.current_city_economy_tier(character), category)

    def buy_lifestyle_asset(self, character: Character, offer_id: str) -> tuple[bool, str]:
        if character.age < MIN_JOURNEY_ACTION_AGE:
            return False, "Compras grandes so ficam disponiveis a partir dos 10 anos."
        offer = next((item for item in LIFESTYLE_OFFERS if item.offer_id == offer_id), None)
        if not offer:
            return False, "Oferta nao encontrada."
        tier = self.current_city_economy_tier(character)
        if offer.tier > tier:
            return False, f"Esta cidade nao suporta esse nivel de compra. Economia local: nivel {tier}."
        if character.money < offer.price:
            return False, f"Voce precisa de {offer.price} Pokedollar."
        character.money -= offer.price
        character.assets[offer.offer_id] = character.assets.get(offer.offer_id, 0) + 1
        character.health = min(100, character.health + offer.health_bonus)
        character.reputation += offer.reputation_bonus
        character.add_history(f"Voce comprou {offer.name}.", ["asset", offer.category])
        return True, f"Compra feita: {offer.name} por {offer.price} Pokedollar."

    def available_courses(self, character: Character) -> list:
        return courses_for_tier(self.current_city_economy_tier(character))

    def take_course(self, character: Character, course_id: str) -> tuple[bool, str]:
        if character.age < MIN_JOURNEY_ACTION_AGE:
            return False, "Cursos pagos so ficam disponiveis a partir dos 10 anos."
        course = next((item for item in COURSES if item.course_id == course_id), None)
        if not course:
            return False, "Curso nao encontrado."
        if course.min_city_tier > self.current_city_economy_tier(character):
            return False, "Esta cidade nao oferece esse curso."
        if character.money < course.price:
            return False, f"Voce precisa de {course.price} Pokedollar."
        character.money -= course.price
        deltas = course_effect_percent(character.attributes, course.attr_deltas)
        character.modify_attributes(deltas)
        character.add_history(f"Voce concluiu o curso: {course.name}.", ["course"])
        detail = ", ".join(f"{key} +{value}" for key, value in deltas.items())
        return True, f"Curso concluido: {course.name}. {detail}."

    def available_trips(self, character: Character) -> list:
        return trips_for_tier(self.current_city_economy_tier(character))

    def take_trip(self, character: Character, trip_id: str) -> tuple[bool, str]:
        if character.age < MIN_JOURNEY_ACTION_AGE:
            return False, "Viagens so ficam disponiveis a partir dos 10 anos."
        trip = next((item for item in TRIPS if item.trip_id == trip_id), None)
        if not trip:
            return False, "Viagem nao encontrada."
        if trip.min_city_tier > self.current_city_economy_tier(character):
            return False, "Esta cidade nao tem acesso pratico a essa viagem."
        if character.money < trip.price:
            return False, f"Voce precisa de {trip.price} Pokedollar."
        character.money -= trip.price
        character.health = min(100, character.health + trip.health_gain)
        character.modify_attributes(trip.attr_deltas)
        character.add_history(f"Voce fez uma viagem de descanso: {trip.name}.", ["trip", "health"])
        return True, f"{trip.name}: saude +{trip.health_gain}."

    def sell_item(self, character: Character, item_name: str, quantity: int = 1) -> tuple[bool, str]:
        if character.age < MIN_CHILD_ACTION_AGE:
            return False, "Voce ainda e muito novo para vender itens sozinho."
        amount = max(1, quantity)
        if character.inventory.get(item_name, 0) < amount:
            return False, f"Voce nao tem {amount}x {item_name}."
        item = self.items.get(item_name)
        if not item or item.price <= 0:
            return False, f"{item_name} nao tem mercado comum."
        character.inventory[item_name] -= amount
        if character.inventory[item_name] <= 0:
            del character.inventory[item_name]
        gain = item_sell_price(item.price) * amount
        character.money += gain
        return True, f"Venda feita: {amount}x {item_name} por {gain} Pokedollar."

    def sell_egg(self, character: Character, egg_index: int) -> tuple[bool, str]:
        if character.age < MIN_JOURNEY_ACTION_AGE:
            return False, "Venda de ovos so fica disponivel a partir dos 10 anos."
        if egg_index < 0 or egg_index >= len(character.eggs):
            return False, "Ovo invalido."
        egg = character.eggs.pop(egg_index)
        tier = getattr(egg, "rarity_tier", getattr(egg, "tier", "C"))
        gain = egg_sell_price(tier)
        character.money += gain
        character.add_history(f"Voce vendeu um ovo {egg.color} no mercado.", ["market", "egg"])
        return True, f"Ovo vendido por {gain} Pokedollar."

    def sell_pokemon(self, character: Character, source: str, index: int) -> tuple[bool, str]:
        if character.age < MIN_JOURNEY_ACTION_AGE:
            return False, "Venda de Pokemon so fica disponivel a partir dos 10 anos."
        collection = character.team if source == "team" else character.box
        if index < 0 or index >= len(collection):
            return False, "Pokemon invalido."
        if source == "team" and len(character.team) <= 1:
            return False, "Voce precisa manter pelo menos um Pokemon na equipe."
        pokemon = collection.pop(index)
        value = int(pokemon_market_value(pokemon, self.pokemon.get(pokemon.species)) * 0.55)
        character.money += value
        apply_negative_reputation(character, 2, "venda de Pokemon no mercado negro")
        character.add_history(f"Voce vendeu {pokemon.display_name()} no mercado negro.", ["black_market", "pokemon"])
        character._sync_active_flags()
        return True, f"{pokemon.display_name()} foi vendido no mercado negro por {value} Pokedollar. Reputacao -2."

    def black_market_available(self, character: Character) -> bool:
        """Mercado negro acessível via contato, cidade grande ou reputação criminal."""
        if character.age < MIN_JOURNEY_ACTION_AGE:
            return False
        has_contact = bool(character.flags.get("black_market_contact"))
        high_tier_city = self.current_city_economy_tier(character) >= 5
        # Personagens notoriamente criminosos ganham acesso underground
        criminal_rep = character.reputation <= -25
        return has_contact or high_tier_city or criminal_rep

    def black_market_access_level(self, character: Character) -> int:
        """0=sem acesso, 1=basico, 2=intermediario, 3=avancado."""
        if not self.black_market_available(character):
            return 0
        has_contact = bool(character.flags.get("black_market_contact"))
        tier = self.current_city_economy_tier(character)
        rep = character.reputation
        if (has_contact and tier >= 6) or rep <= -70:
            return 3
        if has_contact or rep <= -45 or tier >= 6:
            return 2
        return 1

    def black_market_pokemon_offers(self, character: Character) -> list[tuple[PokemonSpecies, int]]:
        access = self.black_market_access_level(character)
        if access == 0:
            return []
        allowed: set[str] = {"common", "uncommon"}
        if access >= 2:
            allowed.add("rare")
        if access >= 3:
            allowed.add("very_rare")
        candidates = [
            species for species in self.pokemon.values()
            if not species.is_legendary and not species.is_mythic and species.rarity in allowed
        ]
        rng = random.Random(f"{character.name}:{character.age}:{character.current_city}:black_market")
        chosen = rng.sample(candidates, k=min(5 + access, len(candidates)))
        # Criminosos de carreira pagam menos (descontos pelo relacionamento)
        discount = 1.0 if character.career != "Criminoso" else max(0.65, 1.0 - character.career_rank() * 0.06)
        return [(species, int(BLACK_MARKET_RARITY_MULT.get(species.rarity, 6000) * 2.2 * discount)) for species in chosen]

    def buy_black_market_pokemon(self, character: Character, species_name: str) -> tuple[bool, str]:
        offers = dict((species.name, price) for species, price in self.black_market_pokemon_offers(character))
        if species_name not in offers:
            return False, f"{species_name} nao esta disponivel no mercado negro agora."
        price = offers[species_name]
        if character.money < price:
            return False, f"Voce precisa de {price} Pokedollar."
        character.money -= price
        species = self.pokemon[species_name]
        pokemon = create_owned_pokemon(species, level=max(5, min(35, character.age // 2)), origin="mercado negro", species_by_name=self.pokemon)
        destination = character.add_pokemon(pokemon)
        character.register_caught(species.name)
        # Criminosos de carreira sofrem menos penalidade reputacional (já é rotina)
        rep_penalty = 1 if character.career == "Criminoso" else 3
        apply_negative_reputation(character, rep_penalty, "compra no mercado negro")
        location_str = "equipe" if destination == "team" else "Box"
        return True, f"{species.name} comprado por {price}P e enviado para {location_str}. Rep {-rep_penalty}."

    def criminal_underworld_status(self, character: Character) -> str:
        """Retorna o status do personagem no submundo criminal."""
        access = self.black_market_access_level(character)
        rep = character.reputation
        career = character.career
        stolen = int(character.flags.get("stolen_pokemon_count", 0))
        suspicion = int(character.flags.get("suspicion", 0))
        in_prison = bool(character.flags.get("prison_months_remaining", 0))

        access_labels = {0: "Sem acesso", 1: "Basico", 2: "Intermediario", 3: "Avancado"}
        if rep <= -70:
            underworld_title = "Figura lendaria do submundo"
        elif rep <= -50:
            underworld_title = "Criminoso veterano"
        elif rep <= -35:
            underworld_title = "Notorio infrator"
        elif rep <= -25:
            underworld_title = "Contato do submundo"
        else:
            underworld_title = "Sem ficha criminal relevante"

        rank_label = ""
        if career == "Criminoso":
            rank_label = f" | Rank criminal: {character.career_rank()}"

        lines = [
            f"Titulo: {underworld_title}{rank_label}",
            f"Reputacao: {rep} | Suspeita acumulada: {suspicion}",
            f"Acesso ao mercado negro: {access_labels.get(access, '?')}",
            f"Pokemon roubados: {stolen}",
        ]
        if in_prison:
            months_left = int(character.flags.get("prison_months_remaining", 0))
            lines.append(f"STATUS: Preso — {months_left} mes(es) restantes.")
        return "\n".join(lines)

    def steal_pokemon(self, character: Character, target_species: str | None = None) -> tuple[bool, str]:
        if is_dead(character):
            return False, "Game over: personagem falecido."
        if character.age < 10:
            return False, "Voce ainda e jovem demais para tentar algo assim."
        candidates = [
            species for species in self.pokemon.values()
            if species.can_be_wild and not species.is_legendary and not species.is_mythic and species.rarity in {"common", "uncommon", "rare"}
        ]
        species = self.pokemon.get(target_species) if target_species else random.choice(candidates)
        if not species:
            return False, "Pokemon alvo invalido."
        if not self._period_action_available(character, "theft"):
            return False, "Voce ja tentou um roubo neste periodo. Avance o tempo para tentar novamente."
        self._mark_period_action_used(character, "theft")
        chance = 0.10 + character.attributes.LUK * 0.002 + character.attributes.PHY * 0.001 + character.attributes.MEN * 0.001
        if character.career == "Criminoso":
            chance += 0.18 + character.career_rank("Criminoso") * 0.03
        if species.rarity == "rare":
            chance -= 0.08
        chance = max(0.03, min(0.55, chance))
        if random.random() <= chance:
            pokemon = create_owned_pokemon(species, level=random.randint(5, max(8, min(35, character.age + 8))), origin="roubado", species_by_name=self.pokemon)
            destination = character.add_pokemon(pokemon)
            character.register_caught(species.name)
            apply_negative_reputation(character, 10 if character.career == "Criminoso" else 18, "roubo de Pokemon")
            character.flags["stolen_pokemon_count"] = int(character.flags.get("stolen_pokemon_count", 0)) + 1
            caught_later_chance = 0.08 + max(0, int(character.flags.get("suspicion", 0))) * 0.004
            if random.random() < min(0.45, caught_later_chance):
                sentence = imprison(character, "pokemon_theft")
                return True, f"Voce roubou {species.name}, mas foi detido depois. Pena: {sentence.months} meses."
            location = "equipe" if destination == "team" else "Box"
            return True, f"Voce roubou {species.name} e enviou para {location}. Chance era {chance * 100:.1f}%. Reputacao caiu."
        fine = min(character.money, 300 + character.age * 20)
        character.money -= fine
        character.health = max(0, character.health - random.randint(2, 8))
        apply_negative_reputation(character, 14 if character.career == "Criminoso" else 24, "tentativa de roubo frustrada")
        if int(character.flags.get("suspicion", 0)) >= 25:
            character.flags["official_event_ban"] = True
        arrest_chance = 0.18 + max(0, int(character.flags.get("suspicion", 0))) * 0.006
        if random.random() < min(0.65, arrest_chance):
            sentence = imprison(character, "attempted_pokemon_theft")
            return False, f"A tentativa falhou e voce foi detido por tentativa de roubo. Pena: {sentence.months} meses."
        return False, f"A tentativa falhou. Voce pagou {fine}P em custos/multas. Chance era {chance * 100:.1f}%."

    def career_goal_status(self, character: Character) -> str:
        if not character.career:
            return "Sem carreira definida."
        years = dict(character.flags.get("career_years", {}))
        career_years = int(years.get(character.career, 0))
        rank = character.career_rank()
        business = "sim" if character.career in dict(character.flags.get("businesses", {})) else "nao"
        retirement = "sim" if character.flags.get("retirement_pension") else "nao"
        return (
            f"{character.career}: rank {rank}, {career_years} ano(s) de carreira, "
            f"negocio proprio: {business}, aposentadoria: {retirement}."
        )

    def start_business(self, character: Character) -> tuple[bool, str]:
        if not character.career:
            return False, "Voce precisa de uma carreira para abrir um negocio."
        if character.career_rank() < 4:
            return False, "Voce precisa de rank Expert ou maior."
        businesses = dict(character.flags.get("businesses", {}))
        if character.career in businesses:
            return False, "Voce ja tem um negocio nessa carreira."
        cost = 30000 + character.career_rank() * 6000
        if character.money < cost:
            return False, f"Voce precisa de {cost} Pokedollar para abrir o negocio."
        character.money -= cost
        businesses[character.career] = {"age_started": character.age}
        character.flags["businesses"] = businesses
        character.reputation += 5
        character.add_history(f"Voce abriu um negocio proprio de {character.career}.", ["career", "business"])
        return True, f"Negocio proprio aberto por {cost} Pokedollar."

    def retire_from_career(self, character: Character) -> tuple[bool, str]:
        if not character.career:
            return False, "Voce nao tem carreira para se aposentar."
        years = dict(character.flags.get("career_years", {}))
        career_years = int(years.get(character.career, 0))
        if character.age < 60 or career_years < 20:
            return False, "Aposentadoria exige 60+ anos e 20 anos na carreira."
        pension = 250 + character.career_rank() * 120 + min(500, career_years * 12)
        old_career = character.career
        character.flags["retirement_pension"] = pension
        character.flags["retired_from"] = old_career
        character.career = None
        character.add_history(f"Voce se aposentou de {old_career} com pensao anual.", ["career", "retirement"])
        return True, f"Aposentadoria concedida: {pension} Pokedollar por ano."

    def manual_action_read_about_pokemon(self, character: Character) -> str:
        if character.age < MIN_CHILD_ACTION_AGE:
            return "Voce ainda e muito novo para frequentar a academia."
        if not self._period_action_available(character, "study"):
            return "Voce ja estudou neste periodo. Avance o tempo para estudar novamente."
        self._mark_period_action_used(character, "study")
        character.modify_attributes({"POK": 2, "MEN": 1})
        character.add_history(f"Voce estudou sobre Pokemon em {character.current_city}.", ["manual", "study"])
        return "Voce leu sobre Pokemon. POK +2, MEN +1."

    def manual_action_work_city(self, character: Character) -> str:
        if character.age < MIN_CHILD_ACTION_AGE:
            return "Voce ainda e muito novo para trabalhar na cidade."
        city = self.get_city_services(character.current_city)
        if not city:
            return "Nao ha trabalho urbano disponivel aqui."
        if not self._period_action_available(character, "work"):
            return "Voce ja trabalhou neste periodo. Avance o tempo para trabalhar novamente."
        self._mark_period_action_used(character, "work")
        work = city.work or {
            "name": "bicos na cidade",
            "base_income": 75,
            "primary_attributes": ["MEN", "LUK"],
            "health_risk": 0.08,
        }
        income = self._city_work_income(character, city, work)
        character.money += income
        risk = float(work.get("health_risk", 0.08))
        if random.random() < risk:
            health_loss = random.randint(2, 6)
            character.health = max(0, character.health - health_loss)
            suffix = f" Foi cansativo e sua saude caiu {health_loss}."
        else:
            suffix = ""
        job_name = str(work.get("name", "bicos na cidade"))
        city_name = self.display_location_name(character.current_city)
        character.add_history(f"Voce trabalhou como {job_name} em {city_name} e ganhou {income} Pokedollar.", ["manual", "work"])
        return f"Voce trabalhou como {job_name} e ganhou {income} Pokedollar.{suffix}"

    def _city_work_income(self, character: Character, city: CityServices, work: dict) -> int:
        base_income = int(work.get("base_income", 75))
        economy_tier = self.current_city_economy_tier(character)
        economy_factor = 0.72 + economy_tier * 0.11
        attribute_keys = [key for key in work.get("primary_attributes", []) if key in {"PHY", "MEN", "POK", "LUK"}]
        if attribute_keys:
            attribute_score = sum(character.attributes.get(key) for key in attribute_keys) / len(attribute_keys)
        else:
            attribute_score = character.attributes.MEN
        attribute_factor = 0.75 + attribute_score / 200
        career_factor = 1.08 if character.career and character.career in city.careers else 1.0
        return calculate_money_gain(
            base_income,
            character.attributes,
            specialty_factor=economy_factor * attribute_factor * career_factor,
        )

    def manual_action_train_team(self, character: Character) -> str:
        if character.age < MIN_CHILD_ACTION_AGE:
            return "Voce ainda e muito novo para treinar Pokemon sozinho."
        eligible = [p for p in character.team if p.status != "badly_injured"]
        if not eligible:
            return "Voce precisa de pelo menos um Pokemon saudavel para treinar."
        if not self._period_action_available(character, "training"):
            return "Voce ja treinou neste periodo. Avance o tempo para treinar novamente."
        self._mark_period_action_used(character, "training")
        xp = 38 + character.attributes.POK // 4 + character.attributes.PHY // 8
        all_notes = []
        for pokemon in eligible:
            notes = grant_pokemon_xp(pokemon, xp, self.pokemon)
            pokemon.current_health = max(0, pokemon.current_health - random.randint(1, 4))
            if pokemon.health_percent(self.pokemon.get(pokemon.species)) <= 0.25:
                pokemon.status = "tired"
            all_notes.extend(notes)
        character.modify_attributes({"PHY": 1, "POK": 1})
        names = ", ".join(p.display_name() for p in eligible)
        character.add_history(f"Voce treinou com {names} em {character.current_city}.", ["manual", "train"])
        extra = f" {' '.join(all_notes)}" if all_notes else ""
        return f"Treino concluido: {len(eligible)} Pokemon (+{xp} XP cada). PHY +1, POK +1.{extra}"

    def manual_action_intensive_training(self, character: Character) -> str:
        if character.age < MIN_JOURNEY_ACTION_AGE:
            return "Treino intensivo so fica disponivel a partir dos 10 anos."
        active = character.active_pokemon()
        if active is None:
            return "Voce precisa de um Pokemon para treino intensivo."
        if not self._period_action_available(character, "training"):
            return "Voce ja treinou neste periodo. Avance o tempo para treinar novamente."
        self._mark_period_action_used(character, "training")
        xp = 80 + character.attributes.POK // 3 + character.attributes.PHY // 5
        if character.career == "Treinador":
            xp += 35
        notes = grant_pokemon_xp(active, xp, self.pokemon)
        health_cost = random.randint(8, 18)
        active.current_health = max(0, active.current_health - health_cost)
        if active.health_percent(self.pokemon.get(active.species)) <= 0.35:
            active.status = "injured"
        character.health = max(0, character.health - 2)
        character.modify_attributes({"PHY": 1, "POK": 2})
        character.add_history(f"Voce fez treino intensivo com {active.display_name()} em {character.current_city}.", ["manual", "intensive_train"])
        extra = f" {' '.join(notes)}" if notes else ""
        return f"Treino intensivo: {active.display_name()} ganhou {xp} XP, mas perdeu {health_cost} HP.{extra}"

    def _period_action_key(self, action: str) -> str:
        return f"period_action_{action}_used"

    def _period_action_available(self, character: Character, action: str) -> bool:
        return not bool(character.flags.get(self._period_action_key(action)))

    def _mark_period_action_used(self, character: Character, action: str) -> None:
        character.flags[self._period_action_key(action)] = True

    def _reset_period_action_flags(self, character: Character) -> None:
        for key in list(character.flags):
            if key.startswith("period_action_"):
                character.flags.pop(key, None)
        character.flags.pop("manual_training_used_this_period", None)

    def manual_action_search_for_egg(self, character: Character) -> str:
        if character.age < MIN_JOURNEY_ACTION_AGE:
            return "Procurar ovos em habitats naturais so fica disponivel a partir dos 10 anos."
        location = self.get_location(character.current_city)
        if not location or not location.encounter_enabled:
            return "Este local nao parece ter habitats adequados para procurar ovos."
        if not self._period_action_available(character, "egg_search"):
            return "Voce ja procurou ovos neste periodo. Avance o tempo para procurar novamente."
        self._mark_period_action_used(character, "egg_search")
        chance = 0.035 + character.attributes.POK * 0.0009 + character.attributes.LUK * 0.0005
        if character.career == "Criador":
            chance += 0.045
        if random.random() <= min(0.24, chance):
            egg = create_random_egg(
                self.pokemon,
                tier=choose_egg_tier({"C": 65, "I": 25, "R": 8, "RR": 2}),
                origin=f"busca manual em {character.current_city}",
            )
            character.eggs.append(egg)
            character.add_history(f"Voce encontrou um ovo {egg.color} em {character.current_city}.", ["manual", "egg"])
            return f"Voce encontrou um ovo {egg.color} ({egg.rarity_label})."
        character.modify_attributes({"POK": 1})
        return "Voce nao encontrou ovos, mas aprendeu mais sobre o habitat local. POK +1."


    def manual_action_hunt_wild_pokemon(self, character: Character) -> tuple[bool, str]:
        """Tenta encontrar e capturar/derrotar um Pokemon selvagem manualmente."""
        if character.age < MIN_JOURNEY_ACTION_AGE:
            return False, "Cacadas so ficam disponiveis a partir dos 10 anos."

        species, level, encounter_text = self.wild_encounter(character)
        if not character.team:
            health_loss = random.randint(3, 9)
            character.health = max(1, character.health - health_loss)
            character.register_seen(species.name)
            msg = (
                encounter_text
                + f"\nSem Pokemon na equipe, voce fugiu e foi atingido de raspao. Saude -{health_loss}."
            )
            character.add_history(msg, ["pokemon", "risk", "manual"])
            return False, msg

        pok = character.attributes.POK
        phy = character.attributes.PHY
        luk = character.attributes.LUK

        # Chance de captura: POK + LUK + bonus Pokebola
        has_pokeball = character.inventory.get("Poke Ball", 0) > 0
        catch_chance = min(0.78, pok * 0.004 + luk * 0.002 + (0.22 if has_pokeball else 0.0))

        # Chance de derrotar sem capturar: PHY + poder da equipe
        team_power = sum(p.combat for p in character.team) if character.team else 0
        battle_chance = min(0.85, phy * 0.004 + min(team_power * 0.008, 0.25))

        roll = random.random()

        if roll < catch_chance:
            if has_pokeball:
                character.inventory["Poke Ball"] = max(0, character.inventory["Poke Ball"] - 1)
                if character.inventory["Poke Ball"] == 0:
                    del character.inventory["Poke Ball"]
            new_poke = create_owned_pokemon(species, level=level, origin="cacada manual", species_by_name=self.pokemon)
            destination = character.add_pokemon(new_poke)
            slot = "equipe" if destination == "team" else "Box"
            character.register_caught(species.name)
            ball_txt = " com Pokebola" if has_pokeball else ""
            msg = encounter_text + "\nVoce capturou " + species.name + " Lv." + str(level) + ball_txt + "! (" + slot + ")"
            character.add_history(msg, ["pokemon", "capture", "manual"])
            return True, msg

        elif roll < catch_chance + battle_chance:
            money = random.randint(15, 70)
            character.money += money
            character.modify_attributes({"PHY": random.randint(0, 1)})
            from .progression import grant_pokemon_xp
            for poke in character.team:
                list(grant_pokemon_xp(poke, 14, self.pokemon))
            msg = encounter_text + "\nVoce derrotou o " + species.name + " selvagem! +" + str(money) + "P, XP para a equipe."
            character.add_history(msg, ["pokemon", "battle", "manual"])
            return True, msg

        else:
            escapes = [
                encounter_text + "\nO " + species.name + " escapou antes que voce agisse.",
                encounter_text + "\nA tentativa falhou. O " + species.name + " desapareceu na mata.",
                encounter_text + "\nO " + species.name + " era rapido demais desta vez.",
            ]
            return False, random.choice(escapes)

    # ── Procurar Batalha com Treinador ─────────────────────────────────────────

    _TRAINER_PREFIXES = [
        "Treinador", "Rival", "Aspirante", "Novato", "Veterano", "Caminhante",
        "Aventureiro", "Explorador", "Caçador", "Buscador",
    ]
    _TRAINER_AREAS = [
        "da Rota", "do Parque", "do Porto", "da Floresta", "da Montanha",
        "da Cidade", "do Vale", "das Cavernas", "da Costa", "da Planície",
    ]

    def manual_action_search_trainer_battle(self, character: Character) -> tuple[bool, str]:
        """Encontra um treinador aleatorio para uma serie curta de 1 a 3 batalhas."""
        if character.age < MIN_JOURNEY_ACTION_AGE:
            return False, "Buscar batalhas só fica disponível a partir dos 10 anos."
        if not character.team:
            return False, "Você precisa de pelo menos um Pokémon na equipe para batalhar."
        healthy_team = [pokemon for pokemon in character.team if pokemon.current_health > 0 and pokemon.status != "badly_injured"]
        if not healthy_team:
            return False, "Sua equipe esta sem condicoes para batalhar."

        viable = [
            species
            for species in self.pokemon.values()
            if not species.is_legendary and not species.is_mythic and species.can_be_wild
        ]
        if not viable:
            return False, "Nenhum Pokémon disponível no mundo para batalhar."

        prefix = random.choice(self._TRAINER_PREFIXES)
        area = random.choice(self._TRAINER_AREAS)
        trainer_name = f"{prefix} {area}"

        team_levels = sorted((p.level for p in healthy_team), reverse=True)
        top_level = team_levels[0]
        match_count = min(len(healthy_team), random.randint(1, 3))
        opponents: list[SeriesOpponent] = []
        for _ in range(match_count):
            species = random.choice(viable)
            raw_level = int(top_level * random.uniform(0.82, 1.12)) + random.randint(-1, 2)
            level = coherent_pokemon_level(species, max(3, raw_level))
            opponents.append(SeriesOpponent(trainer_name, species.name, level))

        wins_required = max(1, match_count // 2 + 1)
        preview = estimate_series_chance(character, opponents, self.pokemon, wins_required=wins_required)
        result = run_team_series(
            character,
            opponents,
            self.pokemon,
            wins_required=wins_required,
            important=False,
            title=f"Serie amistosa contra {trainer_name}",
        )

        header = f"TREINADOR|{trainer_name}|{result.total}|{result.wins}|{result.losses}|{'win' if result.won else 'loss'}|{preview['series_chance']}"
        log = [header]
        log.extend(result.log)

        team_xp = 12 * match_count + 18 * result.wins + (12 if result.won else 0)
        xp_notes = self._grant_team_battle_xp(character, team_xp, result.won)
        if xp_notes:
            log.append(f"XP de batalha contra treinador: {team_xp} para a equipe.")
            log.extend(xp_notes)

        if result.won:
            money = random.randint(30, 80) + sum(opponent.level for opponent in opponents) * 2
            character.money += money
            character.modify_attributes({"POK": random.randint(0, 1), "MEN": random.randint(0, 1)})
            log.append(f"Vitoria na serie! +{money}P.")
        else:
            money = random.randint(8, 25)
            character.money += money
            log.append(f"Derrota na serie. Voce recebeu {money}P de consolacao.")

        character.add_history(
            f"Batalhou contra {trainer_name} em uma serie de {match_count} batalha(s). {'Vitoria' if result.won else 'Derrota'}.",
            ["battle", "trainer", "manual"],
        )
        return result.won, "\n".join(log)

    def get_city_gym(self, character: Character) -> dict | None:
        self.ensure_world_generated(character)
        city = self.get_city_services(character.current_city)
        if not city or not city.gym:
            return None
        gym = character.generated_gyms.get(city.gym)
        if not gym:
            return None
        return self._scaled_gym_for_character(gym, character)

    def gym_risk_preview(self, character: Character) -> dict | None:
        gym = self.get_city_gym(character)
        if not gym:
            return None
        if not character.team:
            return {
                "available": False,
                "risk": "impossivel",
                "estimated_win_chance": 0,
                "summary": "Voce precisa de pelo menos um Pokemon na equipe.",
            }
        if not any(pokemon.current_health > 0 and pokemon.status != "badly_injured" for pokemon in character.team):
            return {
                "available": False,
                "risk": "impossivel",
                "estimated_win_chance": 0,
                "summary": "Sua equipe precisa se recuperar antes de desafiar um ginasio.",
            }
        recommended = int(gym["recommended_level"])
        team_levels = sorted((pokemon.level for pokemon in character.team), reverse=True)
        top_three = team_levels[:3]
        average_top = sum(top_three) / len(top_three)
        strongest = team_levels[0]
        opponents = [
            SeriesOpponent(gym["leader"], opponent["species"], int(opponent["level"]))
            for opponent in gym["team"]
        ]
        wins_required = self._gym_wins_required(len(opponents))
        estimate = estimate_series_chance(character, opponents, self.pokemon, wins_required=wins_required)
        estimated = int(estimate["series_chance"])
        if estimated >= 70:
            risk = "baixo"
            advice = "Sua equipe parece pronta, mas ainda e um desafio opcional."
        elif estimated >= 45:
            risk = "moderado"
            advice = "Voce tem uma chance real, mas itens e Pokemon saudaveis importam."
        elif estimated >= 25:
            risk = "alto"
            advice = "O ginasio pode punir uma tentativa apressada."
        else:
            risk = "muito alto"
            advice = "Melhor treinar, curar a equipe ou buscar vantagem de tipo antes."
        return {
            "available": True,
            "risk": risk,
            "estimated_win_chance": estimated,
            "recommended_level": recommended,
            "team_average": round(average_top, 1),
            "strongest_level": strongest,
            "badge": gym["badge"],
            "leader": gym["leader"],
            "main_type": gym["main_type"],
            "opponents": len(opponents),
            "wins_required": estimate["wins_required"],
            "average_match_chance": estimate["average_match_chance"],
            "match_chances": estimate["match_chances"],
            "summary": advice,
        }

    def _scaled_gym_for_character(self, gym: dict, character: Character) -> dict:
        team_levels = sorted((pokemon.level for pokemon in character.team), reverse=True)
        if not team_levels:
            team_levels = sorted((pokemon.level for pokemon in character.box), reverse=True)
        strongest = team_levels[0] if team_levels else int(gym.get("recommended_level", 12))
        top_three = team_levels[:3] or [strongest]
        average_top = round(sum(top_three) / len(top_three))
        badge_pressure = min(4, len(character.badges))
        base_level = average_top + badge_pressure - 1
        base_level = min(base_level, strongest + 1)
        base_level = max(12, min(41, base_level))
        scaled = dict(gym)
        scaled["recommended_level"] = base_level
        scaled["level_range"] = [base_level, min(41, base_level + 3)]
        scaled_team = []
        for index, member in enumerate(gym["team"][:self._gym_team_size(gym)]):
            level = min(41, base_level + (index % 4))
            scaled_team.append({**member, "level": level})
        scaled["team"] = scaled_team
        return scaled

    def _gym_team_size(self, gym: dict) -> int:
        difficulty = int(gym.get("difficulty", 1))
        if difficulty <= 3:
            return 3
        if difficulty <= 6:
            return 4
        if difficulty <= 8:
            return 5
        return 6

    def _gym_wins_required(self, team_size: int) -> int:
        if team_size <= 3:
            return 2
        if team_size <= 4:
            return 3
        if team_size <= 5:
            return 3
        return 4

    def challenge_city_gym(self, character: Character) -> tuple[bool, list[str]]:
        self.ensure_world_generated(character)
        if is_dead(character):
            return False, ["Game over: personagem falecido."]
        if character.flags.get("in_prison"):
            return False, ["Voce nao pode desafiar ginasios enquanto esta preso."]
        gym = self.get_city_gym(character)
        if not gym:
            return False, ["Nao ha ginasio disponivel nesta cidade."]
        if gym["badge"] in character.badges:
            return False, [f"Voce ja possui {gym['badge']}."]
        if not character.team:
            return False, ["Voce precisa de pelo menos um Pokemon para desafiar um ginasio."]
        active = character.active_pokemon()
        if active is None:
            return False, ["Voce precisa de pelo menos um Pokemon para desafiar um ginasio."]

        opponents = [
            SeriesOpponent(gym["leader"], opponent["species"], int(opponent["level"]))
            for opponent in gym["team"]
        ]
        wins_required = self._gym_wins_required(len(opponents))
        preview = estimate_series_chance(character, opponents, self.pokemon, wins_required=wins_required)
        logs = [
            f"Desafio iniciado contra {gym['leader']} em {gym['city']}.",
            f"Formato: serie de equipe contra {len(opponents)} Pokemon; precisa vencer {wins_required}. Chance estimada da serie: {preview['series_chance']}%."
        ]
        for pokemon in character.team:
            auto_item = self._auto_use_healing_item(character, pokemon)
            if auto_item:
                logs.append(auto_item)
        result = run_team_series(
            character,
            opponents,
            self.pokemon,
            wins_required=wins_required,
            important=True,
            title=f"Serie de ginasio pela {gym['badge']}",
        )
        logs.extend(result.log)
        won_all = result.won
        team_xp = 10 * len(opponents) + 18 * result.wins + (30 if won_all else 0)
        xp_notes = self._grant_team_battle_xp(character, team_xp, won_all)
        if xp_notes:
            logs.append(f"XP de batalha contra treinador: {team_xp} para a equipe.")
            logs.extend(xp_notes)

        if won_all:
            character.badges.append(gym["badge"])
            reward = 300 + gym["difficulty"] * 150
            character.money += reward
            character.reputation = clamp_reputation(character.reputation + 3 + gym["difficulty"])
            character.add_history(f"Voce venceu {gym['leader']} e recebeu {gym['badge']}.", ["gym", "badge"])
            logs.append(f"Vitoria no ginasio! Voce recebeu {gym['badge']} e {reward} Pokedollar.")
        else:
            loss = min(character.money, 80 + gym["difficulty"] * 30)
            character.money -= loss
            character.add_history(f"Voce perdeu para {gym['leader']} no ginasio de {gym['city']}.", ["gym", "loss"])
            logs.append(f"Derrota no ginasio. Voce perdeu {loss} Pokedollar em custos e recuperacao.")
        return won_all, logs

    def _grant_team_battle_xp(self, character: Character, amount: int, won_series: bool) -> list[str]:
        notes: list[str] = []
        if amount <= 0:
            return notes
        for pokemon in character.team:
            if pokemon.status == "badly_injured":
                xp = max(4, amount // 2)
            else:
                xp = amount
            if won_series:
                pokemon.bond = min(100, pokemon.bond + 1)
            notes.extend(grant_pokemon_xp(pokemon, xp, self.pokemon))
        return notes

    def _best_team_member_for_opponent(self, character: Character, opponent_species_name: str, excluded_indexes: set[int] | None = None):
        opponent_species = self.pokemon.get(opponent_species_name)
        if not opponent_species:
            return character.active_pokemon()
        excluded_indexes = excluded_indexes or set()
        best = None
        best_score = -1.0
        for index, pokemon in enumerate(character.team):
            if index in excluded_indexes:
                continue
            species = self.pokemon.get(pokemon.species)
            if not species or pokemon.current_health <= 0:
                continue
            if not pokemon.types:
                pokemon.types = list(species.types)
            type_factor = get_type_factor(pokemon.types, opponent_species.types)
            health_factor = pokemon.health_percent(species)
            score = (
                pokemon.level * 2.4
                + pokemon.combat * 0.35
                + pokemon.healthy * 0.18
                + type_factor * 28
                + health_factor * 18
            )
            if score > best_score:
                best = pokemon
                best_score = score
        return best

    def apply_event_choice(self, character: Character, event: LifeEvent, choice_index: int) -> str:
        choice = event.choices[choice_index]
        result = apply_choice_result(character, event, choice)
        self._scale_event_effects_for_period(character, result.effects)
        self._apply_engine_effects(character, result.effects)
        if result.history_entry:
            self._append_to_annual_report(character, result.history_entry)
        return result.history_entry

    def _scale_event_effects_for_period(self, character: Character, effects: dict) -> None:
        months = int(character.flags.get("current_period_months", 12))
        if months >= 12 or not effects:
            return
        factor = months / 12
        reduction = 1 - factor
        if "health" in effects:
            delta = int(effects.get("health", 0))
            character.health = int(max(0, min(100, character.health - round(delta * reduction))))
        if "money" in effects:
            delta = int(effects.get("money", 0))
            character.money = max(0, character.money - round(delta * reduction))
        if "reputation" in effects:
            delta = int(effects.get("reputation", 0))
            character.reputation = clamp_reputation(character.reputation - round(delta * reduction))
        attr_effects = effects.get("attributes", {})
        if attr_effects:
            rollback = {
                key: -round(int(value) * reduction)
                for key, value in attr_effects.items()
                if isinstance(value, int)
            }
            character.attributes.modify(rollback)

    def _append_to_annual_report(self, character: Character, text: str) -> None:
        report = character.flags.get("last_year_report")
        if not report or text in str(report):
            return
        character.flags["last_year_report"] = f"{report}\nEvento: {_clean_sentence(text)}."

    def _apply_engine_effects(self, character: Character, effects: dict) -> None:
        for reward in effects.get("pokemon", []):
            species_name = reward["species"]
            if species_name not in self.pokemon:
                continue
            level = int(reward.get("level", max(1, min(5, character.age + 1))))
            origin = reward.get("origin", f"evento em {character.current_city}")
            pokemon = create_owned_pokemon(self.pokemon[species_name], level=level, origin=origin, species_by_name=self.pokemon)
            destination = character.add_pokemon(pokemon)
            location = "equipe ativa" if destination == "team" else "Box"
            character.register_caught(species_name)
            character.add_history(f"{pokemon.display_name()} entrou para sua {location} por meio de um evento.", ["pokemon", "event"])
        for reward in effects.get("random_area_pokemon", []):
            location_name = reward.get("location", character.current_city)
            encounter = self._choose_encounter(location_name)
            if not encounter:
                continue
            species = self.pokemon[encounter["species"]]
            level = coherent_pokemon_level(species, int(reward.get("level", max(1, min(5, encounter["min_level"])))), self.pokemon)
            pokemon = create_owned_pokemon(species, level=level, origin=reward.get("origin", f"evento em {location_name}"), species_by_name=self.pokemon)
            destination = character.add_pokemon(pokemon)
            place = "equipe ativa" if destination == "team" else "Box"
            character.register_caught(species.name)
            character.add_history(f"{pokemon.species} se juntou a sua {place} em {location_name}.", ["pokemon", "event"])
        for egg_reward in effects.get("eggs", []):
            tier = egg_reward.get("tier") or choose_egg_tier(egg_reward.get("tier_weights"))
            egg = create_random_egg(
                self.pokemon,
                tier=tier,
                origin=egg_reward.get("origin", f"evento em {character.current_city}"),
                type_hint=egg_reward.get("type_hint"),
            )
            character.eggs.append(egg)
            character.add_history(
                f"Voce recebeu um ovo {egg.color} de raridade {egg.rarity_label}.",
                ["egg", "event"],
            )

    def wild_encounter(self, character: Character) -> tuple[PokemonSpecies, int, str]:
        if int(character.flags.get("repel_years", 0)) > 0 and random.random() < 0.65:
            character.flags["repel_years"] = int(character.flags.get("repel_years", 0)) - 1
            species = self.pokemon["Magikarp"]
            character.register_seen(species.name)
            return species, 1, "O Repel afastou os encontros selvagens mais perigosos. Voce so viu um Magikarp distante."
        location = self.get_location(character.current_city)
        if location and not location.encounter_enabled:
            encounter = None
        else:
            encounter = self._choose_encounter(character.current_city)
        if encounter:
            species = self.pokemon[encounter["species"]]
            level = coherent_pokemon_level(species, random.randint(encounter["min_level"], encounter["max_level"]), self.pokemon)
        else:
            possible = [
                species for species in self.pokemon.values()
                if species.can_be_wild and not species.is_legendary and species.rarity in {"common", "uncommon"}
                and minimum_level_for_species(species, self.pokemon) <= max(4, min(12, character.age + 2))
            ]
            species = random.choice(possible)
            level = coherent_pokemon_level(species, random.randint(3, max(4, min(12, character.age + 2))), self.pokemon)
        character.register_seen(species.name)
        text = f"Um {species.name} selvagem de nivel {level} apareceu perto de {self.display_location_name(character.current_city)}."
        return species, level, text

    def _choose_encounter(self, location_name: str) -> dict | None:
        location_id = self.location_ids_by_name.get(location_name, location_name)
        location = self.locations.get(location_id)
        if location and not location.capture_enabled:
            return None
        encounter_location = self._choose_encounter_table(location_name, location_id)
        if not encounter_location and location_name == "Pallet Town":
            encounter_location = self.encounters.get("route_1")
        if not encounter_location:
            return None
        encounters = [item for item in encounter_location.get("encounters", []) if item["species"] in self.pokemon]
        if not encounters:
            return None
        return random.choices(encounters, weights=[item.get("weight", 1) for item in encounters], k=1)[0]

    def _choose_encounter_table(self, location_name: str, location_id: str) -> dict | None:
        sources = [location_id]
        location = self.locations.get(location_id)
        city = self.city_services.get(location.name if location else location_name)
        if city and city.encounter_sources:
            sources.extend(city.encounter_sources)
        tables = [self.encounters[source] for source in sources if source in self.encounters]
        if not tables:
            return None
        return random.choice(tables)

    def get_location(self, location_name_or_id: str) -> Location | None:
        location_id = self.location_ids_by_name.get(location_name_or_id, location_name_or_id)
        return self.locations.get(location_id)

    def display_location_name(self, location_name_or_id: str) -> str:
        location = self.get_location(location_name_or_id)
        if not location:
            return location_name_or_id
        if self.grid:
            cell = self.grid.cell_for_location(location.location_id)
            if cell and cell.name:
                return cell.name
        return location.name

    def capture_wild(self, character: Character, species_name: str, level: int) -> tuple[bool, str]:
        ball = self.best_available_ball(character, self.pokemon[species_name])
        success, message, _ = try_capture(character, self.pokemon[species_name], level, ball=ball, item=self.items.get(ball), species_by_name=self.pokemon)
        if success:
            character.register_caught(species_name)
        else:
            character.register_seen(species_name)
        return success, message

    def best_available_ball(self, character: Character, species: PokemonSpecies) -> str:
        available = [name for name, amount in character.inventory.items() if amount > 0 and name in self.items and self.items[name].item_type == "capture"]
        if not available:
            return "Poke Ball"
        return max(
            available,
            key=lambda name: self.items[name].capture_bonus_for(species.rarity, species.types, species.evolution_stage),
        )

    def battle_wild(self, character: Character, species_name: str, level: int) -> tuple[bool, list[str]]:
        if not character.team:
            return False, ["Voce ainda nao tem Pokemon para batalhar."]
        active = character.active_pokemon()
        if active is None:
            return False, ["Voce ainda nao tem Pokemon para batalhar."]
        prefix = self._auto_use_healing_item(character, active)
        won, log = simulate_simple_battle(
            character,
            active,
            self.pokemon[active.species],
            f"{species_name} selvagem",
            self.pokemon[species_name],
            level,
            species_by_name=self.pokemon,
        )
        if prefix:
            log.insert(0, prefix)
        return won, log

    def _auto_use_healing_item(self, character: Character, pokemon) -> str | None:
        if pokemon.health_percent(self.pokemon.get(pokemon.species)) > 0.45:
            return None
        for item_name in ("Super Potion", "Potion"):
            if character.inventory.get(item_name, 0) > 0:
                success, message = self.use_item(character, item_name)
                if success:
                    return f"Uso automatico: {message}"
        return None

    def _has_kanto_map(self, character: Character) -> bool:
        return bool(character.flags.get("has_kanto_map")) or character.inventory.get("Mapa de Kanto", 0) > 0

    def _travel_supply_cost(self, character: Character) -> int:
        requested = random.randint(20, 60)
        cost = min(character.money, requested)
        character.money -= cost
        return cost

    def move_to_city(self, character: Character, city_name: str) -> TravelResult:
        if not self.can_travel(character):
            return TravelResult(False, "Voce ainda e jovem demais para viajar sozinho.")

        if not self._has_kanto_map(character):
            ok, new_city = self.travel_random(character)
            if ok:
                travel_cost = self._travel_supply_cost(character)
                suffix = f" (-{travel_cost}P em suprimentos)" if travel_cost else ""
                return TravelResult(True, f"Sem o Mapa de Kanto, voce viajou ao acaso e chegou em {new_city}.{suffix}")
            return TravelResult(False, "Nao foi possivel viajar sem mapa.")

        location = self.get_location(city_name)
        if location and location.kind == "city":
            old_city = self.display_location_name(character.current_city)
            if location.location_id == character.current_city:
                return TravelResult(False, "Voce ja esta nesta cidade.")
            character.current_city = location.location_id
            travel_cost = self._travel_supply_cost(character)
            suffix = f" (-{travel_cost}P)" if travel_cost else ""
            character.add_history(f"Voce viajou de {old_city} para {location.name}.{suffix}", ["travel"])
            return TravelResult(True, f"Voce chegou em {location.name}.")
        return TravelResult(False, "Destino nao encontrado.")

    def move_to_location(self, character: Character, location_name_or_id: str) -> bool:
        if not self.can_travel(character):
            return False
        location = self.get_location(location_name_or_id)
        if not location:
            return False
        character.current_city = location.location_id
        character.add_history(f"Voce chegou a {location.name}.", ["travel"])
        return True

    def travel_random(self, character: Character) -> tuple[bool, str]:
        """Viaja para uma célula adjacente aleatória (sem mapa)."""
        if not self.can_travel(character):
            return False, "Voce ainda e jovem demais para viajar sozinho."
        if self.grid is None:
            return False, "Sistema de mapa nao disponivel."
        current_coord = self.current_coord(character)
        if not current_coord:
            return False, "Posicao atual nao encontrada no mapa."
        options = self.grid.adjacent(current_coord)
        if not options:
            return False, "Nao ha para onde ir daqui."
        destination = random.choice(options)
        old_city = self.display_location_name(character.current_city)
        character.current_city = destination.location_id or destination.name or destination.coord
        new_city = self.display_location_name(character.current_city)
        character.add_history(
            f"Voce partiu de {old_city} e acabou em {new_city}.", ["travel"]
        )
        return True, new_city

    def can_travel(self, character: Character) -> bool:
        return character.age >= 10

    def set_active_pokemon(self, character: Character, index: int) -> bool:
        return character.set_active_pokemon(index)

    def move_team_to_box(self, character: Character, team_index: int) -> tuple[bool, str]:
        if len(character.team) <= 1:
            return False, "Voce precisa manter pelo menos um Pokemon na equipe."
        if team_index < 0 or team_index >= len(character.team):
            return False, "Pokemon invalido."
        pokemon = character.team.pop(team_index)
        pokemon.active = False
        character.box.append(pokemon)
        character._sync_active_flags()
        return True, f"{pokemon.display_name()} foi enviado para a Box."

    def move_box_to_team(self, character: Character, box_index: int) -> tuple[bool, str]:
        if box_index < 0 or box_index >= len(character.box):
            return False, "Pokemon invalido."
        if len(character.team) >= 6:
            return False, "A equipe ja tem 6 Pokemon."
        pokemon = character.box.pop(box_index)
        character.add_pokemon(pokemon)
        return True, f"{pokemon.display_name()} entrou na equipe."

    def swap_box_pokemon(self, character: Character, team_index: int, box_index: int) -> tuple[bool, str]:
        """Troca um Pokemon da equipe com um da box."""
        if team_index < 0 or team_index >= len(character.team):
            return False, "Indice de equipe invalido."
        if box_index < 0 or box_index >= len(character.box):
            return False, "Indice de box invalido."
        team_poke = character.team[team_index]
        box_poke = character.box[box_index]
        character.team[team_index] = box_poke
        character.box[box_index] = team_poke
        box_poke.active = team_poke.active
        team_poke.active = False
        character._sync_active_flags()
        return True, f"{box_poke.display_name()} entrou na equipe. {team_poke.display_name()} foi para a box."

    def reorder_team(self, character: Character, from_index: int, to_index: int) -> tuple[bool, str]:
        """Move um Pokemon para outra posicao na equipe."""
        n = len(character.team)
        if from_index < 0 or from_index >= n or to_index < 0 or to_index >= n or from_index == to_index:
            return False, "Indices invalidos."
        pokemon = character.team.pop(from_index)
        character.team.insert(to_index, pokemon)
        # Mantem o ativo no indice correto
        if character.active_pokemon_index == from_index:
            character.active_pokemon_index = to_index
        elif from_index < character.active_pokemon_index <= to_index:
            character.active_pokemon_index -= 1
        elif to_index <= character.active_pokemon_index < from_index:
            character.active_pokemon_index += 1
        character._sync_active_flags()
        return True, f"{pokemon.display_name()} movido para posicao {to_index + 1}."

    # ------------------------------------------------------------------ #
    # VIAGEM — grade estilo batalha naval                                  #
    # ------------------------------------------------------------------ #

    def current_coord(self, character: Character) -> str | None:
        """Retorna a coordenada de grade da posição atual do personagem."""
        if self.grid is None:
            return None
        cell = self.grid.cell_for_location(character.current_city)
        return cell.coord if cell else None

    def travel_destinations(self, character: Character) -> list[dict]:
        """Retorna células adjacentes passáveis.
        Sem mapa: nome e serviços ficam ocultos (névoa de guerra).
        Com mapa: mostra tudo.
        """
        if not self.can_travel(character):
            return []
        if self.grid is None:
            return []
        has_map = self._has_kanto_map(character)
        current_coord = self.current_coord(character)
        if not current_coord:
            return []
        adjacent = self.grid.adjacent(current_coord)
        result = []
        for cell in adjacent:
            entry: dict = {"coord": cell.coord, "kind": cell.kind, "icon": cell.icon}
            if has_map:
                entry["name"] = cell.name or cell.coord
                entry["description"] = ""
                location = self.get_location(cell.location_id or "")
                city_svc = self.city_services.get(location.name if location else cell.name or "")
                entry["services"] = city_svc.services if city_svc else []
                entry["has_gym"] = bool(city_svc and city_svc.gym) if city_svc else False
            else:
                entry["name"] = "???"
            result.append(entry)
        return result

    def full_grid_for_display(self, character: Character) -> list[list[dict]]:
        """Retorna a grade completa formatada para exibição (com mapa)."""
        if self.grid is None:
            return []
        current_coord = self.current_coord(character)
        grid_rows = []
        for row in self.grid.rows:
            row_cells = []
            for col in self.grid.cols:
                coord = f"{row}{col}"
                cell = self.grid.get(coord)
                if cell is None:
                    row_cells.append({"coord": coord, "name": "   ", "icon": "  ", "current": False, "passable": False})
                    continue
                row_cells.append({
                    "coord": coord,
                    "name": cell.name or "---",
                    "icon": cell.icon,
                    "kind": cell.kind,
                    "current": coord == current_coord,
                    "passable": cell.passable,
                })
            grid_rows.append(row_cells)
        return grid_rows

    def travel_to(self, character: Character, coord_or_name: str) -> tuple[bool, str]:
        """Move o personagem para uma célula adjacente (por coordenada ou nome)."""
        if not self.can_travel(character):
            return False, "Voce ainda e jovem demais para viajar sozinho."
        if self.grid is None:
            return False, "Sistema de mapa nao disponivel."
        # Resolve coordenada
        cell = self.grid.get(coord_or_name.upper()) or self.grid.cell_for_location(coord_or_name)
        if cell is None or not cell.passable:
            return False, f"{coord_or_name} nao e um destino valido."
        current_coord = self.current_coord(character)
        if current_coord and cell.coord not in [c.coord for c in self.grid.adjacent(current_coord)]:
            return False, f"{cell.name or cell.coord} nao e adjacente a sua posicao atual."
        target_location = cell.location_id or cell.name or cell.coord
        if target_location == character.current_city:
            return False, f"Voce ja esta em {self.display_location_name(character.current_city)}."
        old = self.display_location_name(character.current_city)
        character.current_city = target_location
        new = self.display_location_name(character.current_city)
        character.add_history(f"Voce viajou de {old} para {new}.", ["travel"])
        return True, f"Voce chegou a {new}! [{cell.coord}]"

    # ------------------------------------------------------------------ #
    # CARREIRA — PROGRESSÃO MANUAL                                         #
    # ------------------------------------------------------------------ #

    def manual_action_focus_career(self, character: Character) -> str:
        """Foca na carreira atual: ganha XP de rank e dinheiro proporcional."""
        if character.age < MIN_CHILD_ACTION_AGE:
            return "Voce ainda e muito novo para focar em uma rotina de carreira."
        if not character.career:
            return "Voce nao tem uma carreira definida. Escolha uma primeiro."
        if not self._period_action_available(character, "career_focus"):
            return "Voce ja focou na carreira neste periodo. Avance o tempo para fazer isso novamente."
        self._mark_period_action_used(character, "career_focus")
        rank = character.career_rank()
        rank_mult = 1.0 + rank * 0.20
        # Renda da sessão de trabalho dedicada
        base = {
            "Treinador": 120,
            "Criador": 100,
            "Coordenador": 110,
            "Estudante da academia": 40,
            "Pesquisador": 130,
            "Explorador": 105,
            "Cientista": 145,
            "Coletor de Berrys": 80,
            "Construtor de Pokebolas": 115,
            "Cuidador de Fazenda": 90,
            "Construtor": 120,
            "Comerciante": 130,
            "Criminoso": 150,
        }.get(character.career, 80)
        income = int(calculate_money_gain(base, character.attributes) * rank_mult)
        character.money += income
        # Sobe atributo relevante
        attr_map = {
            "Treinador": {"PHY": 1, "POK": 1},
            "Criador": {"POK": 1, "MEN": 1},
            "Coordenador": {"LUK": 1, "POK": 1},
            "Estudante da academia": {"MEN": 2},
            "Pesquisador": {"MEN": 1, "POK": 1},
            "Explorador": {"PHY": 1, "LUK": 1},
            "Cientista": {"MEN": 2},
            "Coletor de Berrys": {"PHY": 1, "POK": 1},
            "Construtor de Pokebolas": {"MEN": 1, "POK": 1},
            "Cuidador de Fazenda": {"POK": 1, "MEN": 1},
            "Construtor": {"PHY": 2},
            "Comerciante": {"MEN": 1, "LUK": 1},
            "Criminoso": {"LUK": 1, "PHY": 1},
        }
        character.modify_attributes(attr_map.get(character.career, {}))
        # XP de carreira
        xp_gain = 8 + rank * 2
        character.career_ranks, character.career_xp, rank_msg = try_career_rank_up(
            character.career, character.career_ranks, character.career_xp, xp_gain
        )
        suffix = f" {rank_msg}" if rank_msg else ""
        character.add_history(
            f"Voce se dedicou a sua carreira de {character.career} e ganhou {income} Pokedollar.",
            ["manual", "work", "career"],
        )
        return f"Dedicacao a carreira: +{income} Pokedollar.{suffix}"


    def career_rank_info(self, character: Character) -> str:
        if not character.career:
            return "Sem carreira definida."
        from .careers import CAREER_RANK_XP
        rank = character.career_rank()
        label = career_rank_label(character.career, character.career_ranks)
        xp = character.career_xp.get(character.career, 0)
        needed = CAREER_RANK_XP[rank] if rank < 5 else 0
        if rank >= 5:
            return f"{character.career} — {label} (rank maximo)"
        return f"{character.career} — {label} (rank {rank}/5, {xp}/{needed} XP)"

    # ------------------------------------------------------------------ #
    # POKÉDEX                                                              #
    # ------------------------------------------------------------------ #

    def reputation_info(self, character: Character) -> str:
        return reputation_summary(character.reputation)

    def pokedex_summary(self, character: Character) -> dict:
        caught = list(character.pokedex_caught)
        seen_set = set(character.pokedex_seen) | set(caught)
        return {
            "seen": len(seen_set),
            "caught": len(caught),
            "total": len(self.pokemon),
            "seen_list": sorted(seen_set),
            "caught_list": sorted(caught),
        }

    # ------------------------------------------------------------------ #
    # TORNEIOS                                                             #
    # ------------------------------------------------------------------ #

    def available_tournaments(self, character: Character) -> list[dict]:
        result = []
        for kind, cfg in TOURNAMENT_KINDS.items():
            ok, reason = can_enter_tournament(character, kind)
            result.append({
                "kind": kind,
                "label": cfg["label"],
                "available": ok,
                "reason": reason,
                "entry_fee": cfg["entry_fee"],
                "prize_pool": cfg["base_prize"] + cfg["prize_per_round"] * cfg["rounds"],
                "rounds": cfg["rounds"],
                "min_badges": cfg.get("min_badges", 0),
                "min_reputation": cfg.get("min_reputation", 0),
            })
        return result

    def enter_tournament(self, character: Character, kind: str) -> tuple[bool, "TournamentResult | None", str]:
        ok, reason = can_enter_tournament(character, kind)
        if not ok:
            return False, None, reason
        if not self._period_action_available(character, "tournament"):
            return False, None, "Voce ja participou de um torneio neste periodo."
        cfg = TOURNAMENT_KINDS[kind]
        character.money = max(0, character.money - cfg["entry_fee"])
        opponents = generate_tournament(character, self.pokemon, kind, self.name_database)
        result = run_tournament(character, opponents, self.pokemon, kind)
        if result.prize_money > 0:
            character.money += result.prize_money
        character.reputation = clamp_reputation(character.reputation + result.rep_gained)
        if result.champion:
            summary = f"Voce venceu o {cfg['label']}! Premio: {result.prize_money} Pokedollar."
            character.add_history(summary, ["tournament", "win"])
        else:
            summary = f"Voce chegou ate a rodada {result.rounds_won + 1} no {cfg['label']}."
            character.add_history(summary, ["tournament"])
        self._mark_period_action_used(character, "tournament")
        return True, result, summary

    # ------------------------------------------------------------------ #
    # CONTESTS E BREEDING                                                  #
    # ------------------------------------------------------------------ #

    def enter_contest(self, character: Character, pokemon_index: int = 0, difficulty: str = "local", category: str = "beauty") -> tuple[bool, "ContestResult | None", str]:
        if is_dead(character):
            return False, None, "Game over: personagem falecido."
        if character.age < 10:
            return False, None, "Voce ainda e jovem demais para concursos."
        if not self._period_action_available(character, "contest"):
            return False, None, "Voce ja participou de um contest neste periodo."
        if pokemon_index < 0 or pokemon_index >= len(character.team):
            return False, None, "Pokemon invalido para contest."
        entry_fee = {"local": 80, "city": 180, "regional": 450}.get(difficulty, 80)
        if character.money < entry_fee:
            return False, None, f"Inscricao custa {entry_fee}P."
        pokemon = character.team[pokemon_index]
        species = self.pokemon.get(pokemon.species)
        if not species:
            return False, None, "Especie nao encontrada."
        character.money -= entry_fee
        result = run_contest(character, pokemon, species, difficulty, category)
        character.money += result.prize_money

        character.reputation = clamp_reputation(character.reputation + result.rep_gained)
        if result.rank == 1:
            ribbon = _contest_ribbon_label(category, difficulty)
            ribbons = list(character.flags.get("contest_ribbons", []))
            if ribbon not in ribbons:
                ribbons.append(ribbon)
            character.flags["contest_ribbons"] = ribbons
            history = f"{pokemon.display_name()} venceu um contest {difficulty}."
            character.add_history(history, ["contest", "win"])
        else:
            history = f"{pokemon.display_name()} ficou em {result.rank}o lugar em um contest {difficulty}."
            character.add_history(history, ["contest"])
        self._mark_period_action_used(character, "contest")
        summary_msg = (
            f"{pokemon.display_name()} ficou em {result.rank}o lugar no contest {difficulty} ({category})."
            f" Premio: {result.prize_money}P."
        )
        return True, result, summary_msg

    def breed_pokemon(self, character: Character, first: int = 0, second: int = 1) -> tuple[bool, str]:
        if is_dead(character):
            return False, "Game over: personagem falecido."
        if character.age < 10:
            return False, "Voce ainda e jovem demais para breeding."
        if not self._period_action_available(character, "breed"):
            return False, "Voce ja tentou breeding neste periodo."
        if len(character.team) < 2:
            return False, "Voce precisa de pelo menos 2 Pokemon na equipe para tentar breeding."
        if first < 0 or first >= len(character.team) or second < 0 or second >= len(character.team) or first == second:
            return False, "Indices de Pokemon invalidos para breeding."
        pok_a = character.team[first]
        pok_b = character.team[second]
        if not self.pokemon.get(pok_a.species) or not self.pokemon.get(pok_b.species):
            return False, "Especie nao encontrada."
        chance = breed_success_chance(character, pok_a, pok_b)
        self._mark_period_action_used(character, "breed")
        success, egg, message = create_bred_egg(character, pok_a, pok_b, self.pokemon)
        if success and egg:
            character.eggs.append(egg)
            character.reputation = clamp_reputation(character.reputation + (2 if character.career == "Criador" else 1))
            message = (
                f"Breeding bem-sucedido: {pok_a.display_name()} e {pok_b.display_name()} "
                f"produziram um ovo {egg.color} ({egg.rarity_label}). Chance era {chance * 100:.0f}%."
            )
            character.add_history(message, ["breed", "egg"])
            return True, message
        message = (
            f"O breeding entre {pok_a.display_name()} e {pok_b.display_name()} nao gerou ovo desta vez. "
            f"Chance era {chance * 100:.0f}%."
        )
        character.add_history(message, ["breed"])
        return False, message

    def breeding_preview(self, character: Character, first: int = 0, second: int = 1) -> dict:
        if is_dead(character):
            return {"available": False, "summary": "Game over: personagem falecido."}
        if character.age < MIN_JOURNEY_ACTION_AGE:
            return {"available": False, "summary": "Criacao Pokemon fica disponivel a partir dos 10 anos."}
        if len(character.team) < 2 or first == second:
            return {"available": False, "summary": "Criacao exige dois Pokemon diferentes na equipe."}
        if first < 0 or second < 0 or first >= len(character.team) or second >= len(character.team):
            return {"available": False, "summary": "Pokemon invalido para criacao."}
        first_pokemon = character.team[first]
        second_pokemon = character.team[second]
        chance = breed_success_chance(character, first_pokemon, second_pokemon)
        return {
            "available": True,
            "first": first_pokemon.display_name(),
            "second": second_pokemon.display_name(),
            "chance": round(chance * 100, 1),
            "career_bonus": character.career == "Criador",
            "summary": f"Chance estimada: {chance * 100:.1f}%.",
        }


def _is_history_worthy(note: str) -> bool:
    """Decide se uma nota de atividade merece entrar no historico do personagem."""
    if not note or len(note) < 15:
        return False
    if note.startswith("BATALHA|") or note.startswith("XP:") or note.startswith("Nivel "):
        return False
    skip_prefixes = ("Passou o ano", "Sem novidades", "XP de carreira")
    if any(note.startswith(p) for p in skip_prefixes):
        return False
    return True


def _clean_sentence(text: str) -> str:
    text = str(text).strip()
    if not text:
        return text
    text = text[0].upper() + text[1:]
    if not text.endswith((".", "!", "?")):
        text = text.rstrip(".") + "."
    return text
