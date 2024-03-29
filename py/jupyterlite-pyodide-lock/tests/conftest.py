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


@pytest.fixture
def lite(script_runner, tmp_path):
    def lite_runner(*args, **kwargs):
        kwargs["cwd"] = str(kwargs.get("cwd", tmp_path))
        return script_runner.run(["jupyter-lite", *args], **kwargs)

    return lite_runner
