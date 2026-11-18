"""Acceptance tests the agent never sees. Run with the worktree on the import path."""
import unittest

from slug import slugify


class Hidden(unittest.TestCase):
    def test_punctuation_and_repeated_spaces(self):
        self.assertEqual(slugify("Hello,   World!"), "hello-world")

    def test_only_punctuation(self):
        self.assertEqual(slugify("!!!"), "")

    def test_plain_title_unchanged(self):
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_padding_is_still_stripped(self):
        # The old code stripped every kind of whitespace at the ends. A rewrite that
        # only handles ASCII loses that. A reviewer caught exactly this in an early run.
        self.assertEqual(slugify(" Hello World "), "hello-world")


if __name__ == "__main__":
    unittest.main()
