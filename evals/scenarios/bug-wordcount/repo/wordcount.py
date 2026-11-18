"""Count words in text files."""
import sys


def count_words(text: str) -> int:
    return len(text.split(" "))


def main(argv: list[str]) -> int:
    total = 0
    for path in argv:
        with open(path) as handle:
            n = count_words(handle.read())
        print(f"{n}\t{path}")
        total += n
    if len(argv) > 1:
        print(f"{total}\ttotal")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
