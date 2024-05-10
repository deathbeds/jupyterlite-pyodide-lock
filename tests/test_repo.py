from pathlib import Path

import pytest
import re

from .conftest import HERE, ROOT, UTF8

PIXI_PATTERNS = {
    ".github/workflows/*.yml": r"JLPL_PIXI_VERSION: ([^\s]+)",
    "docs/.readthedocs.yml": r"pixi==([^\s]+)",
    "CONTRIBUTING.md": r"pixi==([^\s]+)",
}

@pytest.mark.parametrize(("glob"), PIXI_PATTERNS.keys())
def test_repo_pixi_version(the_pixi_version: str, glob: str):
    paths = sorted(ROOT.glob(glob))
    assert paths
    for path in paths:
        pattern = PIXI_PATTERNS[glob]
        text = path.read_text(**UTF8)
        matches = re.findall(pattern, text)
        assert {the_pixi_version} == {*matches}, \
            f"pixi {the_pixi_version} is missing from {path.relative_to(ROOT)}"
