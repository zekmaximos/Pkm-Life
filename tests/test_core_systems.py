import unittest
import json
from pathlib import Path
from unittest.mock import patch

from game.attributes import PlayerAttributes, generate_initial_attributes
from game.battle import resolve_auto_battle
from game.capture import attempt_capture, calculate_capture_chance
from game.economy import calculate_money_gain
from game.inventory import Item
from game.pokemon import PokemonSpecies, assign_evolution_stages, create_owned_pokemon, coherent_pokemon_level, minimum_level_for_species
from game.character import Character
from game.careers import (
    CAREER_BALL_CRAFTER,
    CAREER_BERRY_COLLECTOR,
    CAREER_BREEDER,
    CAREER_COORDINATOR,
    CAREER_CRIMINAL,
    CAREER_EXPLORER,
    CAREER_FARM_CARETAKER,
    CAREER_MERCHANT,
    CAREER_RESEARCHER,
    CAREER_SCIENTIST,
    CAREER_STUDENT,
    CAREER_TRAINER,
    CAREERS,
    available_careers,
    pokemon_work_bonus,
)
from game.progression import progress_year
from game.progression import grant_pokemon_xp
from game.engine import GameEngine
from game.events import LifeEvent, event_occurrence_chance, event_weight, valid_events
from game.eggs import create_random_egg, progress_eggs
from game.year_simulation import apply_activity_results, simulate_year_activities
from game.tournaments import can_enter_tournament, generate_tournament
from game.series_battle import SeriesOpponent, estimate_series_chance
from game.mortality import mortality_chance
from game.prison import sentence_for_crime
from game.academy import apply_focus_progress, capture_bonus_for, focus_label


