import unittest
from slug import slugify


class SlugTests(unittest.TestCase):
    def test_spaces_become_dashes(self):
        self.assertEqual(slugify("Hello World"), "hello-world")


if __name__ == "__main__":
    unittest.main()
