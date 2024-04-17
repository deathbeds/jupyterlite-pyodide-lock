"""replace text in a file with text from another file between matching markers."""

from argparse import ArgumentParser
from pathlib import Path

UTF8 = dict(encoding="utf-8")

PARSER = ArgumentParser()
PARSER.add_argument("source", type=Path)
PARSER.add_argument("dest", type=Path)
PARSER.add_argument("pattern", default=None)


def replace_between(source: Path, dest: Path, pattern: str | None) -> int:
    """Replace text in a file with text from another file between matching markers."""
    pattern = pattern or f"### {source.name} ###"
    src_text = source.read_text(**UTF8)
    dest_text = dest.read_text(**UTF8)
    if pattern not in dest_text:
        print(f"'{pattern}' not in {dest}")
        return 1
    if pattern not in src_text:
        print(f"'{pattern}' not in {source}")
        return 1
    src_chunks = src_text.split(pattern)
    dest_chunks = dest_text.split(pattern)
    dest_text = "".join(
        [dest_chunks[0], pattern, src_chunks[1], pattern, dest_chunks[2]]
    )
    dest.write_text(dest_text, encoding="utf-8")
    return True


if __name__ == "__main__":
    replace_between(**dict(vars(PARSER.parse_args())))
