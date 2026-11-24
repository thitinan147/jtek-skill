import unittest

from config import read_client, read_server


class Config(unittest.TestCase):
    def test_server(self):
        self.assertEqual(read_server(["host = 0.0.0.0", "port = 9000"]), {"host": "0.0.0.0", "port": 9000})

    def test_server_defaults(self):
        self.assertEqual(read_server(["# nothing"]), {"host": "127.0.0.1", "port": 8000})

    def test_client(self):
        self.assertEqual(read_client(["url = http://example.com/", "timeout = 5"]),
                         {"url": "http://example.com/", "timeout": 5.0})


if __name__ == "__main__":
    unittest.main()
