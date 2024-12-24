"""Clean up notebooks by removing outputs, execution counts, and empty cells."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

import sys
from argparse import ArgumentParser
from pathlib import Path

import nbformat

UTF8 = dict(encoding="utf-8")
NL_LF = dict(newline="\n")
PARSER = ArgumentParser()
PARSER.add_argument("--fix", action="store_true")
PARSER.add_argument("roots", type=Path, nargs="*")


def lint_one(nb_path: Path, fix: bool) -> list[str]:
    """Fix/lint one notebook."""
    old_text = nb_path.read_text(**UTF8).strip()
    nb = nbformat.reads(old_text, as_version=4)
    new_cells = []

    for cell in nb.cells:
        if hasattr(cell, "outputs"):
            cell.outputs = []
            cell.execution_count = None
        if cell.source.strip() != "":
            new_cells += [cell]

    nb.cells = new_cells

    new_text = nbformat.writes(nb).strip()
    if old_text == new_text:
        return []
    if fix:
        nb_path.write_text(new_text + "\n", **UTF8, **NL_LF)
        return []
    return [f"- {nb_path} needs fixing"]


def main(fix: bool, roots: list[Path]) -> int:
    """Loop over all the notebooks in all the roots."""
    errors = []
    for root in roots:
        for nb_path in sorted(root.rglob("*.ipynb")):
            if "ipynb_checkpoints" in str(nb_path):
                continue
            errors += lint_one(nb_path, fix)

    if errors:
        print("\n".join(["", *errors, "", "please run:\n\n\tpixi run fix\n"]))

    return len(errors)


if __name__ == "__main__":
    sys.exit(main(**dict(vars(PARSER.parse_args()))))
