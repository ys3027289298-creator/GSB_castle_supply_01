import unittest

from castle import core
from castle.core import CastleGame


class FoodAllocationTest(unittest.TestCase):
    def test_same_food_not_allocated_twice(self):
        game = CastleGame(seed=1)
        food_before = game.food
        self.assertEqual(game.apply(core.CMD_FEED), core.MSG_OK)
        self.assertEqual(game.apply(core.CMD_FEED), core.MSG_ALREADY_FED)
        cost = (game.soldiers + game.wounded) * core.FOOD_PER_HEAD
        self.assertEqual(game.food, food_before - cost)

    def test_feed_resets_next_turn(self):
        game = CastleGame(seed=1)
        game.apply(core.CMD_FEED)
        game.apply(core.CMD_END_TURN)
        self.assertEqual(game.apply(core.CMD_FEED), core.MSG_OK)


class GateRepairTest(unittest.TestCase):
    def test_repair_deducts_materials(self):
        game = CastleGame(seed=1)
        game.gate = 50
        materials_before = game.materials
        self.assertEqual(game.apply(core.CMD_REPAIR), core.MSG_OK)
        self.assertEqual(game.gate, 60)
        self.assertEqual(game.materials,
                         materials_before - 10 * core.REPAIR_MATERIALS_PER_POINT)

    def test_repair_without_materials_rejected(self):
        game = CastleGame(seed=1)
        game.gate = 50
        game.materials = 0
        self.assertEqual(game.apply(core.CMD_REPAIR), core.MSG_NO_MATERIALS)
        self.assertEqual(game.gate, 50)


class NightRaidTest(unittest.TestCase):
    def test_no_raid_on_truce_day(self):
        game = CastleGame(seed=1)
        while not game.is_truce(game.day):
            game.apply(core.CMD_END_TURN)
        gate_before = game.gate
        game.apply(core.CMD_END_TURN)
        self.assertEqual(game.gate, gate_before)
        self.assertIn(core.MSG_TRUCE, game.log)

    def test_raid_on_normal_day(self):
        game = CastleGame(seed=1)
        self.assertFalse(game.is_truce(game.day))
        self.assertGreater(game.raid_damage(game.day), 0)


class ArrowTest(unittest.TestCase):
    def test_cannot_shoot_without_arrows(self):
        game = CastleGame(seed=1)
        game.arrows = 0
        self.assertEqual(game.apply(core.CMD_SHOOT), core.MSG_NO_ARROWS)
        self.assertEqual(game.arrows, 0)

    def test_shoot_consumes_arrows(self):
        game = CastleGame(seed=1)
        self.assertEqual(game.apply(core.CMD_SHOOT), core.MSG_OK)
        self.assertEqual(game.arrows, 100 - core.VOLLEY_ARROWS)


class DefenderTest(unittest.TestCase):
    def test_wounded_not_counted_as_defenders(self):
        game = CastleGame(seed=1)
        game.soldiers = 10
        game.wounded = 5
        self.assertEqual(game.defenders, 10)


class RecallTest(unittest.TestCase):
    def test_recall_returns_morale(self):
        game = CastleGame(seed=1)
        game.morale = 40
        self.assertEqual(game.apply(core.CMD_RECALL), core.MSG_OK)
        self.assertEqual(game.morale, 40 + core.RECALL_MORALE_RETURN)


class EventReplayTest(unittest.TestCase):
    def test_replay_keeps_random_order(self):
        game = CastleGame(seed=9)
        first = [game.raid_damage(day) for day in range(1, 8)]
        game.preview_events(3)
        game.raid_damage(3)
        second = [game.raid_damage(day) for day in range(1, 8)]
        self.assertEqual(first, second)

    def test_same_seed_same_sequence(self):
        game_a = CastleGame(seed=9)
        game_b = CastleGame(seed=9)
        for _ in range(3):
            game_a.apply(core.CMD_END_TURN)
            game_b.apply(core.CMD_END_TURN)
        self.assertEqual(game_a.save(), game_b.save())


