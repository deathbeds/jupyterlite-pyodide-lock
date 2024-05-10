"""test configuration and fixtures for ``jupyterlite-pyodide-lock-webdriver``"""

#### the below is copied from ``jupyterlite-pyodide-lock``'s ``conftest.py``
### shared fixtures ###
import difflib
import json
import os
import shutil
from typing import Any
import subprocess
import urllib.request
from pathlib import Path

from jupyterlite_core.constants import JSON_FMT, JUPYTER_LITE_CONFIG, UTF8
from jupyterlite_pyodide_lock.constants import (
    ENV_VAR_ALL,
    FILES_PYTHON_HOSTED,
    PYODIDE_LOCK_STEM,
)
from jupyterlite_pyodide_lock.utils import warehouse_date_to_epoch

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
WIDGET_ISO8601 = dict(
    before="2024-02-08T15:31:28Z",
    actual="2024-02-08T15:31:29.801655Z",
    after_="2024-02-08T15:31:31Z",
)

WIDGETS_CONFIG = dict(
    specs_pep508={"specs": ["ipywidgets >=8.1.2,<8.1.3"]},
    packages_url={"packages": [WIDGETS_URL]},
    packages_local_wheel={"packages": [WIDGETS_WHEEL]},
    packages_local_folder={"packages": ["../dist"]},
    well_known={},
)


def pytest_configure(config):
    from pytest_metadata.plugin import metadata_key

    config.stash[metadata_key].pop("JAVA_HOME", None)

    for k in sorted([*os.environ, *ENV_VAR_ALL]):
        if k.startswith("JLPL_") or k.startswith("JUPYTERLITE_"):
            config.stash[metadata_key][k] = os.environ.get(k, "")


@fixture(scope="session")
def the_pyproject():
    return tomllib.loads(PPT.read_text(**UTF8))


@fixture()
def a_lite_dir(tmp_path: Path):
    lite_dir = tmp_path / "lite"
    lite_dir.mkdir()
    return lite_dir


@fixture()
def a_bad_widget_lock_date_epoch() -> int:
    return warehouse_date_to_epoch(WIDGET_ISO8601["before"])


@fixture()
def a_good_widget_lock_date_epoch() -> int:
    return warehouse_date_to_epoch(WIDGET_ISO8601["after_"])


@fixture()
def lite_cli(a_lite_dir: Path):
    def run(*args, expect_rc=0, expect_stderr=None, expect_stdout=None, **popen_kwargs):
        a_lite_config = a_lite_dir / JUPYTER_LITE_CONFIG
        env = None

        print(
            "[env] well-known:",
            {
                k: v
                for k, v in sorted(os.environ.items())
                if k.startswith("JLPL_") or k.startswith("JUPYTERLITE_")
            },
        )

        if "env" in popen_kwargs:
            print("[env] custom:", env)
            env = dict(os.environ)
            env.update(popen_kwargs.pop("env"))

        kwargs = dict(
            cwd=str(popen_kwargs.get("cwd", a_lite_dir)),
            stdout=subprocess.PIPE if expect_stdout else None,
            stderr=subprocess.PIPE if expect_stderr else None,
            env=env,
            **UTF8,
        )
        kwargs.update(**popen_kwargs)

        a_lite_config.exists() and print(
            "[config]",
            a_lite_config,
            a_lite_config.read_text(**UTF8),
            flush=True,
        )

        proc = subprocess.Popen(["jupyter-lite", *args], **kwargs)
        stdout, stderr = proc.communicate()

        if expect_rc is not None:
            print("[rc]", proc.returncode)
            assert proc.returncode == expect_rc
        if expect_stdout:
            print("[stdout]", stdout)
            assert expect_stdout in stdout
        if expect_stderr:
            print("[stderr]", stderr)
            assert expect_stderr in stderr

        return proc.returncode, stdout, stderr

    return run


@fixture(params=sorted(WIDGETS_CONFIG))
def a_widget_approach(request):
    return request.param


@fixture()
def a_lite_config_with_widgets(
    a_lite_dir: Path, a_lite_config: Path, a_widget_approach: str
) -> Path:
    approach = WIDGETS_CONFIG[a_widget_approach]

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

    patch_config(
        a_lite_config,
        PyodideLockAddon=dict(
            extra_preload_packages=["ipywidgets"],
            **(approach or {}),
        ),
    )

    return a_lite_config


def patch_config(config_path: Path, **configurables):
    config = {}
    if config_path.exists():
        config = json.loads(config_path.read_text(**UTF8))
    for cls_name, values in configurables.items():
        config.setdefault(cls_name, {}).update(values)
    config_path.write_text(json.dumps(config, **JSON_FMT), **UTF8)
    return config_path


def fetch(url: str, dest: Path):
    with urllib.request.urlopen(url) as response:  # noqa: S310
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as fd:
            shutil.copyfileobj(response, fd)


def expect_no_diff(left_text: Path, right_text: Path, left: str, right: str):
    diff = [
        *difflib.unified_diff(
            left_text.strip().splitlines(),
            right_text.strip().splitlines(),
            left,
            right,
        ),
    ]
    print("\n".join(diff))
    assert not diff


### shared fixtures ###
#### the above is copied from ``jupyterlite-pyodide-lock``'s ``conftest.py``


@fixture()
def a_lite_config(a_lite_dir: Path) -> Path:
    return patch_config(
        a_lite_dir / JUPYTER_LITE_CONFIG,
        PyodideLockAddon=dict(enabled=True, locker="WebDriverLocker"),
    )


def pytest_html_report_title(report):
    report.title = "jupyterlite-pyodide-lock-webdriver"
