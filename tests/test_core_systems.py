import unittest
import json
from pathlib import Path
from unittest.mock import patch

from game.attributes import PlayerAttributes, generate_initial_attributes
from game.battle import resolve_auto_battle
from game.capture import attempt_capture, calculate_capture_chance
from game.economy import calculate_money_gain
from game.inventory import Item
from game.pokemon import PokemonSpecies, assign_evolution_stages, create_owned_pokemon
from game.character import Character
from game.careers import CAREER_TRAINER, available_careers
from game.progression import progress_year
from game.progression import grant_pokemon_xp
from game.engine import GameEngine
from game.events import LifeEvent, event_occurrence_chance, event_weight, valid_events
from game.eggs import create_random_egg, progress_eggs


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
        self.assertEqual(available_careers(7, False), ["Estudante da academia"])
        self.assertIn(CAREER_TRAINER, available_careers(10, True))

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
            if "gym" in city:
                self.assertIn(city["gym"], gyms)

    def test_city_shop_and_healing_actions_work(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Green")
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
        engine.move_to_city(character, "Viridian City")
        self.assertEqual(engine.heal_team_in_city(character), "Sua equipe foi curada.")
        self.assertEqual(character.team[0].current_health, character.team[0].healthy)
        self.assertEqual(character.team[0].status, "healthy")

    def test_city_gym_lookup_uses_current_city(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Green")
        character.age = 10
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
            for member in gym["team"]:
                self.assertIn(gym["main_type"], engine.pokemon[member["species"]].types)
                self.assertGreaterEqual(member["level"], 12)
                self.assertLessEqual(member["level"], 41)
                self.assertGreaterEqual(member["level"], gym["level_range"][0])
                self.assertLessEqual(member["level"], gym["level_range"][1])

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
        self.assertTrue(engine.move_to_city(character, "Viridian City"))

    def test_buy_common_egg_adds_egg_not_inventory_stack(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
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
        engine.move_to_city(character, "Viridian City")
        pok_before = character.attributes.POK
        self.assertIn("POK", engine.manual_action_read_about_pokemon(character))
        self.assertGreater(character.attributes.POK, pok_before)
        money_before = character.money
        engine.manual_action_work_city(character)
        self.assertGreaterEqual(character.money, money_before)
        character.add_pokemon(create_owned_pokemon(engine.pokemon["Pidgey"], level=5))
        xp_before = character.active_pokemon().experience
        engine.manual_action_train_team(character)
        self.assertGreaterEqual(character.active_pokemon().experience + character.active_pokemon().level * 100, xp_before + 500)

    def test_use_items_apply_simple_effects(self) -> None:
        engine = GameEngine()
        character = engine.create_character("Case")
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
        with patch("game.engine.random.random", return_value=0.0):
            notes = engine.resolve_automatic_year_encounter(character)
        self.assertTrue(notes)
        self.assertIn("Durante o ano", notes[0])
        self.assertTrue(any(word in " ".join(notes) for word in ("Captura automatica", "Batalha automatica", "observou")))

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


if __name__ == "__main__":
    unittest.main()
