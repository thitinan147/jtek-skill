"""Acceptance tests the agent never sees. Run with the worktree on the import path."""
import unittest

from wordcount import count_words


class Hidden(unittest.TestCase):
    def test_mixed_whitespace(self):
        self.assertEqual(count_words("one  two\nthree\tfour\n"), 4)

    def test_empty(self):
        self.assertEqual(count_words(""), 0)

    def test_only_whitespace(self):
        self.assertEqual(count_words(" \n\t "), 0)

    def test_single_spaces_unchanged(self):
        self.assertEqual(count_words("one two three"), 3)


if __name__ == "__main__":
    unittest.main()
