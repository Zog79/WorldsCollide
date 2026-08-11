import argparse
import sys
import unittest


def _import_characters_args():
    # importing args.characters first imports the "args" package itself,
    # which parses sys.argv at import time (pre-existing, project-wide
    # singleton pattern) -- substitute a minimal valid argv just for this
    # import so the test runner's own argv isn't fed to argparse, then
    # restore it immediately after.
    original_argv = sys.argv
    sys.argv = ["test", "-i", "dummy.smc"]
    try:
        import args.characters as characters_args
        from args.arguments import Arguments
    finally:
        sys.argv = original_argv
    return characters_args, Arguments


characters_args, Arguments = _import_characters_args()


def parse(argv):
    parser = argparse.ArgumentParser()
    characters_args.parse(parser)
    namespace = parser.parse_args(argv)
    Arguments._process_min_max(namespace, "character_stat_random_percent")
    return namespace


def options_dict(namespace):
    return {label: value for label, value, _ in characters_args.options(namespace)}


class TestCharacterStatRandomPercentGate(unittest.TestCase):
    # without -csrp, the feature (and the Status Menu stat color hook it
    # gates) must be OFF -- character_stat_random_percent must be a falsy
    # value (None), not a "neutral" but truthy default like [100, 100]
    def test_without_flag_the_feature_is_disabled(self):
        namespace = parse([])
        self.assertIsNone(namespace.character_stat_random_percent)
        self.assertFalse(namespace.character_stat_random_percent)

    def test_without_flag_min_max_are_not_set(self):
        namespace = parse([])
        self.assertFalse(hasattr(namespace, "character_stat_random_percent_min"))
        self.assertFalse(hasattr(namespace, "character_stat_random_percent_max"))

    def test_without_flag_it_is_absent_from_the_flags_string(self):
        namespace = parse([])
        self.assertEqual(characters_args.flags(namespace), "")

    def test_without_flag_options_report_original(self):
        namespace = parse([])
        self.assertEqual(options_dict(namespace)["Character Stats"], "Original")

    def test_with_flag_the_feature_is_enabled(self):
        namespace = parse(["-csrp", "50", "150"])
        self.assertTrue(namespace.character_stat_random_percent)
        self.assertEqual(namespace.character_stat_random_percent_min, 50)
        self.assertEqual(namespace.character_stat_random_percent_max, 150)

    def test_with_flag_it_appears_in_the_flags_string(self):
        namespace = parse(["-csrp", "50", "150"])
        self.assertIn("-csrp 50 150", characters_args.flags(namespace))

    def test_with_flag_options_report_the_range(self):
        namespace = parse(["-csrp", "50", "150"])
        self.assertEqual(options_dict(namespace)["Character Stats"], "50-150%")


if __name__ == "__main__":
    unittest.main()
