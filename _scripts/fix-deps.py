"""fix dependencies."""

import sys
from argparse import ArgumentParser
from pathlib import Path

from tomli_w import dumps

try:
    from tomllib import loads
except ImportError:
    from tomli import loads

PARSER = ArgumentParser()
PARSER.add_argument("upstream", type=Path)
PARSER.add_argument("downstream", type=Path)

UTF8 = dict(encoding="utf-8")


def fix_deps(
    upstream: Path,
    downstream: Path,
) -> int:
    """Replace a pyproject.toml dependency from an upstream."""
    up = loads(upstream.read_text(**UTF8))
    up_version = up["project"]["version"]
    up_name = up["project"]["name"]
    new_spec = f"{up_name} =={up_version}"
    down = loads(downstream.read_text(**UTF8))

    for i, spec in enumerate(down["project"]["dependencies"]):
        if spec.split(" ")[0] != up_name:
            continue
        if spec != new_spec:
            down["project"]["dependencies"][i] = new_spec
            downstream.write_text(dumps(down), **UTF8)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(fix_deps(**dict(vars(PARSER.parse_args()))))
