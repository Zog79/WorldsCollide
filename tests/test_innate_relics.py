import random
import sys
import unittest


def _import_innate_relics():
    # data.innate_relics imports data.items, which imports the "args" package.
    # That package parses sys.argv at import time (pre-existing, project-wide
    # singleton pattern, unrelated to innate relics itself) -- substitute a
    # minimal valid argv just for this import so the test runner's own argv
    # doesn't get fed to argparse, then restore it immediately after.
    original_argv = sys.argv
    sys.argv = ["test", "-i", "dummy.smc"]
    try:
        from data.innate_relics import InnateRelics
    finally:
        sys.argv = original_argv
    return InnateRelics


InnateRelics = _import_innate_relics()


class FakeCharacter:
    def __init__(self, id):
        self.id = id


class FakeCharacters:
    def __init__(self, count = 14):
        self.playable = [FakeCharacter(i) for i in range(count)]


class FakeItems:
    # InnateRelics.relic_pool() only ever calls get_id() with the literal
    # names from its own COMMON_RELIC_NAMES/RARE_RELIC_NAMES pools, so a
    # simple identity mapping is enough to exercise assign()'s own logic
    # without needing the real item table.
    def get_id(self, name):
        return name


class FakeArgs:
    def __init__(self, percent):
        self.random_innate_relics = percent


def make_innate_relics(percent):
    return InnateRelics(rom = None, args = FakeArgs(percent), characters = FakeCharacters(), items = FakeItems())


class TestRandomInnateRelicsSemantics(unittest.TestCase):
    # -rir 0 -> nobody gets a relic
    def test_zero_percent_assigns_nobody(self):
        ir = make_innate_relics(0)
        ir.assign()
        self.assertEqual(ir.relic_assignments, {})

    # -rir 100 -> every one of the 14 playable characters gets a relic
    def test_hundred_percent_assigns_everybody(self):
        ir = make_innate_relics(100)
        ir.assign()
        self.assertEqual(len(ir.relic_assignments), 14)
        self.assertEqual(set(ir.relic_assignments.keys()), set(range(14)))

    def test_assigned_relics_come_from_the_declared_pools(self):
        ir = make_innate_relics(100)
        ir.assign()
        pool = set(InnateRelics.COMMON_RELIC_NAMES) | set(InnateRelics.RARE_RELIC_NAMES)
        for item_id in ir.relic_assignments.values():
            self.assertIn(item_id, pool)

    # each character is rolled independently (per current, intentional
    # semantics) rather than a fixed count of characters being chosen --
    # guards against a regression to the older "fixed count" model
    def test_middle_percent_is_a_per_character_roll_not_a_fixed_count(self):
        counts = set()
        for seed in range(50):
            random.seed(seed)
            ir = make_innate_relics(50)
            ir.assign()
            counts.add(len(ir.relic_assignments))
        self.assertGreater(len(counts), 1)


class TestRelicPoolIntegrity(unittest.TestCase):
    def test_no_overlap_between_common_and_rare_pools(self):
        common = set(InnateRelics.COMMON_RELIC_NAMES)
        rare = set(InnateRelics.RARE_RELIC_NAMES)
        self.assertEqual(common & rare, set())

    def test_no_duplicate_names_within_either_pool(self):
        self.assertEqual(len(InnateRelics.COMMON_RELIC_NAMES), len(set(InnateRelics.COMMON_RELIC_NAMES)))
        self.assertEqual(len(InnateRelics.RARE_RELIC_NAMES), len(set(InnateRelics.RARE_RELIC_NAMES)))


if __name__ == "__main__":
    unittest.main()
