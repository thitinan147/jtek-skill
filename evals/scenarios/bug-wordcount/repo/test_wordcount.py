import unittest
from wordcount import count_words


class CountTests(unittest.TestCase):
    def test_single_spaces(self):
        self.assertEqual(count_words("one two three"), 3)


if __name__ == "__main__":
    unittest.main()
