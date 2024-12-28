"""Prose checks for ``jupyterlite-pyodide-lock``."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import mistune

HERE = Path(__file__).parent
SCRIPTS = HERE.parent
ROOT = SCRIPTS.parent
DOCS = ROOT / "docs"
BUILD = ROOT / "build"
DOCS_BUILD = BUILD / "docs"
REPORTS = BUILD / "reports"
VALE_REPORT = REPORTS / "vale.html"
SRC = ROOT / "py"
SCRIPTS = ROOT / "_scripts"
GH = ROOT / ".github"

ALL_PY = [*DOCS.rglob("*.py"), *SRC.rglob("*.py"), *SCRIPTS.rglob("*.py")]
ALL_HTML = [*DOCS_BUILD.rglob("*.html")]
ALL_MD = [*GH.rglob("*.md"), *SRC.rglob("*.md")]

CHECK_PATHS = {
    *sorted(p for p in [*ALL_PY, *ALL_HTML, *ALL_MD] if "checkpoint" not in str(p)),
}

VALE_ARGS: list[str | Path] = [
    "vale",
    *sorted(CHECK_PATHS),
    "--output=JSON",
]

TValeResults = dict[str, list[dict[str, Any]]]


def report(raw: TValeResults) -> list[str]:
    """Filter and report vale findings."""
    raw = {k: v for k, v in raw.items() if "ipynb_checkpoints" not in k}
    if not raw:
        return []
    lines: list[str] = []
    widths = [
        ":" + ("-" * (1 + max(len(r) for r in raw))),
        (5 * "-") + ":",
        (7 * "-") + ":",
        ":" + ("-" * (1 + max(len(line["Match"]) for line in sum(raw.values(), [])))),
    ]

    def line(*c: str) -> str:
        return "|".join([
            "",
            *[
                f" {c[i]} ".ljust(len(w))
                if w.startswith(":")
                else f" {c[i]} ".rjust(len(w))
                for i, w in enumerate(widths)
            ],
            "",
        ])

    lines += [
        line("file", "line", "column", "message"),
        "|".join(["", *widths, ""]),
    ]

    for path, findings in raw.items():
        for found in findings:
            lines += [line(path, found["Line"], found["Span"][0], found["Match"])]

    md = "\n".join(lines)

    print(md)
    return lines


def write_html(md_lines: list[str]) -> None:
    """Write out an HTML report."""
    VALE_REPORT.parent.mkdir(parents=True, exist_ok=True)
    html = [
        "<style>",
        "* {font-family: sans-serif}",
        "td, th {padding: 0.25em 0.5em;}",
        "</style>",
        mistune.html("\n".join(md_lines)),
    ]
    VALE_REPORT.write_text("\n".join(html), encoding="utf-8")


def main() -> int:
    """Run the checks."""
    str_args = [
        a if isinstance(a, str) else os.path.relpath(str(a), str(HERE))
        for a in VALE_ARGS
    ]
    print(">>>", " \\\n\t".join(str_args), flush=True)
    proc = subprocess.Popen(
        str_args,
        encoding="utf-8",
        cwd=str(HERE),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out = proc.communicate()[0]
    raw: TValeResults = json.loads(out)
    rc = proc.returncode
    report_lines: list[str] = []
    if raw:
        report_lines = report(raw)
        rc = len(report_lines)
    summary = f"# {len(raw)} vale issues in {len(CHECK_PATHS)} files"
    write_html([summary, "", *report_lines])
    print("\n", summary)
    return rc


if __name__ == "__main__":
    sys.exit(main())
