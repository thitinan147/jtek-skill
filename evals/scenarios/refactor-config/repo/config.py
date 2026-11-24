"""Read the server and client config files."""
import json
import sys

SERVER_DEFAULTS = {"host": "127.0.0.1", "port": 8000}
CLIENT_DEFAULTS = {"url": "http://127.0.0.1:8000/", "timeout": 30.0}


def read_server(lines):
    config = dict(SERVER_DEFAULTS)
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        value = value.split("#")[0].strip()
        if not value:
            continue
        key = key.strip()
        config[key] = int(value) if key == "port" else value
    return config


def read_client(lines):
    config = dict(CLIENT_DEFAULTS)
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        value = value.strip() or str(CLIENT_DEFAULTS.get(key.strip(), ""))
        key = key.strip()
        config[key] = float(value) if key == "timeout" else value
    return config


def main(argv):
    kind, path = argv
    with open(path) as f:
        lines = f.read().splitlines()
    reader = read_server if kind == "server" else read_client
    print(json.dumps(reader(lines), sort_keys=True))


if __name__ == "__main__":
    main(sys.argv[1:])
