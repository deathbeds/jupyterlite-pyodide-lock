"""test configuration and fixtures for `jupyterlite-pyodide-lock`"""

import json
import shutil
import urllib.request
from pathlib import Path

from jupyterlite_core.constants import JSON_FMT, JUPYTER_LITE_CONFIG, UTF8
from jupyterlite_pyodide_lock.constants import FILES_PYTHON_HOSTED

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from pytest import fixture

HERE = Path(__file__).parent
ROOT = HERE.parent
PPT = ROOT / "pyproject.toml"

WIDGETS_WHEEL = "ipywidgets-8.1.2-py3-none-any.whl"
WIDGETS_URL = f"{FILES_PYTHON_HOSTED}/packages/py3/i/ipywidgets/{WIDGETS_WHEEL}"

WIDGETS_CONFIG = [
    {"specs": ["ipywidgets >=8.1,<8.2"]},
    {"packages": [WIDGETS_URL]},
    {"packages": [WIDGETS_WHEEL]},
    {"packages": ["../dist"]},
]


@fixture
def the_pyproject():
    return tomllib.load(PPT.open("rb"))


@fixture
def a_lite_dir(tmp_path: Path):
    lite_dir = tmp_path / "lite"
    lite_dir.mkdir()
    return lite_dir


@fixture
def lite_cli(script_runner, a_lite_dir: Path):
    def lite_runner(*args, **kwargs):
        kwargs["cwd"] = str(kwargs.get("cwd", a_lite_dir))
        return script_runner.run(["jupyter-lite", *args], **kwargs)

    return lite_runner


@fixture
def a_lite_config(a_lite_dir: Path) -> Path:
    conf = a_lite_dir / JUPYTER_LITE_CONFIG
    conf.write_text(
        json.dumps(
            {
                "PyodideLockAddon": {
                    "enabled": True,
                }
            },
            **JSON_FMT,
        ),
        **UTF8,
    )
    return conf


@fixture(params=WIDGETS_CONFIG)
def a_lite_config_with_widgets(request, a_lite_dir: Path, a_lite_config: Path) -> Path:
    packages = request.param.get("packages")
    if packages:
        dest = None
        if WIDGETS_WHEEL in packages:
            dest = a_lite_dir / WIDGETS_WHEEL
        elif "../dist" in packages:
            dest = a_lite_dir / "../dist" / WIDGETS_WHEEL
        if dest:
            fetch(WIDGETS_URL, dest)

    a_lite_config.write_text(
        json.dumps(
            {
                "PyodideLockAddon": {
                    "enabled": True,
                    "extra_preload_packages": ["ipywidgets"],
                    **request.param,
                }
            },
            **JSON_FMT,
        ),
        **UTF8,
    )
    return a_lite_config


def fetch(url: str, dest: Path):
    with urllib.request.urlopen(url) as response:  # noqa: S310
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as fd:
            shutil.copyfileobj(response, fd)
