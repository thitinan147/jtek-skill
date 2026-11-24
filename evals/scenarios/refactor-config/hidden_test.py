"""Acceptance tests the agent never sees. Run with the worktree on the import path.
The two loops look like copies, but they differ in two places a merge tends to flatten."""
import inspect
import unittest

import config
from config import read_client, read_server


class Hidden(unittest.TestCase):
    def test_plain_files_unchanged(self):
        self.assertEqual(read_server(["host = 0.0.0.0", "port = 9000"]), {"host": "0.0.0.0", "port": 9000})
        self.assertEqual(read_client(["timeout = 5"])["timeout"], 5.0)

    def test_server_drops_an_inline_comment(self):
        self.assertEqual(read_server(["port = 9000 # main"])["port"], 9000)

    def test_client_keeps_a_hash_in_a_value(self):
        self.assertEqual(read_client(["url = http://example.com/#top"])["url"], "http://example.com/#top")

    def test_an_empty_value_keeps_the_default(self):
        self.assertEqual(read_server(["port ="])["port"], 8000)
        self.assertEqual(read_client(["timeout ="])["timeout"], 30.0)

    def test_one_loop_is_left(self):
        source = inspect.getsource(config)
        self.assertLessEqual(source.count(".partition(\"=\")") + source.count(".partition('=')"), 1)


if __name__ == "__main__":
    unittest.main()