class CoreSystemsTest(unittest.TestCase):
    def test_player_attributes_are_generated_inside_limits(self) -> None:
        attrs = generate_initial_attributes()
        for value in attrs.to_dict().values():
            self.assertGreaterEqual(value, 0)
            self.assertLessEqual(value, 100)

    def test_pokemon_instance_stats_are_varied_inside_limits(self) -> None:
        species = PokemonSpecies(
            pokedex_id=25,
            name="Pikachu",
            types=["Electric"],
            rarity="uncommon",
            habitats=["Viridian City"],
            evolution=None,
            evolution_level=None,
            base_combat=60,
            base_beauty=55,
            base_healthy=45,
            base_occult=35,
            can_be_wild=True,
            is_legendary=False,
            is_starter=False,
            ability="Static",
        )
        pokemon = create_owned_pokemon(species, level=8)
        for value in (pokemon.combat, pokemon.beauty, pokemon.healthy, pokemon.occult, pokemon.level):
            self.assertGreaterEqual(value, 1)
            self.assertLessEqual(value, 100)

    def test_capture_chance_and_attempt_capture_return_expected_shape(self) -> None:
        attrs = PlayerAttributes(PHY=50, MEN=50, POK=70, LUK=60)
        chance = calculate_capture_chance("rare", 40, attrs, ball_bonus=12, pokemon_level=12, evolution_stage=1)
        self.assertGreaterEqual(chance, 1)
        self.assertLessEqual(chance, 95)
        result = attempt_capture("rare", "Eevee", 40, attrs, ball_bonus=12, pokemon_level=12, evolution_stage=1)
        self.assertGreaterEqual(result.chance, 1)
        self.assertLessEqual(result.chance, 95)
        self.assertIsInstance(result.success, bool)

    def test_auto_battle_returns_scores_chance_and_winner(self) -> None:
        attrs = PlayerAttributes(PHY=50, MEN=65, POK=70, LUK=55)
        bulbasaur = create_owned_pokemon(
            PokemonSpecies(1, "Bulbasaur", ["Grass", "Poison"], "rare", [], None, None, 55, 50, 55, 25, False, False, True),
            level=10,
        )
        geodude = create_owned_pokemon(
            PokemonSpecies(74, "Geodude", ["Rock", "Ground"], "common", [], None, None, 60, 25, 75, 10, True, False, False),
            level=9,
        )
        result = resolve_auto_battle(bulbasaur, geodude, attrs)
        self.assertGreater(result.player_score, 0)
        self.assertGreater(result.enemy_score, 0)
        self.assertGreaterEqual(result.win_chance, 0.05)
        self.assertLessEqual(result.win_chance, 0.95)
        self.assertGreaterEqual(result.xp_gain, 6)
        self.assertIn(result.winner, {bulbasaur.display_name(), geodude.display_name()})

    def test_money_gain_is_positive(self) -> None:
        attrs = PlayerAttributes(PHY=50, MEN=70, POK=40, LUK=60)
        self.assertGreater(calculate_money_gain(100, attrs), 0)

    def test_year_progression_moves_career_money_and_pokemon_xp(self) -> None:
        character = Character("Blue")
        character.age = 10
        character.career = CAREER_TRAINER
        species = PokemonSpecies(16, "Pidgey", ["Normal", "Flying"], "common", [], None, None, 45, 40, 40, 10, True, False, False)
        pokemon = create_owned_pokemon(species, level=5)
        character.add_pokemon(pokemon)
        money_before = character.money
        xp_before = pokemon.experience
        notes = progress_year(character)
        self.assertGreaterEqual(character.money, money_before)
        self.assertGreaterEqual(pokemon.experience + pokemon.level * 100, xp_before + 500)
        self.assertTrue(notes)

    def test_available_careers_are_age_and_team_aware(self) -> None:
        self.assertEqual(available_careers(0, False), [])
        self.assertEqual(available_careers(7, False), ["Estudante da academia"])
        self.assertIn(CAREER_TRAINER, available_careers(10, True))
        teen_careers = available_careers(16, False)
        self.assertIn(CAREER_BERRY_COLLECTOR, teen_careers)
        self.assertIn(CAREER_BALL_CRAFTER, teen_careers)
        self.assertIn(CAREER_FARM_CARETAKER, teen_careers)
        self.assertIn(CAREER_MERCHANT, teen_careers)
        adult_careers = available_careers(18, False)
        self.assertIn(CAREER_RESEARCHER, adult_careers)
        self.assertIn(CAREER_EXPLORER, adult_careers)
        self.assertIn(CAREER_SCIENTIST, adult_careers)

    def test_capture_penalizes_level_and_evolution_stage(self) -> None:
        attrs = PlayerAttributes(PHY=50, MEN=50, POK=50, LUK=50)
        easy = calculate_capture_chance("common", 50, attrs, ball_bonus=0, pokemon_level=3, evolution_stage=1)
        hard = calculate_capture_chance("common", 50, attrs, ball_bonus=0, pokemon_level=45, evolution_stage=3)
        self.assertLess(hard, easy)

    def test_item_capture_bonus_can_prefer_types_and_stage(self) -> None:
        item = Item(
            item_id="net_ball",
            name="Net Ball",
            item_type="capture",
            capture_bonus=8,
            preferred_types=("Water", "Bug"),
            max_evolution_stage=1,
        )
        self.assertGreater(item.capture_bonus_for("common", ["Water"], 1), item.capture_bonus_for("rare", ["Fire"], 3))

    def test_pokemon_evolves_when_reaching_evolution_level(self) -> None:
        bulbasaur = PokemonSpecies(1, "Bulbasaur", ["Grass", "Poison"], "rare", [], "Ivysaur", 16, 55, 50, 55, 25, False, False, True)
        ivysaur = PokemonSpecies(2, "Ivysaur", ["Grass", "Poison"], "rare", [], None, None, 65, 55, 65, 30, False, False, False)
        species = {"Bulbasaur": bulbasaur, "Ivysaur": ivysaur}
        assign_evolution_stages(species)
        pokemon = create_owned_pokemon(bulbasaur, level=15)
        notes = grant_pokemon_xp(pokemon, 100, species)
        self.assertEqual(pokemon.species, "Ivysaur")
        self.assertTrue(any("evoluiu" in note for note in notes))

    def test_evolved_pokemon_level_is_coherent_with_evolution(self) -> None:
        engine = GameEngine()
        pidgeotto = engine.pokemon["Pidgeotto"]
        pidgeot = engine.pokemon["Pidgeot"]

        self.assertEqual(minimum_level_for_species(pidgeotto, engine.pokemon), 18)
        self.assertEqual(minimum_level_for_species(pidgeot, engine.pokemon), 36)
        self.assertEqual(coherent_pokemon_level(pidgeotto, 9, engine.pokemon), 18)
        self.assertEqual(create_owned_pokemon(pidgeotto, level=9, species_by_name=engine.pokemon).level, 18)

    def test_kanto_database_has_151_pokemon_with_game_stats(self) -> None:
        data = json.loads(Path("data/pokemon_kanto.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data), 151)
        self.assertEqual({row["pokedex_id"] for row in data}, set(range(1, 152)))
        for row in data:
            for key in ("base_combat", "base_beauty", "base_healthy", "base_occult"):
                self.assertGreaterEqual(row[key], 1)
                self.assertLessEqual(row[key], 100)
            self.assertTrue(row["types"])
            self.assertTrue(row["ability"])

    def test_encounter_database_references_valid_pokemon(self) -> None:
        pokemon = {
            row["name"]
            for row in json.loads(Path("data/pokemon_kanto.json").read_text(encoding="utf-8"))
        }
        location_ids = {
            row["id"]
            for row in json.loads(Path("data/locations_kanto.json").read_text(encoding="utf-8"))
        }
        encounter_tables = json.loads(Path("data/encounters_kanto.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(encounter_tables), 20)
        for encounter_table in encounter_tables:
            self.assertIn(encounter_table["location_id"], location_ids)
            self.assertTrue(encounter_table["encounters"])
            for encounter in encounter_table["encounters"]:
                self.assertIn(encounter["species"], pokemon)
                self.assertGreaterEqual(encounter["min_level"], 1)
                self.assertGreaterEqual(encounter["max_level"], encounter["min_level"])

    def test_kanto_locations_include_cities_and_routes(self) -> None:
        locations = json.loads(Path("data/locations_kanto.json").read_text(encoding="utf-8"))
        by_name = {location["name"]: location for location in locations}
        for name in ("Pallet Town", "Viridian City", "Cinnabar Island", "Indigo Plateau"):
            self.assertEqual(by_name[name]["kind"], "city")
        for route_number in range(1, 26):
            self.assertEqual(by_name[f"Route {route_number}"]["kind"], "route")
        self.assertTrue(by_name["Route 1"]["encounter_enabled"])

    def test_city_services_reference_valid_cities_items_and_gyms(self) -> None:
        locations = json.loads(Path("data/locations_kanto.json").read_text(encoding="utf-8"))
        city_names = {location["name"] for location in locations if location["kind"] == "city"}
        items = {item["name"] for item in json.loads(Path("data/items.json").read_text(encoding="utf-8"))}
        gyms = {gym["id"] for gym in json.loads(Path("data/gyms_kanto.json").read_text(encoding="utf-8"))}
        services = json.loads(Path("data/city_services_kanto.json").read_text(encoding="utf-8"))
        self.assertEqual({city["city"] for city in services}, city_names)
        for city in services:
            self.assertIn(city["city"], city_names)
            self.assertTrue(city["services"])
            for item in city.get("shop_inventory", []):
                self.assertIn(item, items)
            for career in city.get("careers", []):
                self.assertIn(career, CAREERS)
            if "gym" in city:
                self.assertIn(city["gym"], gyms)
            self.assertIn("work", city)
            self.assertIsInstance(city["work"].get("name"), str)
            self.assertGreater(city["work"].get("base_income", 0), 0)
            self.assertTrue(city["work"].get("primary_attributes"))

    def test_journey_events_have_40_unique_varied_entries(self) -> None:
        events = json.loads(Path("data/events_journey.json").read_text(encoding="utf-8"))
        event_ids = [event["id"] for event in events]
        tags = {tag for event in events for tag in event.get("tags", [])}
        careers = {
            event.get("conditions", {}).get("career")
            for event in events
            if event.get("conditions", {}).get("career")
        }
        self.assertGreaterEqual(len(events), 40)
        self.assertEqual(len(event_ids), len(set(event_ids)))
        self.assertTrue({"battle", "care", "contest", "academy", "risk", "rare", "city"}.issubset(tags))
        self.assertTrue({
            "Treinador",
            "Criador",
            "Coordenador",
            "Estudante da academia",
            "Coletor de Berrys",
            "Construtor de Pokebolas",
            "Cuidador de Fazenda",
            "Construtor",
            "Comerciante",
        }.issubset(careers))

    def test_city_shop_and_healing_actions_work(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Green")
        character.age = 5
        character.money = 500
        success, message = engine.buy_item(character, "Poke Ball", 1)
        self.assertTrue(success, message)
        self.assertGreaterEqual(character.inventory.get("Poke Ball", 0), 6)
        pokemon_species = engine.pokemon["Pidgey"]
        pokemon = create_owned_pokemon(pokemon_species, level=5)
        pokemon.current_health = 1
        pokemon.status = "injured"
        character.add_pokemon(pokemon)
        character.age = 10
        character.inventory["Mapa de Kanto"] = 1
        engine.move_to_city(character, "Viridian City")
        self.assertEqual(engine.heal_team_in_city(character), "Sua equipe foi curada.")
        self.assertEqual(character.team[0].current_health, character.team[0].max_health(engine.pokemon[character.team[0].species]))
        self.assertEqual(character.team[0].status, "healthy")

    def test_city_gym_lookup_uses_current_city(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Green")
        character.age = 10
        character.inventory["Mapa de Kanto"] = 1
        engine.move_to_city(character, "Pewter City")
        gym = engine.get_city_gym(character)
        self.assertIsNotNone(gym)
        self.assertEqual(gym["main_type"], "Rock")

    def test_generated_gyms_have_random_leaders_and_type_valid_teams(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Leaf")
        self.assertEqual(len(character.generated_gyms), 12)
        leaders = [gym["leader"] for gym in character.generated_gyms.values()]
        self.assertEqual(len(leaders), len(set(leaders)))
        official = [gym for gym in character.generated_gyms.values() if gym["official"]]
        created = [gym for gym in character.generated_gyms.values() if not gym["official"]]
        self.assertEqual(len(official), 8)
        self.assertEqual(len(created), 4)
        for gym in character.generated_gyms.values():
            self.assertGreaterEqual(len(gym["team"]), 3)
            self.assertLessEqual(len(gym["team"]), 6)
            self.assertGreaterEqual(gym["recommended_level"], 12)
            self.assertLessEqual(gym["recommended_level"], 38)
            self.assertEqual(gym["level_range"][1], gym["level_range"][0] + 3)
            very_rare_count = 0
            for member in gym["team"]:
                self.assertIn(gym["main_type"], engine.pokemon[member["species"]].types)
                if engine.pokemon[member["species"]].rarity == "very_rare":
                    very_rare_count += 1
                if gym["difficulty"] <= 2:
                    self.assertLessEqual(engine.pokemon[member["species"]].evolution_stage, 1)
                    self.assertNotIn(engine.pokemon[member["species"]].rarity, {"very_rare", "legendary", "mythic"})
                self.assertGreaterEqual(member["level"], 12)
                self.assertLessEqual(member["level"], 41)
                self.assertGreaterEqual(member["level"], gym["level_range"][0])
                self.assertLessEqual(member["level"], gym["level_range"][1])
            self.assertLessEqual(very_rare_count, 1)

    def test_city_gym_scales_to_strongest_player_pokemon(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Leaf")
        character.age = 10
        character.add_pokemon(create_owned_pokemon(engine.pokemon["Pidgey"], level=26))
        character.inventory["Mapa de Kanto"] = 1
        engine.move_to_city(character, "Pewter City")
        gym = engine.get_city_gym(character)
        self.assertEqual(gym["recommended_level"], 25)
        self.assertEqual(gym["level_range"], [25, 28])
        for member in gym["team"]:
            self.assertGreaterEqual(member["level"], 25)
            self.assertLessEqual(member["level"], 28)

    def test_city_gym_scales_by_top_three_average_not_single_outlier(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Leaf")
        character.age = 10
        character.add_pokemon(create_owned_pokemon(engine.pokemon["Pidgey"], level=50))
        character.add_pokemon(create_owned_pokemon(engine.pokemon["Rattata"], level=12))
        character.add_pokemon(create_owned_pokemon(engine.pokemon["Caterpie"], level=12))
        character.inventory["Mapa de Kanto"] = 1
        engine.move_to_city(character, "Pewter City")
        gym = engine.get_city_gym(character)
        self.assertLess(gym["recommended_level"], 41)
        self.assertEqual(gym["recommended_level"], 24)

    def test_generated_gyms_are_saved_with_character(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Leaf")
        saved = character.to_dict()
        loaded = Character.from_dict(saved)
        self.assertEqual(character.generated_gyms, loaded.generated_gyms)

    def test_event_occurrence_chance_responds_to_character_state(self) -> None:
        low = Character("Low")
        low.attributes.LUK = 10
        low.attributes.POK = 10
        high = Character("High")
        high.attributes.LUK = 90
        high.attributes.POK = 90
        high.inventory["Great Ball"] = 3
        high.career = CAREER_TRAINER
        self.assertGreater(event_occurrence_chance(high, ["battle"]), event_occurrence_chance(low, []))

    def test_event_conditions_can_require_items_and_pokemon_state(self) -> None:
        event = LifeEvent(
            event_id="test_capture_event",
            title="Test",
            text="Test",
            min_age=1,
            max_age=99,
            phase=None,
            region=None,
            city=None,
            choices=[],
            conditions={"requires_no_pokemon": True, "min_items": {"Poke Ball": 1}},
        )
        character = Character("Case")
        character.age = 1
        self.assertIn(event, valid_events(character, [event]))
        character.inventory["Poke Ball"] = 0
        self.assertNotIn(event, valid_events(character, [event]))

    def test_event_weight_responds_to_city_focus_career_and_items(self) -> None:
        event = LifeEvent(
            event_id="test_battle",
            title="Test",
            text="Test",
            min_age=1,
            max_age=99,
            phase=None,
            region=None,
            city=None,
            choices=[],
            tags=["battle", "capture"],
            base_weight=1.0,
        )
        character = Character("Case")
        baseline = event_weight(character, event, [])
        character.career = CAREER_TRAINER
        character.inventory["Poke Ball"] = 2
        boosted = event_weight(character, event, ["battle"])
        self.assertGreater(boosted, baseline)

    def test_oak_event_only_when_character_has_no_pokemon(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 9
        character.add_pokemon(create_owned_pokemon(engine.pokemon["Pidgey"], level=3))
        event = engine.advance_year(character)
        self.assertNotEqual(event.event_id if event else None, "oak_starter")

    def test_oak_event_has_priority_over_age_10_automatic_encounter(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 9
        character.inventory["Poke Ball"] = 5
        character.attributes.POK = 90
        character.attributes.LUK = 90
        with patch("game.engine.random.random", return_value=0.0):
            event = engine.advance_year(character)
        self.assertEqual(event.event_id if event else None, "oak_starter")
        self.assertFalse(character.team)
        self.assertIn("aos 10 anos", character.flags["last_year_report"])

    def test_oak_starter_requires_pokemon_career_choice(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        message = engine.choose_starter(character, "Bulbasaur", None)
        self.assertFalse(character.team)
        self.assertIn("esperar", message)
        character = engine.create_character("Case2")
        message = engine.choose_starter(character, "Bulbasaur", "Criador")
        self.assertTrue(character.team)
        self.assertEqual(character.career, "Criador")
        self.assertIn("Bulbasaur", message)

    def test_oak_pokemon_options_match_selected_profession(self) -> None:
        engine = GameEngine()
        self.assertEqual(engine.oak_pokemon_options_for_career("Treinador"), ["Bulbasaur", "Charmander", "Squirtle"])
        coordinator_options = engine.oak_pokemon_options_for_career("Coordenador")
        breeder_options = engine.oak_pokemon_options_for_career("Criador")
        self.assertEqual(len(coordinator_options), 2)
        self.assertEqual(len(breeder_options), 3)
        for name in coordinator_options + breeder_options:
            species = engine.pokemon[name]
            self.assertEqual(species.rarity, "common")
            self.assertFalse(species.is_starter)

    def test_random_area_pokemon_event_effect_adds_valid_pokemon(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        event = LifeEvent(
            event_id="area_friend",
            title="Area",
            text="Area",
            min_age=1,
            max_age=99,
            phase=None,
            region=None,
            city=None,
            choices=[],
        )
        choice = type("Choice", (), {"effects": {"random_area_pokemon": [{"location": "Pallet Town", "level": 3}]}, "history_entry": "", "chance": None, "failure_effects": None, "failure_history_entry": None})()
        engine._apply_engine_effects(character, choice.effects)
        self.assertTrue(character.team)
        self.assertIn(character.team[0].species, engine.pokemon)

    def test_egg_can_be_saved_and_hatched(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        egg = create_random_egg(engine.pokemon, tier="C", origin="teste", type_hint="Normal")
        egg.years_to_hatch = 1
        character.eggs.append(egg)
        loaded = Character.from_dict(character.to_dict())
        self.assertEqual(len(loaded.eggs), 1)
        notes = progress_eggs(loaded, engine.pokemon)
        self.assertFalse(loaded.eggs)
        self.assertTrue(loaded.team)
        self.assertTrue(any("chocou" in note for note in notes))

    def test_travel_is_blocked_before_age_10(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        self.assertFalse(engine.move_to_city(character, "Viridian City"))
        character.age = 10
        character.inventory["Mapa de Kanto"] = 1
        self.assertTrue(engine.move_to_city(character, "Viridian City"))

    def test_buy_common_egg_adds_egg_not_inventory_stack(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 5
        character.money = 2000
        success, message = engine.buy_item(character, "Common Egg", 1)
        self.assertTrue(success, message)
        self.assertEqual(len(character.eggs), 1)
        self.assertEqual(character.eggs[0].years_to_hatch, 1)
        self.assertNotIn("Common Egg", character.inventory)

    def test_active_pokemon_selection_changes_battle_leader(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.add_pokemon(create_owned_pokemon(engine.pokemon["Pidgey"], level=5))
        character.add_pokemon(create_owned_pokemon(engine.pokemon["Poliwag"], level=5))
        self.assertEqual(character.active_pokemon().species, "Pidgey")
        self.assertTrue(engine.set_active_pokemon(character, 1))
        self.assertEqual(character.active_pokemon().species, "Poliwag")

    def test_manual_actions_have_effects(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 10
        character.inventory["Mapa de Kanto"] = 1
        engine.move_to_city(character, "Viridian City")
        pok_before = character.attributes.POK
        self.assertIn("POK", engine.manual_action_read_about_pokemon(character))
        self.assertGreater(character.attributes.POK, pok_before)
        self.assertIn("ja estudou", engine.manual_action_read_about_pokemon(character))
        money_before = character.money
        work_message = engine.manual_action_work_city(character)
        self.assertIn("Guia de rota", work_message)
        self.assertGreaterEqual(character.money, money_before)
        self.assertIn("ja trabalhou", engine.manual_action_work_city(character))
        character.add_pokemon(create_owned_pokemon(engine.pokemon["Pidgey"], level=5))
        xp_before = character.active_pokemon().experience
        engine.manual_action_train_team(character)
        self.assertGreaterEqual(character.active_pokemon().experience + character.active_pokemon().level * 100, xp_before + 500)
        self.assertIn("ja treinou", engine.manual_action_intensive_training(character))
        engine.advance_time(character, 3)
        intensive_before = character.active_pokemon().experience + character.active_pokemon().level * 100
        self.assertIn("Treino intensivo", engine.manual_action_intensive_training(character))
        self.assertGreater(character.active_pokemon().experience + character.active_pokemon().level * 100, intensive_before)

    def test_city_specific_work_scales_with_economy_and_attributes(self) -> None:
        engine = GameEngine()
        pallet = engine.create_character("PalletWorker")
        pallet.age = 5
        pallet.attributes = PlayerAttributes(PHY=25, MEN=25, POK=25, LUK=25)
        pallet_money_before = pallet.money
        pallet_message = engine.manual_action_work_city(pallet)
        pallet_income = pallet.money - pallet_money_before
        self.assertIn("Laboratorio Oak", pallet_message)

        saffron = engine.create_character("SaffronWorker")
        saffron.age = 10
        saffron.attributes = PlayerAttributes(PHY=80, MEN=85, POK=85, LUK=75)
        saffron.inventory["Mapa de Kanto"] = 1
        engine.move_to_city(saffron, "Saffron City")
        saffron_money_before = saffron.money
        saffron_message = engine.manual_action_work_city(saffron)
        saffron_income = saffron.money - saffron_money_before
        self.assertIn("Silph", saffron_message)
        self.assertGreater(saffron_income, pallet_income)

    def test_period_actions_reset_only_after_time_advance(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Period")
        character.age = 10
        character.inventory["Mapa de Kanto"] = 1
        engine.move_to_city(character, "Viridian City")
        self.assertIn("POK", engine.manual_action_read_about_pokemon(character))
        self.assertIn("ja estudou", engine.manual_action_read_about_pokemon(character))
        self.assertIn("Pokedollar", engine.manual_action_work_city(character))
        self.assertIn("ja trabalhou", engine.manual_action_work_city(character))
        character.career = CAREER_TRAINER
        self.assertIn("Dedicacao", engine.manual_action_focus_career(character))
        self.assertIn("ja focou", engine.manual_action_focus_career(character))

        engine.advance_time(character, 3)

        self.assertIn("POK", engine.manual_action_read_about_pokemon(character))
        self.assertIn("Pokedollar", engine.manual_action_work_city(character))
        self.assertIn("Dedicacao", engine.manual_action_focus_career(character))

    def test_early_childhood_blocks_manual_city_and_journey_actions(self) -> None:
        engine = GameEngine()
        baby = engine.create_character("Baby")
        baby.money = 5000
        baby.add_pokemon(create_owned_pokemon(engine.pokemon["Pidgey"], level=3))
        self.assertEqual(engine.available_careers_for_character(baby), [])
        self.assertIn("muito novo", engine.manual_action_read_about_pokemon(baby))
        self.assertIn("muito novo", engine.manual_action_work_city(baby))
        self.assertIn("muito novo", engine.manual_action_train_team(baby))
        self.assertIn("muito novo", engine.manual_action_focus_career(baby))
        self.assertIn("muito novo", engine.buy_item(baby, "Poke Ball", 1)[1])
        self.assertIn("muito novo", engine.use_item(baby, "Potion")[1])
        self.assertIn("depende de adultos", engine.heal_team_in_city(baby))
        self.assertIn("10 anos", engine.manual_action_intensive_training(baby))
        self.assertIn("10 anos", engine.manual_action_search_for_egg(baby))
        self.assertFalse(engine.black_market_available(baby))

        child = engine.create_character("Child")
        child.age = 5
        child.career = CAREER_STUDENT
        self.assertIn("POK", engine.manual_action_read_about_pokemon(child))
        self.assertIn("Pokedollar", engine.manual_action_work_city(child))
        child.add_pokemon(create_owned_pokemon(engine.pokemon["Pidgey"], level=3))
        self.assertIn("Treino concluido", engine.manual_action_train_team(child))
        self.assertIn("10 anos", engine.manual_action_intensive_training(child))

    def test_manual_egg_search_is_rare_but_breeder_has_edge(self) -> None:
        engine = GameEngine()
        regular = engine.create_character("Regular")
        regular.age = 10
        regular.current_city = "route_1"
        regular.attributes = PlayerAttributes(PHY=50, MEN=50, POK=100, LUK=100)
        with patch("game.engine.random.random", return_value=0.18):
            self.assertIn("nao encontrou ovos", engine.manual_action_search_for_egg(regular))
        self.assertFalse(regular.eggs)

        breeder = engine.create_character("Breeder")
        breeder.age = 10
        breeder.current_city = "route_1"
        breeder.career = CAREER_BREEDER
        breeder.attributes = PlayerAttributes(PHY=50, MEN=50, POK=100, LUK=100)
        with patch("game.engine.random.random", return_value=0.18):
            self.assertIn("encontrou um ovo", engine.manual_action_search_for_egg(breeder))
        self.assertEqual(len(breeder.eggs), 1)

    def test_egg_event_probabilities_stay_rare(self) -> None:
        childhood = json.loads(Path("data/events_childhood.json").read_text(encoding="utf-8"))
        journey = json.loads(Path("data/events_journey.json").read_text(encoding="utf-8"))
        by_id = {event["id"]: event for event in childhood + journey}
        self.assertLessEqual(by_id["warm_common_egg"]["base_weight"], 0.12)
        self.assertLessEqual(by_id["warm_common_egg"]["choices"][0]["chance"], 0.45)
        self.assertLessEqual(by_id["academy_colored_egg"]["base_weight"], 0.06)
        self.assertLessEqual(by_id["shimmering_super_rare_egg"]["base_weight"], 0.018)
        self.assertLessEqual(by_id["habitat_nest_discovery"]["choices"][0]["chance"], 0.22)
        self.assertLessEqual(by_id["rare_moonlit_egg"]["choices"][0]["chance"], 0.18)

    def test_use_items_apply_simple_effects(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 5
        pokemon = create_owned_pokemon(engine.pokemon["Pidgey"], level=5)
        pokemon.current_health = 1
        character.add_pokemon(pokemon)
        character.inventory["Potion"] = 1
        success, message = engine.use_item(character, "Potion")
        self.assertTrue(success, message)
        self.assertGreater(character.active_pokemon().current_health, 1)
        character.inventory["Protein"] = 1
        combat_before = character.active_pokemon().combat
        success, _ = engine.use_item(character, "Protein")
        self.assertTrue(success)
        self.assertGreater(character.active_pokemon().combat, combat_before)
        character.inventory["Lucky Charm"] = 1
        luck_before = character.attributes.LUK
        success, _ = engine.use_item(character, "Lucky Charm")
        self.assertTrue(success)
        self.assertGreater(character.attributes.LUK, luck_before)

    def test_team_overflow_goes_to_box_and_old_reserve_saves_load(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        for _ in range(6):
            self.assertEqual(character.add_pokemon(create_owned_pokemon(engine.pokemon["Pidgey"], level=5)), "team")
        self.assertEqual(character.add_pokemon(create_owned_pokemon(engine.pokemon["Rattata"], level=5)), "box")
        self.assertEqual(len(character.team), 6)
        self.assertEqual(len(character.box), 1)

        saved = character.to_dict()
        legacy_save = dict(saved)
        legacy_save.pop("box")
        legacy_save["reserve"] = saved["box"]
        loaded = Character.from_dict(legacy_save)
        self.assertEqual(len(loaded.box), 1)
        self.assertEqual(loaded.box[0].species, "Rattata")

    def test_box_transfer_actions_keep_active_team_valid(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.add_pokemon(create_owned_pokemon(engine.pokemon["Pidgey"], level=5))
        character.add_pokemon(create_owned_pokemon(engine.pokemon["Rattata"], level=5))
        success, message = engine.move_team_to_box(character, 1)
        self.assertTrue(success, message)
        self.assertEqual(len(character.team), 1)
        self.assertEqual(len(character.box), 1)
        self.assertEqual(character.active_pokemon().species, "Pidgey")

        success, message = engine.move_box_to_team(character, 0)
        self.assertTrue(success, message)
        self.assertEqual(len(character.team), 2)
        self.assertFalse(character.team[1].active)

    def test_automatic_year_encounter_can_resolve_without_manual_input(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 10
        character.career = CAREER_TRAINER
        character.inventory["Poke Ball"] = 5
        character.attributes.POK = 90
        character.attributes.LUK = 90
        character.add_pokemon(create_owned_pokemon(engine.pokemon["Pidgey"], level=5))
        with patch("game.engine.random.random", return_value=0.0):
            notes = engine.resolve_automatic_year_encounter(character)
        self.assertTrue(notes)
        self.assertIn("Durante o ano", notes[0])
        self.assertTrue(any(word in " ".join(notes) for word in ("Captura automatica", "Batalha automatica", "observou")))

    def test_encounter_without_pokemon_reduces_health_without_game_over(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 10
        character.health = 4
        character.current_city = "route_1"
        character.team = []
        with patch("game.engine.random.randint", return_value=7):
            success, message = engine.manual_action_hunt_wild_pokemon(character)
        self.assertFalse(success)
        self.assertEqual(character.health, 1)
        self.assertIn("Sem Pokemon", message)

    def test_annual_capture_adds_owned_pokemon_to_team_or_box(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 10
        character.career = CAREER_TRAINER
        character.inventory = {"Master Ball": 1}
        before_owned = len(character.team) + len(character.box)
        with patch("game.year_simulation.random.choices", return_value=["capture"]), patch("game.capture.random.random", return_value=0.0):
            results = simulate_year_activities(character, engine.pokemon)
        _, report = apply_activity_results(character, results, engine.pokemon)
        self.assertGreater(len(character.team) + len(character.box), before_owned)
        self.assertTrue(character.pokedex_caught)
        self.assertGreaterEqual(len(report["captures"]), 1)

    def test_annual_capture_does_not_create_underleveled_evolved_pokemon(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 10
        character.career = CAREER_TRAINER
        character.inventory = {"Master Ball": 1}
        with patch("game.year_simulation._pick_activity", return_value="capture"), patch("game.year_simulation.random.choice", return_value=engine.pokemon["Pidgeotto"]), patch("game.year_simulation.random.randint", return_value=9), patch("game.year_simulation._capture_note", return_value="captura"), patch("game.year_simulation._sim_career_mission", return_value=None), patch("game.capture.random.random", return_value=0.0):
            result = simulate_year_activities(character, engine.pokemon, months=3)[0]
        self.assertEqual(result.pokemon_name, "Pidgeotto")
        self.assertEqual(result.pokemon_level, 18)
        self.assertEqual(character.team[0].level, 18)

    def test_grid_travel_stores_canonical_location_id(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 10
        ok, message = engine.travel_to(character, "C2")
        self.assertTrue(ok, message)
        self.assertEqual(character.current_city, "route_1")
        self.assertEqual(engine.get_location(character.current_city).name, "Route 1")
        species, _, text = engine.wild_encounter(character)
        self.assertIn(species.name, engine.pokemon)
        self.assertIn("Rota 1", text)

    def test_repel_reduces_automatic_year_encounter_chance(self) -> None:
        from game.auto_year import automatic_encounter_chance

        character = Character("Case")
        character.age = 10
        baseline = automatic_encounter_chance(character, True)
        character.flags["repel_years"] = 1
        reduced = automatic_encounter_chance(character, True)
        self.assertLess(reduced, baseline)

    def test_auto_healing_item_is_used_before_wild_battle(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 10
        pokemon = create_owned_pokemon(engine.pokemon["Pidgey"], level=12)
        pokemon.current_health = 1
        pokemon.status = "injured"
        character.add_pokemon(pokemon)
        character.inventory["Potion"] = 1
        message = engine._auto_use_healing_item(character, character.active_pokemon())
        self.assertEqual(character.inventory.get("Potion", 0), 0)
        self.assertIsNotNone(message)
        self.assertTrue(message.startswith("Uso automatico:"))
        self.assertGreater(character.active_pokemon().current_health, 1)

    def test_pokemon_max_health_is_separate_from_healthy_stat(self) -> None:
        engine = GameEngine()
        pokemon = create_owned_pokemon(engine.pokemon["Rattata"], level=2)
        self.assertGreaterEqual(pokemon.max_health(engine.pokemon[pokemon.species]), 20)
        self.assertNotEqual(pokemon.max_health(engine.pokemon[pokemon.species]), pokemon.healthy)
        pokemon.current_health = 1
        pokemon.heal_full(engine.pokemon[pokemon.species])
        self.assertEqual(pokemon.current_health, pokemon.max_health(engine.pokemon[pokemon.species]))

    def test_annual_report_is_recorded_after_year_progression(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 10
        character.career = CAREER_TRAINER
        character.add_pokemon(create_owned_pokemon(engine.pokemon["Pidgey"], level=5))
        engine.advance_year(character)
        self.assertIn("Resumo anual", character.flags["last_year_report"])
        self.assertIn("Local:", character.flags["last_year_report"])
        self.assertIn("Pokemon:", character.flags["last_year_report"])
        self.assertIn("Encontros:", character.flags["last_year_report"])
        self.assertIn("Dinheiro:", character.flags["last_year_report"])
        self.assertIn("last_year_activity_report", character.flags)
        self.assertIn("captures", character.flags["last_year_activity_report"])
        self.assertFalse(any("annual_report" in entry.tags for entry in character.history))

    def test_event_choice_is_appended_to_current_annual_report(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 10
        character.career = CAREER_TRAINER
        character.add_pokemon(create_owned_pokemon(engine.pokemon["Pidgey"], level=5))
        engine.advance_year(character)
        event = LifeEvent(
            event_id="annual_note",
            title="Annual",
            text="Annual",
            min_age=1,
            max_age=99,
            phase=None,
            region=None,
            city=None,
            choices=[],
        )
        choice = type("Choice", (), {"effects": {}, "history_entry": "Voce tomou uma decisao importante.", "chance": None, "failure_effects": None, "failure_history_entry": None})()
        event.choices = [choice]
        engine.apply_event_choice(character, event, 0)
        self.assertIn("Evento: Voce tomou uma decisao importante.", character.flags["last_year_report"])

    def test_career_only_changes_on_transition_events(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 12
        character.career = "Treinador"
        normal_event = LifeEvent(
            event_id="normal_career_effect",
            title="Normal",
            text="Normal",
            min_age=1,
            max_age=99,
            phase=None,
            region=None,
            city=None,
            choices=[],
            tags=["care"],
        )
        transition_event = LifeEvent(
            event_id="transition_career_effect",
            title="Transition",
            text="Transition",
            min_age=1,
            max_age=99,
            phase=None,
            region=None,
            city=None,
            choices=[],
            tags=["career_transition"],
        )
        choice = type("Choice", (), {"effects": {"career": "Criador"}, "history_entry": "", "chance": None, "failure_effects": None, "failure_history_entry": None})()
        normal_event.choices = [choice]
        transition_event.choices = [choice]
        engine.apply_event_choice(character, normal_event, 0)
        self.assertEqual(character.career, "Treinador")
        engine.apply_event_choice(character, transition_event, 0)
        self.assertEqual(character.career, "Criador")

    def test_path_choice_event_is_only_valid_for_student_career(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 12
        character.career = "Criador"
        character.add_pokemon(create_owned_pokemon(engine.pokemon["Pidgey"], level=5))
        path_event = next(event for event in engine.journey_events if event.event_id == "choose_path_after_starter")
        self.assertNotIn(path_event, valid_events(character, engine.journey_events))
        character.career = "Estudante da academia"
        self.assertIn(path_event, valid_events(character, engine.journey_events))

    def test_student_after_ten_can_choose_academic_focus(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 12
        character.career = CAREER_STUDENT
        ok, message = engine.set_academy_focus(character, "pokemon_types", "Electric")
        self.assertTrue(ok, message)
        self.assertIn("Electric", focus_label(character))
        pikachu_bonus = capture_bonus_for(character, engine.pokemon["Pikachu"])
        rattata_bonus = capture_bonus_for(character, engine.pokemon["Rattata"])
        self.assertGreater(pikachu_bonus, rattata_bonus)

    def test_student_focus_progress_affects_attributes_and_training(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 12
        character.career = CAREER_STUDENT
        character.add_pokemon(create_owned_pokemon(engine.pokemon["Pidgey"], level=5))
        ok, _ = engine.set_academy_focus(character, "battle_theory")
        self.assertTrue(ok)
        pok_before = character.attributes.POK
        xp_before = character.team[0].experience + character.team[0].level * 100
        notes = progress_year(character, engine.pokemon)
        self.assertGreater(character.attributes.POK, pok_before)
        self.assertGreater(character.team[0].experience + character.team[0].level * 100, xp_before)
        self.assertTrue(any("Teoria de Batalha" in note or "estudos" in note for note in notes))

    def test_student_focus_progress_accumulates_before_attribute_bonus(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 12
        character.career = CAREER_STUDENT
        ok, _ = engine.set_academy_focus(character, "capture_techniques")
        self.assertTrue(ok)
        luk_before = character.attributes.LUK
        apply_focus_progress(character, 3)
        self.assertEqual(character.attributes.LUK, luk_before)
        apply_focus_progress(character, 3)
        apply_focus_progress(character, 3)
        apply_focus_progress(character, 3)
        self.assertEqual(character.attributes.LUK, min(100, luk_before + 1))

    def test_automatic_gym_invite_can_trigger_for_ready_team(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 12
        character.career = CAREER_TRAINER
        character.add_pokemon(create_owned_pokemon(engine.pokemon["Pidgey"], level=16))
        character.inventory["Mapa de Kanto"] = 1
        engine.move_to_city(character, "Pewter City")
        with patch("game.engine.random.random", return_value=0.0):
            invite = engine.resolve_automatic_gym_invite(character)
        self.assertIsNotNone(invite)
        self.assertIn("Convite de ginasio", invite)

    def test_gym_risk_preview_and_annual_notice_are_contextual(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 16
        character.career = CAREER_TRAINER
        character.add_pokemon(create_owned_pokemon(engine.pokemon["Pidgey"], level=16))
        character.inventory["Mapa de Kanto"] = 1
        engine.move_to_city(character, "Pewter City")
        preview = engine.gym_risk_preview(character)
        self.assertIsNotNone(preview)
        self.assertIn(preview["risk"], {"baixo", "moderado", "alto", "muito alto"})
        report = engine.build_annual_report(character, engine._year_snapshot(character), [], {})
        self.assertIn("Ginasios:", report)

    def test_adult_student_can_transition_to_research_careers(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 18
        character.career = "Estudante da academia"
        ids = {
            event.event_id
            for event in valid_events(character, engine.journey_events)
            if "career_transition" in event.tags
        }
        self.assertIn("adult_student_research_offer", ids)
        self.assertIn("adult_student_explorer_offer", ids)
        self.assertIn("adult_student_scientist_offer", ids)

    def test_annual_report_mentions_large_health_drop_reason(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 10
        before = engine._year_snapshot(character)
        character.health -= 15
        report = engine.build_annual_report(
            character,
            before,
            [],
            {"health_reasons": [{"delta": -15, "reason": "teste de esforco"}]},
        )
        self.assertIn("Saude: caiu 15", report)
        self.assertIn("teste de esforco", report)

    def test_profession_pokemon_bonus_uses_coherent_species(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.add_pokemon(create_owned_pokemon(engine.pokemon["Meowth"], level=8))
        factor, notes = pokemon_work_bonus(CAREER_MERCHANT, character.team)
        self.assertGreater(factor, 1.0)
        self.assertTrue(notes)

    def test_profession_missions_feed_annual_report_and_inventory(self) -> None:
        from game.year_simulation import ActivityResult, apply_activity_results

        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 16
        character.career = CAREER_BALL_CRAFTER
        result = ActivityResult(
            kind="career_mission",
            note="Missao de profissao: montagem de lote simples concluida.",
            money_delta=100,
            items_delta={"Poke Ball": 1},
            mission_name="montagem de lote simples",
            mission_success=True,
        )
        notes, activity_report = apply_activity_results(character, [result], engine.pokemon)
        report = engine.build_annual_report(character, engine._year_snapshot(character), notes, activity_report)
        self.assertEqual(character.inventory.get("Poke Ball", 0), 6)
        self.assertEqual(activity_report["career_missions"][0]["success"], True)
        self.assertIn("Profissao:", report)

    def test_lifestyle_courses_and_trips_use_city_economy_tiers(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 20
        character.money = 200000
        character.inventory["Mapa de Kanto"] = 1
        engine.move_to_city(character, "Saffron City")
        self.assertEqual(engine.current_city_economy_tier(character), 6)
        success, message = engine.buy_lifestyle_asset(character, "saffron_penthouse")
        self.assertTrue(success, message)
        self.assertIn("saffron_penthouse", character.assets)
        men_before = character.attributes.MEN
        success, message = engine.take_course(character, "lab_methods")
        self.assertTrue(success, message)
        self.assertGreater(character.attributes.MEN, men_before)
        character.health = 40
        success, message = engine.take_trip(character, "sevii_island_trip")
        self.assertTrue(success, message)
        self.assertGreater(character.health, 40)

    def test_selling_items_eggs_and_black_market_pokemon(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 20
        character.money = 50000
        character.inventory["Potion"] = 2
        success, message = engine.sell_item(character, "Potion", 1)
        self.assertTrue(success, message)
        self.assertEqual(character.inventory["Potion"], 1)
        from game.eggs import create_random_egg
        egg = create_random_egg(engine.pokemon, tier="R", origin="test")
        character.eggs.append(egg)
        success, message = engine.sell_egg(character, 0)
        self.assertTrue(success, message)
        self.assertFalse(character.eggs)
        character.inventory["Mapa de Kanto"] = 1
        engine.move_to_city(character, "Saffron City")
        offers = engine.black_market_pokemon_offers(character)
        self.assertTrue(offers)
        species, _ = offers[0]
        owned_before = len(character.team) + len(character.box)
        success, message = engine.buy_black_market_pokemon(character, species.name)
        self.assertTrue(success, message)
        self.assertGreater(len(character.team) + len(character.box), owned_before)

    def test_career_business_and_retirement_goals(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 62
        character.career = CAREER_MERCHANT
        character.money = 100000
        character.career_ranks[CAREER_MERCHANT] = 4
        character.flags["career_years"] = {CAREER_MERCHANT: 22}
        success, message = engine.start_business(character)
        self.assertTrue(success, message)
        self.assertIn(CAREER_MERCHANT, character.flags["businesses"])
        success, message = engine.retire_from_career(character)
        self.assertTrue(success, message)
        self.assertIsNone(character.career)
        self.assertGreater(character.flags["retirement_pension"], 0)

    def test_city_services_have_nearby_encounter_sources(self) -> None:
        services = json.loads(Path("data/city_services_kanto.json").read_text(encoding="utf-8"))
        by_city = {row["city"]: row for row in services}
        self.assertIn("route_1", by_city["Pallet Town"]["encounter_sources"])
        self.assertIn("safari_zone", by_city["Fuchsia City"]["encounter_sources"])

    def test_advance_time_supports_three_and_six_month_periods(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 10
        character.career = CAREER_TRAINER
        character.add_pokemon(create_owned_pokemon(engine.pokemon["Pidgey"], level=8))
        engine.advance_time(character, 3)
        self.assertEqual(character.age, 10)
        self.assertEqual(character.flags["age_month_progress"], 3)
        self.assertIn("Resumo de 3 meses", character.flags["last_year_report"])
        engine.advance_time(character, 6)
        self.assertEqual(character.age, 10)
        self.assertEqual(character.flags["age_month_progress"], 9)
        engine.advance_time(character, 3)
        self.assertEqual(character.age, 11)
        self.assertEqual(character.flags["age_month_progress"], 0)

    def test_kanto_league_requires_eight_badges_and_uses_fixed_levels(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 18
        character.money = 10000
        character.reputation = 40
        character.career = CAREER_TRAINER
        character.add_pokemon(create_owned_pokemon(engine.pokemon["Charizard"], level=60))
        ok, reason = can_enter_tournament(character, "kanto_league")
        self.assertFalse(ok)
        character.badges = [f"Badge {i}" for i in range(8)]
        ok, reason = can_enter_tournament(character, "kanto_league")
        self.assertTrue(ok, reason)
        opponents = generate_tournament(character, engine.pokemon, "kanto_league")
        self.assertEqual(len(opponents), 16)
        self.assertTrue(all(50 <= opponent.pokemon_level <= 60 for opponent in opponents))

    def test_contest_uses_beauty_and_rewards_reputation(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 16
        character.money = 1000
        character.career = CAREER_COORDINATOR
        pokemon = create_owned_pokemon(engine.pokemon["Vulpix"], level=18)
        pokemon.beauty = 95
        character.add_pokemon(pokemon)
        success, result, message = engine.enter_contest(character, 0, "local")
        self.assertTrue(success, message)
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.participants, result.rank)

    def test_contest_win_adds_visual_ribbon_flag(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 16
        character.money = 1000
        character.career = CAREER_COORDINATOR
        pokemon = create_owned_pokemon(engine.pokemon["Vulpix"], level=30)
        pokemon.beauty = 100
        pokemon.occult = 100
        character.add_pokemon(pokemon)
        with patch("game.contests.random.uniform", return_value=0.9):
            success, result, message = engine.enter_contest(character, 0, "local", "beauty")
        self.assertTrue(success, message)
        self.assertEqual(result.rank, 1)
        self.assertTrue(character.flags.get("contest_ribbons"))
        self.assertIn("Ribbon Beauty", character.flags["contest_ribbons"][0])


    def test_breeder_has_better_breed_egg_path(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 18
        character.career = CAREER_BREEDER
        first = create_owned_pokemon(engine.pokemon["Eevee"], level=12)
        second = create_owned_pokemon(engine.pokemon["Rattata"], level=12)
        first.happiness = 90
        second.happiness = 90
        character.add_pokemon(first)
        character.add_pokemon(second)
        preview = engine.breeding_preview(character, 0, 1)
        self.assertTrue(preview["available"])
        self.assertGreater(preview["chance"], 30)
        with patch("game.breeding.random.random", return_value=0.0):
            success, message = engine.breed_pokemon(character, 0, 1)
        self.assertTrue(success, message)
        self.assertEqual(len(character.eggs), 1)

    def test_gym_preview_uses_series_details(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 16
        character.career = CAREER_TRAINER
        for name in ("Pidgey", "Mankey", "Geodude"):
            character.add_pokemon(create_owned_pokemon(engine.pokemon[name], level=18))
        character.inventory["Mapa de Kanto"] = 1
        engine.move_to_city(character, "Pewter City")
        preview = engine.gym_risk_preview(character)
        self.assertIsNotNone(preview)
        self.assertGreaterEqual(preview["opponents"], 3)
        self.assertIn("average_match_chance", preview)
        self.assertIn("match_chances", preview)

    def test_gym_preview_handles_team_with_no_healthy_pokemon(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 16
        character.inventory["Mapa de Kanto"] = 1
        pokemon = create_owned_pokemon(engine.pokemon["Pidgey"], level=18)
        pokemon.current_health = 0
        pokemon.status = "badly_injured"
        character.add_pokemon(pokemon)
        engine.move_to_city(character, "Pewter City")
        preview = engine.gym_risk_preview(character)
        self.assertFalse(preview["available"])
        self.assertIn("recuperar", preview["summary"])
        estimate = estimate_series_chance(
            character,
            [SeriesOpponent("Teste", "Geodude", 12)],
            engine.pokemon,
            wins_required=1,
        )
        self.assertEqual(estimate["series_chance"], 0)

    def test_gym_defeat_allows_rematch_and_grants_team_xp(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 14
        character.career = CAREER_TRAINER
        for name in ("Pidgey", "Rattata", "Caterpie"):
            character.add_pokemon(create_owned_pokemon(engine.pokemon[name], level=8))
        character.inventory["Mapa de Kanto"] = 1
        engine.move_to_city(character, "Pewter City")
        before_xp = sum(pokemon.experience for pokemon in character.team)
        with patch("game.battle.random.random", return_value=1.0):
            won, log = engine.challenge_city_gym(character)
        self.assertFalse(won)
        self.assertFalse(character.badges)
        self.assertGreater(sum(pokemon.experience for pokemon in character.team), before_xp)
        for pokemon in character.team:
            pokemon.heal_full(engine.pokemon[pokemon.species])
            pokemon.status = "healthy"
        won_again, log_again = engine.challenge_city_gym(character)
        self.assertIsInstance(won_again, bool)

    def test_tournament_rounds_are_best_of_three(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 18
        character.money = 5000
        character.reputation = 20
        character.add_pokemon(create_owned_pokemon(engine.pokemon["Charizard"], level=55))
        opponents = generate_tournament(character, engine.pokemon, "city")
        self.assertTrue(all(len(opponent.team) == 3 for opponent in opponents))
        ok, result, message = engine.enter_tournament(character, "city")
        self.assertTrue(ok, message)
        self.assertTrue(any("melhor de 3" in line for line in result.log))
        opponents = generate_tournament(character, engine.pokemon, "city", engine.name_database)
        self.assertTrue(all(" " in opponent.name for opponent in opponents))

    def test_contest_categories_and_items_affect_result_shape(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 18
        character.money = 3000
        character.career = CAREER_COORDINATOR
        character.inventory["Mystic Veil"] = 1
        pokemon = create_owned_pokemon(engine.pokemon["Gastly"], level=20)
        pokemon.occult = 95
        character.add_pokemon(pokemon)
        success, result, message = engine.enter_contest(character, 0, "local", "mysterious")
        self.assertTrue(success, message)
        self.assertEqual(result.category, "mysterious")
        self.assertTrue(any("Mysterious" in line for line in result.log))

    def test_criminal_reputation_can_ban_official_events(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 18
        character.money = 5000
        character.career = CAREER_CRIMINAL
        character.add_pokemon(create_owned_pokemon(engine.pokemon["Ekans"], level=20))
        with patch("game.engine.random.random", return_value=1.0):
            success, message = engine.steal_pokemon(character, "Pidgey")
        self.assertFalse(success)
        self.assertLess(character.reputation, 0)
        character.flags["official_event_ban"] = True
        ok, reason = can_enter_tournament(character, "city")
        self.assertFalse(ok)
        self.assertIn("banido", reason)

    def test_prison_sentence_blocks_actions_and_progresses_time(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 18
        character.money = 2000
        character.career = CAREER_CRIMINAL
        character.add_pokemon(create_owned_pokemon(engine.pokemon["Ekans"], level=20))
        with patch("game.engine.random.random", return_value=0.0):
            success, message = engine.steal_pokemon(character, "Pidgey")
        self.assertTrue(character.flags.get("in_prison"))
        self.assertGreater(character.flags.get("prison_months_remaining", 0), 0)
        ok, log = engine.challenge_city_gym(character)
        self.assertFalse(ok)
        before = character.flags["prison_months_remaining"]
        engine.advance_time(character, 3)
        self.assertLess(character.flags["prison_months_remaining"], before)

    def test_mortality_risk_scales_with_age_health_and_prison(self) -> None:
        young = Character("Young")
        young.age = 18
        young.health = 95
        old = Character("Old")
        old.age = 82
        old.health = 24
        young_chance, _ = mortality_chance(young, 12)
        old_chance, _ = mortality_chance(old, 12)
        prison_chance, cause = mortality_chance(old, 12, "prison", -20)
        self.assertGreater(old_chance, young_chance)
        self.assertGreater(prison_chance, old_chance)
        self.assertIn("prisao", cause)

    def test_death_sets_game_over_and_blocks_official_actions(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 90
        character.health = 5
        character.career = CAREER_TRAINER
        character.add_pokemon(create_owned_pokemon(engine.pokemon["Pidgey"], level=20))
        with patch("game.mortality.random.random", return_value=0.0):
            engine.advance_time(character, 3)
        self.assertTrue(character.flags.get("dead"))
        self.assertEqual(character.health, 0)
        self.assertIn("Game over", character.flags["last_year_report"])
        ok, reason = can_enter_tournament(character, "city")
        self.assertFalse(ok)
        self.assertIn("morreu", reason)
        ok, message = engine.challenge_city_gym(character)
        self.assertFalse(ok)
        self.assertIn("Game over", message[0])

    def test_prison_sentences_are_stricter_and_prison_fights_can_kill(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
        character.age = 55
        character.health = 20
        character.career = CAREER_CRIMINAL
        sentence = sentence_for_crime("pokemon_theft", character.reputation, character.career)
        self.assertGreaterEqual(sentence.months, 36)
        character.flags["in_prison"] = True
        character.flags["prison_months_remaining"] = sentence.months
        with patch("game.prison.random.random", return_value=0.0), patch("game.prison.random.randint", return_value=18), patch("game.mortality.random.random", return_value=0.0):
            engine.advance_time(character, 12)
        self.assertTrue(character.flags.get("last_prison_fight"))
        self.assertTrue(character.flags.get("dead"))
        self.assertIn("prisao", character.flags.get("death_cause", ""))

    def test_web_app_can_create_advance_and_run_action(self) -> None:
        from web.app import app

        client = app.test_client()
        created = client.post("/api/new", json={"name": "WebCase", "hometown": "Pallet Town"})
        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.get_json()["state"]["name"], "WebCase")

        advanced = client.post("/api/advance", json={"months": 12})
        self.assertEqual(advanced.status_code, 200)
        self.assertIn("feed", advanced.get_json())

        studied = client.post("/api/action/read", json={})
        self.assertEqual(studied.status_code, 200)
        self.assertGreaterEqual(studied.get_json()["state"]["attributes"]["POK"], 0)

    def test_web_oak_event_can_be_accepted(self) -> None:
        import web.app as web_app

        client = web_app.app.test_client()
        created = client.post("/api/new", json={"name": "OakWeb", "hometown": "Pallet Town"})
        self.assertEqual(created.status_code, 200)
        web_app.character.age = 9
        web_app.character.current_city = "Pallet Town"
        web_app.character.hometown = "Pallet Town"
        web_app.character.team = []
        web_app.character.box = []
        web_app.character.flags.pop("oak_event_done", None)
        advanced = client.post("/api/advance", json={"months": 12})
        self.assertEqual(advanced.status_code, 200)
        payload = advanced.get_json()
        self.assertIsNotNone(payload.get("pending_event"))
        self.assertIn("Professor Oak", payload["pending_event"]["title"])
        career_step = client.post("/api/event_choice", json={"index": 0})
        self.assertEqual(career_step.status_code, 200)
        self.assertIsNotNone(career_step.get_json().get("pending_event"))
        self.assertIn("Bulbasaur", career_step.get_json()["pending_event"]["choices"][0]["text"])
        accepted = client.post("/api/event_choice", json={"index": 0})
        self.assertEqual(accepted.status_code, 200)
        state = accepted.get_json()["state"]
        self.assertTrue(state["team"])
        self.assertEqual(state["team"][0]["species"], "Bulbasaur")
        self.assertTrue(state["team"][0]["sprite"].endswith("001-bulbasaur.png"))
        self.assertTrue(Path("web/static/sprites/pokemon/001-bulbasaur.png").exists())
        self.assertEqual(state["career"], "Treinador")

    def test_web_oak_student_path_chooses_academy_focus(self) -> None:
        import web.app as web_app

        client = web_app.app.test_client()
        created = client.post("/api/new", json={"name": "StudentOak", "hometown": "Pallet Town"})
        self.assertEqual(created.status_code, 200)
        web_app.character.age = 9
        web_app.character.current_city = "Pallet Town"
        web_app.character.hometown = "Pallet Town"
        web_app.character.team = []
        web_app.character.box = []
        web_app.character.flags.pop("oak_event_done", None)
        advanced = client.post("/api/advance", json={"months": 12})
        self.assertEqual(advanced.status_code, 200)
        student_step = client.post("/api/event_choice", json={"index": 3})
        self.assertEqual(student_step.status_code, 200)
        self.assertIsNotNone(student_step.get_json().get("pending_event"))
        focus_step = client.post("/api/event_choice", json={"index": 0})
        self.assertEqual(focus_step.status_code, 200)
        state = focus_step.get_json()["state"]
        self.assertEqual(state["career"], "Estudante da academia")
        self.assertFalse(state["team"])
        self.assertIsNone(focus_step.get_json().get("pending_event"))
        self.assertTrue(web_app.character.flags.get("academy_focus"))

    def test_web_does_not_advance_after_death(self) -> None:
        import web.app as web_app

        client = web_app.app.test_client()
        created = client.post("/api/new", json={"name": "DeadWeb", "hometown": "Pallet Town"})
        self.assertEqual(created.status_code, 200)
        web_app.character.age = 15
        web_app.character.flags["dead"] = True
        web_app.character.flags["death_cause"] = "teste"
        web_app.character.flags["last_year_report"] = "Game over\nDeadWeb morreu aos 15 anos por teste."

        advanced = client.post("/api/advance", json={"months": 12})

        self.assertEqual(advanced.status_code, 200)
        state = advanced.get_json()["state"]
        self.assertEqual(state["age"], 15)
        self.assertTrue(state["dead"])
        self.assertFalse(state["action_availability"]["advance"])

    def test_web_feed_cards_include_pokemon_sprite_mentions(self) -> None:
        import web.app as web_app

        mentions = web_app.pokemon_mentions_for_text("Um Pidgey selvagem apareceu perto de Pallet Town.")

        self.assertEqual(mentions[0]["name"], "Pidgey")
        self.assertTrue(mentions[0]["sprite"].endswith("016-pidgey.png"))


if __name__ == "__main__":
    unittest.main()
