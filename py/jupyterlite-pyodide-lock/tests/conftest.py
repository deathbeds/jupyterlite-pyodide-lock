from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

import pytest

HERE = Path(__file__).parent
ROOT = HERE.parent
PPT = ROOT / "pyproject.toml"


@pytest.fixture
def the_pyproject():
    return tomllib.load(PPT.open("rb"))
