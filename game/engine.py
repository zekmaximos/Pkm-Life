from __future__ import annotations

import json
from pathlib import Path
import random

from .battle import simulate_simple_battle
from .auto_year import automatic_encounter_chance, decide_auto_encounter_action
from .careers import available_careers, career_progress, try_career_rank_up, career_rank_label
from .capture import try_capture
from .character import Character
from .city import CityServices
from .eggs import choose_egg_tier, create_random_egg
from .events import LifeEvent, apply_choice_result, choose_weighted_event, should_roll_life_event
from .gyms import GymTemplate, generate_gyms
from .inventory import Item, add_item, consume_item
from .locations import Location
from .names import NameDatabase
from .pokemon import PokemonSpecies, assign_evolution_stages, create_owned_pokemon
from .progression import progress_year
from .progression import grant_pokemon_xp
from .economy import calculate_money_gain
from .tournaments import (
    generate_tournament, run_tournament, can_enter_tournament,
    TOURNAMENT_KINDS, TournamentResult,
)


DATA_DIR = Path("data")


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

    def _load_json(self, filename: str) -> list[dict] | list[str]:
        path = self.data_dir / filename
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_json_object(self, filename: str) -> dict:
        path = self.data_dir / filename
        return json.loads(path.read_text(encoding="utf-8"))

    def create_character(self, name: str, hometown: str = "Pallet Town") -> Character:
        character = Character(name=name.strip() or "Red", hometown=hometown, current_city=hometown)
        self.ensure_world_generated(character)
        character.add_history(f"Voce nasceu em {hometown}, na regiao de Kanto.", ["birth"])
        return character

    def ensure_world_generated(self, character: Character) -> None:
        if character.generated_gyms:
            return
        if self.name_database is None:
            raise RuntimeError("Name database was not loaded.")
        character.generated_gyms = generate_gyms(self.gym_templates, self.pokemon, self.name_database)

    def advance_year(self, character: Character) -> LifeEvent | None:
        # --- Verifica hospitalização por saúde zerada ---
        if character.health <= 0:
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

        # XP de carreira automático por passar o ano
        if character.career:
            rank_xp = 3 + (1 if character.career != "Estudante da academia" else 0)
            character.career_ranks, character.career_xp, rank_msg = try_career_rank_up(
                character.career, character.career_ranks, character.career_xp, rank_xp
            )
            if rank_msg:
                year_notes.append(rank_msg)
                character.add_history(rank_msg, ["career", "rank_up"])

        if character.age == 10 and not character.flags.get("oak_event_done") and not self.character_has_pokemon(character):
            report = self.build_annual_report(character, before, year_notes)
            character.flags["last_year_report"] = report
            return self.professor_oak_event()

        for note in self.resolve_automatic_year_encounter(character):
            year_notes.append(note)
            character.add_history(note, ["auto_encounter"])

        gym_invite = self.resolve_automatic_gym_invite(character)
        if gym_invite:
            year_notes.append(gym_invite)
            character.add_history(gym_invite, ["gym", "invite"])

        report = self.build_annual_report(character, before, year_notes)
        character.flags["last_year_report"] = report
        # Relatório anual fica SOMENTE em flags, não polui o histórico

        event_pool = self.childhood_events if character.age < 10 else self.journey_events
        city_focus = self._event_focus_for(character)
        if not should_roll_life_event(character, event_pool, city_focus):
            return None
        return choose_weighted_event(character, event_pool, city_focus)

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
        level = random.randint(encounter["min_level"], encounter["max_level"])
        has_ball = any(
            amount > 0 and name in self.items and self.items[name].item_type == "capture"
            for name, amount in character.inventory.items()
        )
        action = decide_auto_encounter_action(character, species, level, has_ball)
        notes = [f"Durante o ano, voce encontrou um {species.name} selvagem de nivel {level} em {character.current_city}."]
        if action == "capture":
            success, message = self.capture_wild(character, species.name, level)
            notes.append(f"Captura automatica: {message}")
        elif action == "battle":
            won, log = self.battle_wild(character, species.name, level)
            notes.append(f"Batalha automatica: {log[-2] if len(log) >= 2 else log[-1]}")
        else:
            character.attributes.modify({"POK": 1})
            notes.append(f"Voce observou {species.name} e aprendeu sobre seu comportamento. POK +1.")
        return notes

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

    def build_annual_report(self, character: Character, before: dict, notes: list[str]) -> str:
        money_delta = character.money - int(before["money"])
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
        battles = sum(1 for note in notes if "Batalha automatica" in note)
        captures = sum(1 for note in notes if "Captura automatica" in note and "foi capturado" in note)
        observations = sum(1 for note in notes if "observou" in note)
        lines = [f"Resumo anual aos {character.age} anos"]
        lines.append(f"Local: {before['city']}." if before["city"] == character.current_city else f"Local: {before['city']} -> {character.current_city}.")
        if level_ups:
            lines.append(f"Treino: sua equipe ganhou {level_ups} nivel(is).")
        else:
            lines.append("Treino: nenhum nivel ganho.")
        pokemon_parts = []
        if new_pokemon > 0:
            pokemon_parts.append(f"{new_pokemon} novo(s) Pokemon")
        if evolutions:
            pokemon_parts.append("evolucoes: " + ", ".join(evolutions))
        if not pokemon_parts:
            pokemon_parts.append("sem novas capturas ou evolucoes")
        lines.append("Pokemon: " + "; ".join(pokemon_parts) + ".")
        encounter_parts = []
        if captures:
            encounter_parts.append(f"{captures} captura(s)")
        if battles:
            encounter_parts.append(f"{battles} batalha(s)")
        if observations:
            encounter_parts.append(f"{observations} observacao(oes)")
        lines.append("Encontros: " + (", ".join(encounter_parts) if encounter_parts else "nenhum encontro marcante") + ".")
        if money_delta:
            action = "ganhou" if money_delta > 0 else "gastou/perdeu"
            lines.append(f"Dinheiro: voce {action} {abs(money_delta)} Pokedollar.")
        else:
            lines.append("Dinheiro: sem mudanca.")
        if egg_delta > 0:
            lines.append(f"Ovos: voce recebeu/encontrou {egg_delta} ovo(s).")
        elif egg_delta < 0:
            lines.append(f"Ovos: {abs(egg_delta)} ovo(s) chocaram ou sairam da incubacao.")
        else:
            lines.append("Ovos: sem mudanca.")
        if badge_delta:
            lines.append(f"Ginasios: voce conquistou {badge_delta} insignia(s).")
        else:
            lines.append("Ginasios: nenhuma insignia nova.")
        if notes:
            lines.append("Registro: " + " | ".join(_clean_sentence(note) for note in notes[:4]) + ".")
        else:
            lines.append("Registro: nada marcante mudou alem da passagem do tempo.")
        return "\n".join(lines)

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

    def choose_starter(self, character: Character, starter_name: str | None, career: str | None = None) -> str:
        character.flags["oak_event_done"] = True
        allowed_careers = {"Treinador", "Criador", "Coordenador"}
        if starter_name is None:
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
        pokemon = create_owned_pokemon(species, level=5, origin="presente do Professor Oak")
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
        if career not in self.available_careers_for_character(character):
            return False
        if character.career != career:
            character.career = career
            character.add_history(f"Voce passou a seguir a profissao de {career}.", ["career"])
        return True

    def available_careers_for_character(self, character: Character) -> list[str]:
        base = available_careers(character.age, bool(character.team))
        city = self.get_city_services(character.current_city)
        if not city:
            return base
        return [career for career in city.careers if career in base]

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
            character.attributes.modify({"LUK": 2})
            return True, "Voce se sente mais confiante. LUK +2."
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
        city = self.get_city_services(character.current_city)
        if not city or not city.has_service("pokemon_center"):
            return "Esta cidade nao tem Pokemon Center disponivel."
        for pokemon in character.team:
            pokemon.heal_full(self.pokemon.get(pokemon.species))
            pokemon.status = "healthy"
        character.add_history(f"Sua equipe descansou no Pokemon Center de {character.current_city}.", ["city", "heal"])
        return "Sua equipe foi curada."

    def manual_action_read_about_pokemon(self, character: Character) -> str:
        character.attributes.modify({"POK": 2, "MEN": 1})
        character.add_history(f"Voce estudou sobre Pokemon em {character.current_city}.", ["manual", "study"])
        return "Voce leu sobre Pokemon. POK +2, MEN +1."

    def manual_action_work_city(self, character: Character) -> str:
        city = self.get_city_services(character.current_city)
        if not city:
            return "Nao ha trabalho urbano disponivel aqui."
        income = calculate_money_gain(85, character.attributes)
        if "corporate_work" in city.services:
            income = calculate_money_gain(120, character.attributes, specialty_factor=1.1)
        elif "port" in city.services or "harbor" in city.services:
            income = calculate_money_gain(100, character.attributes, specialty_factor=1.05)
        elif "academy" in city.services or "research_lab" in city.services:
            income = calculate_money_gain(90, character.attributes, specialty_factor=1.0 + character.attributes.POK / 500)
        character.money += income
        if random.random() < 0.15:
            character.health = max(0, character.health - 4)
            suffix = " Foi cansativo e sua saude caiu um pouco."
        else:
            suffix = ""
        character.add_history(f"Voce trabalhou em {character.current_city} e ganhou {income} Pokedollar.", ["manual", "work"])
        return f"Voce ganhou {income} Pokedollar trabalhando na cidade.{suffix}"

    def manual_action_train_team(self, character: Character) -> str:
        active = character.active_pokemon()
        if active is None:
            return "Voce precisa de um Pokemon para treinar."
        xp = 38 + character.attributes.POK // 4 + character.attributes.PHY // 8
        notes = grant_pokemon_xp(active, xp, self.pokemon)
        active.current_health = max(0, active.current_health - random.randint(1, 5))
        if active.health_percent(self.pokemon.get(active.species)) <= 0.25:
            active.status = "tired"
        character.attributes.modify({"PHY": 1, "POK": 1})
        character.add_history(f"Voce treinou com {active.display_name()} em {character.current_city}.", ["manual", "train"])
        extra = f" {' '.join(notes)}" if notes else ""
        return f"{active.display_name()} ganhou {xp} XP. PHY +1, POK +1.{extra}"

    def manual_action_intensive_training(self, character: Character) -> str:
        active = character.active_pokemon()
        if active is None:
            return "Voce precisa de um Pokemon para treino intensivo."
        xp = 80 + character.attributes.POK // 3 + character.attributes.PHY // 5
        if character.career == "Treinador":
            xp += 35
        notes = grant_pokemon_xp(active, xp, self.pokemon)
        health_cost = random.randint(8, 18)
        active.current_health = max(0, active.current_health - health_cost)
        if active.health_percent(self.pokemon.get(active.species)) <= 0.35:
            active.status = "injured"
        character.health = max(0, character.health - 2)
        character.attributes.modify({"PHY": 1, "POK": 2})
        character.add_history(f"Voce fez treino intensivo com {active.display_name()} em {character.current_city}.", ["manual", "intensive_train"])
        extra = f" {' '.join(notes)}" if notes else ""
        return f"Treino intensivo: {active.display_name()} ganhou {xp} XP, mas perdeu {health_cost} HP.{extra}"

    def manual_action_search_for_egg(self, character: Character) -> str:
        location = self.get_location(character.current_city)
        if not location or not location.encounter_enabled:
            return "Este local nao parece ter habitats adequados para procurar ovos."
        chance = 0.08 + character.attributes.POK * 0.0015 + character.attributes.LUK * 0.001
        if character.career == "Criador":
            chance += 0.05
        if random.random() <= min(0.35, chance):
            egg = create_random_egg(
                self.pokemon,
                tier=choose_egg_tier({"C": 65, "I": 25, "R": 8, "RR": 2}),
                origin=f"busca manual em {character.current_city}",
            )
            character.eggs.append(egg)
            character.add_history(f"Voce encontrou um ovo {egg.color} em {character.current_city}.", ["manual", "egg"])
            return f"Voce encontrou um ovo {egg.color} ({egg.rarity_label})."
        character.attributes.modify({"POK": 1})
        return "Voce nao encontrou ovos, mas aprendeu mais sobre o habitat local. POK +1."

    def get_city_gym(self, character: Character) -> dict | None:
        self.ensure_world_generated(character)
        city = self.get_city_services(character.current_city)
        if not city or not city.gym:
            return None
        gym = character.generated_gyms.get(city.gym)
        if not gym:
            return None
        return self._scaled_gym_for_character(gym, character)

    def _scaled_gym_for_character(self, gym: dict, character: Character) -> dict:
        team_levels = sorted((pokemon.level for pokemon in character.team), reverse=True)
        if not team_levels:
            team_levels = sorted((pokemon.level for pokemon in character.box), reverse=True)
        strongest = team_levels[0] if team_levels else 12
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
        for index, member in enumerate(gym["team"]):
            level = min(41, base_level + (index % 4))
            scaled_team.append({**member, "level": level})
        scaled["team"] = scaled_team
        return scaled

    def challenge_city_gym(self, character: Character) -> tuple[bool, list[str]]:
        self.ensure_world_generated(character)
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

        logs = [f"Desafio iniciado contra {gym['leader']} em {gym['city']}."]
        auto_item = self._auto_use_healing_item(character, active)
        if auto_item:
            logs.append(auto_item)
        won_all = True
        for opponent in gym["team"]:
            won, battle_log = simulate_simple_battle(
                character,
                active,
                self.pokemon[active.species],
                f"{gym['leader']} - {opponent['species']}",
                self.pokemon[opponent["species"]],
                opponent["level"],
                important=True,
                species_by_name=self.pokemon,
            )
            logs.extend(battle_log)
            if not won:
                won_all = False
                break

        if won_all:
            character.badges.append(gym["badge"])
            reward = 300 + gym["difficulty"] * 150
            character.money += reward
            character.reputation += 3 + gym["difficulty"]
            character.add_history(f"Voce venceu {gym['leader']} e recebeu {gym['badge']}.", ["gym", "badge"])
            logs.append(f"Vitoria no ginasio! Voce recebeu {gym['badge']} e {reward} Pokedollar.")
        else:
            loss = min(character.money, 80 + gym["difficulty"] * 30)
            character.money -= loss
            character.add_history(f"Voce perdeu para {gym['leader']} no ginasio de {gym['city']}.", ["gym", "loss"])
            logs.append(f"Derrota no ginasio. Voce perdeu {loss} Pokedollar em custos e recuperacao.")
        return won_all, logs

    def apply_event_choice(self, character: Character, event: LifeEvent, choice_index: int) -> str:
        choice = event.choices[choice_index]
        result = apply_choice_result(character, event, choice)
        self._apply_engine_effects(character, result.effects)
        if result.history_entry:
            self._append_to_annual_report(character, result.history_entry)
        return result.history_entry

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
            pokemon = create_owned_pokemon(self.pokemon[species_name], level=level, origin=origin)
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
            level = int(reward.get("level", max(1, min(5, encounter["min_level"]))))
            pokemon = create_owned_pokemon(species, level=level, origin=reward.get("origin", f"evento em {location_name}"))
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
            level = random.randint(encounter["min_level"], encounter["max_level"])
        else:
            possible = [
                species for species in self.pokemon.values()
                if species.can_be_wild and not species.is_legendary and species.rarity in {"common", "uncommon"}
            ]
            species = random.choice(possible)
            level = random.randint(3, max(4, min(12, character.age + 2)))
        character.register_seen(species.name)
        text = f"Um {species.name} selvagem de nivel {level} apareceu perto de {character.current_city}."
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
        city = self.city_services.get(location_name)
        if city and city.encounter_sources:
            sources.extend(city.encounter_sources)
        tables = [self.encounters[source] for source in sources if source in self.encounters]
        if not tables:
            return None
        return random.choice(tables)

    def get_location(self, location_name_or_id: str) -> Location | None:
        location_id = self.location_ids_by_name.get(location_name_or_id, location_name_or_id)
        return self.locations.get(location_id)

    def capture_wild(self, character: Character, species_name: str, level: int) -> tuple[bool, str]:
        ball = self.best_available_ball(character, self.pokemon[species_name])
        success, message, _ = try_capture(character, self.pokemon[species_name], level, ball=ball, item=self.items.get(ball))
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

    def move_to_city(self, character: Character, city_name: str) -> bool:
        if not self.can_travel(character):
            return False
        location = self.get_location(city_name)
        if location and location.kind == "city":
            character.current_city = location.name
            character.add_history(f"Voce chegou a {location.name}.", ["travel"])
            return True
        return False

    def move_to_location(self, character: Character, location_name_or_id: str) -> bool:
        if not self.can_travel(character):
            return False
        location = self.get_location(location_name_or_id)
        if not location:
            return False
        character.current_city = location.name
        character.add_history(f"Voce chegou a {location.name}.", ["travel"])
        return True

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

    # ------------------------------------------------------------------ #
    # VIAGEM                                                               #
    # ------------------------------------------------------------------ #

    def travel_destinations(self, character: Character) -> list[dict]:
        """Retorna todas as cidades acessíveis (exceto a atual). Com mapa, inclui serviços e descrição."""
        if not self.can_travel(character):
            return []
        has_map = bool(character.flags.get("has_kanto_map"))
        destinations = []
        for loc in self.locations.values():
            if loc.kind != "city" or loc.name == character.current_city:
                continue
            entry: dict = {"name": loc.name, "id": loc.location_id}
            if has_map:
                entry["description"] = loc.description
                city_svc = self.city_services.get(loc.name)
                entry["services"] = city_svc.services if city_svc else []
                entry["has_gym"] = bool(city_svc and city_svc.gym) if city_svc else False
            destinations.append(entry)
        return sorted(destinations, key=lambda d: d["name"])

    def travel_to(self, character: Character, city_name: str) -> tuple[bool, str]:
        if not self.can_travel(character):
            return False, "Voce ainda e jovem demais para viajar sozinho."
        location = self.get_location(city_name)
        if not location or location.kind != "city":
            return False, f"{city_name} nao e um destino valido."
        if location.name == character.current_city:
            return False, f"Voce ja esta em {character.current_city}."
        old_city = character.current_city
        character.current_city = location.name
        character.add_history(f"Voce viajou de {old_city} para {location.name}.", ["travel"])
        return True, f"Voce chegou a {location.name}."

    # ------------------------------------------------------------------ #
    # CARREIRA — PROGRESSÃO MANUAL                                         #
    # ------------------------------------------------------------------ #

    def manual_action_focus_career(self, character: Character) -> str:
        """Foca na carreira atual: ganha XP de rank e dinheiro proporcional."""
        if not character.career:
            return "Voce nao tem uma carreira definida. Escolha uma primeiro."
        rank = character.career_rank()
        rank_mult = 1.0 + rank * 0.20
        # Renda da sessão de trabalho dedicada
        base = {"Treinador": 120, "Criador": 100, "Coordenador": 110, "Estudante da academia": 40}.get(character.career, 80)
        income = int(calculate_money_gain(base, character.attributes) * rank_mult)
        character.money += income
        # Sobe atributo relevante
        attr_map = {
            "Treinador": {"PHY": 1, "POK": 1},
            "Criador": {"POK": 1, "MEN": 1},
            "Coordenador": {"LUK": 1, "POK": 1},
            "Estudante da academia": {"MEN": 2},
        }
        character.attributes.modify(attr_map.get(character.career, {}))
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
                "prize_pool": cfg["base_prize"] * cfg["rounds"],
                "rounds": cfg["rounds"],
                "min_badges": cfg.get("min_badges", 0),
            })
        return result

    def enter_tournament(self, character: Character, kind: str) -> tuple[bool, "TournamentResult | None", str]:
        ok, reason = can_enter_tournament(character, kind)
        if not ok:
            return False, None, reason
        cfg = TOURNAMENT_KINDS[kind]
        character.money = max(0, character.money - cfg["entry_fee"])
        opponents = generate_tournament(character, self.pokemon, kind)
        result = run_tournament(character, opponents, self.pokemon, kind)
        if result.prize_money > 0:
            character.money += result.prize_money
        character.reputation += result.rounds_won * (2 if kind == "regional" else 1)
        if result.champion:
            summary = f"Voce venceu o {cfg['label']}! Premio: {result.prize_money} Pokedollar."
            character.add_history(summary, ["tournament", "win"])
        else:
            summary = f"Voce chegou ate a rodada {result.rounds_won + 1} no {cfg['label']}."
            character.add_history(summary, ["tournament"])
        return True, result, summary


# ------------------------------------------------------------------ #
# Helpers de módulo                                                    #
# ------------------------------------------------------------------ #

def _is_history_worthy(note: str) -> bool:
    """Filtra notas de progressão que realmente merecem entrar no histórico."""
    keywords = (
        "subiu para o nivel", "evoluiu", "aprendeu", "conseguiu", "venceu",
        "badge", "insignia", "torneio", "rank", "ovo chocou",
    )
    lower = note.lower()
    return any(kw in lower for kw in keywords)


def _clean_sentence(text: str) -> str:
    """Normaliza uma frase para o relatório anual."""
    text = text.strip().rstrip(".")
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    return text
