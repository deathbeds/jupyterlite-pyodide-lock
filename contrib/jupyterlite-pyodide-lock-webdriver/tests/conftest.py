"""test configuration and fixtures for ``jupyterlite-pyodide-lock-webdriver``"""

#### the below is copied from ``jupyterlite-pyodide-lock``'s ``conftest.py``
### shared fixtures ###

import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

from jupyterlite_core.constants import JSON_FMT, JUPYTER_LITE_CONFIG, UTF8
from jupyterlite_pyodide_lock.constants import FILES_PYTHON_HOSTED, PYODIDE_LOCK_STEM

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

WIDGETS_CONFIG = dict(
    specs_pep508={"specs": ["ipywidgets >=8.1,<8.2"]},
    packages_url={"packages": [WIDGETS_URL]},
    packages_local_wheel={"packages": [WIDGETS_WHEEL]},
    packages_local_folder={"packages": ["../dist"]},
    well_known={},
)


@fixture()
def the_pyproject():
    return tomllib.loads(PPT.read_text(**UTF8))


@fixture()
def a_lite_dir(tmp_path: Path):
    lite_dir = tmp_path / "lite"
    lite_dir.mkdir()
    return lite_dir


@fixture()
def lite_cli(a_lite_dir: Path):
    def run(*args, **kwargs):
        kwargs["cwd"] = str(kwargs.get("cwd", a_lite_dir))
        kwargs["encoding"] = "utf-8"
        proc = subprocess.Popen(["jupyter-lite", *args], **kwargs)
        stdout, stderr = proc.communicate()
        return proc.returncode, stdout, stderr

    return run


@fixture(params=sorted(WIDGETS_CONFIG))
def a_lite_config_with_widgets(request, a_lite_dir: Path, a_lite_config: Path) -> Path:
    approach = WIDGETS_CONFIG[request.param]

    packages = approach.get("packages")

    fetch_dest = None

    if packages:
        if WIDGETS_WHEEL in packages:
            fetch_dest = a_lite_dir / WIDGETS_WHEEL
        elif "../dist" in packages:
            fetch_dest = a_lite_dir / "../dist" / WIDGETS_WHEEL

    if not approach:
        fetch_dest = a_lite_dir / "static" / PYODIDE_LOCK_STEM

    if fetch_dest:
        fetch(WIDGETS_URL, fetch_dest)

    conf = json.loads(a_lite_config.read_text(**UTF8))
    conf["PyodideLockAddon"].update(
        extra_preload_packages=["ipywidgets"],
        **(approach or {}),
    )

    a_lite_config.write_text(json.dumps(conf, **JSON_FMT), **UTF8)
    return a_lite_config


def fetch(url: str, dest: Path):
    with urllib.request.urlopen(url) as response:  # noqa: S310
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as fd:
            shutil.copyfileobj(response, fd)


### shared fixtures ###
#### the above is copied from ``jupyterlite-pyodide-lock``'s ``conftest.py``


@fixture()
def a_lite_config(a_lite_dir: Path) -> Path:
    conf = a_lite_dir / JUPYTER_LITE_CONFIG
    conf.write_text(
        json.dumps(
            {
                "PyodideLockAddon": {"enabled": True, "locker": "webdriver"},
            },
            **JSON_FMT,
        ),
        **UTF8,
    )
    return conf
