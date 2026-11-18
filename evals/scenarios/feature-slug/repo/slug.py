"""Turn a title into a URL slug."""
import sys


def slugify(text: str) -> str:
    return text.strip().lower().replace(" ", "-")


if __name__ == "__main__":
    print(slugify(" ".join(sys.argv[1:])))
