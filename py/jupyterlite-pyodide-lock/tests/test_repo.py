"""Tests of repo versions, etc."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

from __future__ import annotations

import re

import pytest

from .conftest import ROOT, UTF8

PIXI_PATTERNS = {
    ".github/workflows/*.yml": [r"JLPL_PIXI_VERSION: ([^\s]+)"],
    "docs/environment.yml": [r"""pixi ==([^\s"']+)"""],
    "CONTRIBUTING.md": [r"""pixi ==([^\s"']+)"""],
}

PY_PATTERNS = {
    "py/*/pyproject.toml": [r"""version = "([^"]+)"""],
    "CHANGELOG.md": [
        r"""## `([\d\.abcr]+?)`""",
        r"""## `jupyterlite-pyodide-lock ([\d\.abcr]+?)`""",
        r"""## `jupyterlite-pyodide-lock-webdriver ([\d\.abcr]+?)`""",
    ],
}


@pytest.mark.parametrize(("glob"), PIXI_PATTERNS.keys())
def test_repo_pixi_version(the_pixi_version: str, glob: str) -> None:
    """Verify consistent ``pixi`` versions."""
    _verify_patterns("python version", the_pixi_version, glob, PIXI_PATTERNS)


@pytest.mark.parametrize(("glob"), PY_PATTERNS.keys())
def test_repo_py_version(the_py_version: str, glob: str) -> None:
    """Verify consistent ``jupyterlite-pyodide-lock`` versions."""
    _verify_patterns("python version", the_py_version, glob, PY_PATTERNS)


def _verify_patterns(
    what: str, version: str, glob: str, patterns: dict[str, list[str]]
) -> None:
    """Verify some versions against glob patterns."""
    paths = sorted(ROOT.glob(glob))
    assert paths, f"no paths matched {glob}"
    for path in paths:
        text = path.read_text(**UTF8)
        print(text)
        for pattern in patterns[glob]:
            matches = re.findall(pattern, text)
            assert {*matches} == {version}, (
                f"{what} {version} is missing from {path.relative_to(ROOT)}"
            )