class VictoryTest(unittest.TestCase):
    def test_no_settlement_after_victory(self):
        game = CastleGame(seed=1)
        game.day = core.VICTORY_DAY
        self.assertEqual(game.apply(core.CMD_END_TURN), core.MSG_VICTORY)
        self.assertTrue(game.over)
        snapshot = game.save()
        self.assertEqual(game.apply(core.CMD_END_TURN), core.MSG_GAME_OVER)
        self.assertEqual(game.apply(core.CMD_SHOOT), core.MSG_GAME_OVER)
        self.assertEqual(game.save(), snapshot)

    def test_no_settlement_after_defeat(self):
        game = CastleGame(seed=1)
        game.gate = 1
        result = game.apply(core.CMD_END_TURN)
        self.assertEqual(result, core.MSG_DEFEAT)
        self.assertTrue(game.over)
        self.assertFalse(game.victory)
        self.assertEqual(game.apply(core.CMD_FEED), core.MSG_GAME_OVER)


class AtomicTurnTest(unittest.TestCase):
    def test_end_turn_applies_all_changes_together(self):
        game = CastleGame(seed=5)
        game.apply(core.CMD_FEED)
        game.apply(core.CMD_END_TURN)
        self.assertFalse(game._food_allocated)
        self.assertEqual(game.day, 2)
        self.assertGreaterEqual(game.morale, 0)
        self.assertLessEqual(game.gate, core.MAX_GATE)


class IllegalCommandTest(unittest.TestCase):
    def test_unknown_command_rejected(self):
        game = CastleGame(seed=1)
        snapshot = game.save()
        self.assertEqual(game.apply("炸毁城墙"), core.MSG_INVALID)
        self.assertEqual(game.save(), snapshot)

    def test_empty_command_rejected(self):
        game = CastleGame(seed=1)
        self.assertEqual(game.apply(""), core.MSG_INVALID)


class EmptyDataTest(unittest.TestCase):
    def test_load_empty_save_rejected(self):
        with self.assertRaises(ValueError):
            CastleGame.load({})

    def test_load_missing_keys_rejected(self):
        with self.assertRaises(ValueError):
            CastleGame.load({"day": 1, "food": 10})

    def test_save_load_roundtrip(self):
        game = CastleGame(seed=3)
        game.apply(core.CMD_FEED)
        game.apply(core.CMD_END_TURN)
        restored = CastleGame.load(game.save())
        self.assertEqual(restored.save(), game.save())
        self.assertEqual(set(game.save()), set(core.SAVE_KEYS))


class CapacityBoundaryTest(unittest.TestCase):
    def test_morale_capped_at_max(self):
        game = CastleGame(seed=1)
        game.morale = core.MAX_MORALE
        game.apply(core.CMD_RECALL)
        self.assertEqual(game.morale, core.MAX_MORALE)

    def test_gate_capped_at_max(self):
        game = CastleGame(seed=1)
        game.gate = core.MAX_GATE
        materials_before = game.materials
        game.apply(core.CMD_REPAIR)
        self.assertEqual(game.gate, core.MAX_GATE)
        self.assertEqual(game.materials, materials_before)

    def test_morale_not_below_zero(self):
        game = CastleGame(seed=1)
        game.morale = 0
        game.apply(core.CMD_END_TURN)
        self.assertEqual(game.morale, 0)


class DuplicateInputTest(unittest.TestCase):
    def test_duplicate_command_list_idempotent_state(self):
        game = CastleGame(seed=1)
        script = [core.CMD_FEED, core.CMD_FEED, core.CMD_SHOOT, core.CMD_SHOOT]
        results = [game.apply(command) for command in script]
        self.assertEqual(results[1], core.MSG_ALREADY_FED)
        cost = (game.soldiers + game.wounded) * core.FOOD_PER_HEAD
        self.assertEqual(game.food, 100 - cost)
        self.assertEqual(game.arrows, 100 - 2 * core.VOLLEY_ARROWS)


class DemoTest(unittest.TestCase):
    def test_fixed_demo_runs(self):
        game = core.run_demo()
        self.assertIsInstance(game, CastleGame)
        self.assertFalse(game.over)


if __name__ == "__main__":
    unittest.main()
