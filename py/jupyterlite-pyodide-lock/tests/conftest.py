"""Test configuration and fixtures for ``jupyterlite-pyodide-lock``."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

from __future__ import annotations

# the below is copied to ``contrib`` packages
# shared fixtures ###
import difflib
import json
import os
import pprint
import shutil
import subprocess
import textwrap
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jupyterlite_core.constants import JSON_FMT, JUPYTER_LITE_CONFIG, UTF8

from jupyterlite_pyodide_lock import constants as C  # noqa: N812
from jupyterlite_pyodide_lock.utils import warehouse_date_to_epoch

try:
    import tomllib
except ImportError:
    import tomli as tomllib


import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

    TLiteRunResult = tuple[int, str | None, str | None]

    def t_lite_runner(
        *args: str,
        expect_rc: int = 0,
        expect_stderr: str | None = None,
        expect_stdout: str | None = None,
        **popen_kwargs: Any,
    ) -> TLiteRunResult:
        """Provide a type for the ``lite_cli`` fixture."""
        print(args, expect_rc, expect_stderr, expect_stdout, popen_kwargs)
        return 0, None, None

    TLiteRunner = type[t_lite_runner]


HERE = Path(__file__).parent
PKG = HERE.parent
PPT = PKG / "pyproject.toml"

WIDGETS_WHEEL = "ipywidgets-8.1.2-py3-none-any.whl"
WIDGETS_URL = f"{C.FILES_PYTHON_HOSTED}/packages/py3/i/ipywidgets/{WIDGETS_WHEEL}"
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


def pytest_configure(config: Any) -> None:
    """Configure the pytest environment."""
    try:
        from pytest_metadata.plugin import metadata_key
    except ImportError:
        return

    config.stash[metadata_key].pop("JAVA_HOME", None)

    for k in sorted([*os.environ, *C.ENV_VAR_ALL]):
        if k.startswith("JLPL_") or k.startswith("JUPYTERLITE_"):  # noqa: PIE810
            config.stash[metadata_key][k] = os.environ.get(k, "")
    return


@pytest.fixture(scope="session")
def the_pyproject() -> dict[str, Any]:
    """Provide the python project data."""
    return tomllib.loads(PPT.read_text(**UTF8))


@pytest.fixture
def a_lite_dir(tmp_path: Path) -> Path:
    """Provide a temporary JupyterLite project."""
    lite_dir = tmp_path / "lite"
    lite_dir.mkdir()
    return lite_dir


@pytest.fixture
def a_bad_widget_lock_date_epoch() -> int:
    """Provide a UNIX timestamp for a widget release that should NOT be in a lock."""
    return warehouse_date_to_epoch(WIDGET_ISO8601["before"])


@pytest.fixture
def a_good_widget_lock_date_epoch() -> int:
    """Provide a UNIX timestamp for a widget release that should be in a lock."""
    return warehouse_date_to_epoch(WIDGET_ISO8601["after_"])


@pytest.fixture
def lite_cli(a_lite_dir: Path) -> TLiteRunner:
    """Provide a ``jupyter lite`` runner in a project."""

    def run(
        *args: str,
        expect_rc: int = 0,
        expect_stderr: str | None = None,
        expect_stdout: str | None = None,
        **popen_kwargs: Any,
    ) -> TLiteRunResult:
        a_lite_config = a_lite_dir / JUPYTER_LITE_CONFIG
        env = None

        print(
            "[env] well-known:\n",
            pprint.pformat({
                k: os.getenv(k)
                for k in sorted(os.environ)
                if k.startswith(("JLPL_", "JUPYTERLITE_"))
            }),
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


@pytest.fixture(params=sorted(WIDGETS_CONFIG))
def a_widget_approach(request: pytest.FixtureRequest) -> str:
    """Provide a key for which ``ipywidgets`` lock approach to try."""
    return request.param


@pytest.fixture
def a_lite_config_with_widgets(
    a_lite_dir: Path, a_lite_config: Path, a_widget_approach: str
) -> Generator[Path, None, None]:
    """Patch a lite project to use ``ipywidgets``."""
    approach = WIDGETS_CONFIG[a_widget_approach]

    packages = approach.get("packages")

    fetch_dest = None

    if packages:
        if WIDGETS_WHEEL in packages:
            fetch_dest = a_lite_dir / WIDGETS_WHEEL
        elif "../dist" in packages:
            fetch_dest = a_lite_dir / "../dist" / WIDGETS_WHEEL

    if not approach:
        fetch_dest = a_lite_dir / "static" / C.PYODIDE_LOCK_STEM

    if fetch_dest:
        fetch(WIDGETS_URL, fetch_dest)

    patch_config(
        a_lite_config,
        PyodideLockAddon=dict(
            extra_preload_packages=["ipywidgets"],
            **(approach or {}),
        ),
    )

    yield a_lite_config

    for log_path in a_lite_dir.glob("*.log"):
        print(log_path)
        print(textwrap.indent(log_path.read_text(**UTF8), "\t"))


def patch_config(config_path: Path, **configurables: dict[str, Any]) -> Path:
    """Patch a Jupyter JSON configuration file."""
    config = {}
    if config_path.exists():
        config = json.loads(config_path.read_text(**UTF8))
    for cls_name, values in configurables.items():
        config.setdefault(cls_name, {}).update(values)
    json_text = json.dumps(config, **JSON_FMT)
    config_path.write_text(json_text, **UTF8)
    print("patched config")
    print(json_text)
    return config_path


def fetch(url: str, dest: Path) -> None:
    """Download a file to a destination path, creating its parent folder if needed."""
    with urllib.request.urlopen(url) as response:  # noqa: S310
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as fd:
            shutil.copyfileobj(response, fd)


def expect_no_diff(left_text: Path, right_text: Path, left: str, right: str) -> None:
    """Verify two texts contain no differences."""
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


# shared fixtures ###
# the above is copied to ``contrib`` packages

ROOT = PKG.parent.parent
PXT = ROOT / "pixi.toml"


@pytest.fixture(scope="session")
def the_pixi_manifest() -> dict[str, Any]:
    """Provide the the pixi manifest data."""
    return tomllib.loads(PXT.read_text(**UTF8))


@pytest.fixture(scope="session")
def the_pixi_version(the_pixi_manifest: dict[str, Any]) -> str:
    """Provide the source of truth for the pixi version."""
    import re

    return re.findall(r"/v(.*?)/", the_pixi_manifest["$schema"])[0]


@pytest.fixture(scope="session")
def the_py_version(the_pyproject: dict[str, Any]) -> str:
    """Provide the source of truth for the python version."""
    return the_pyproject["project"]["version"]


@pytest.fixture
def a_lite_config(a_lite_dir: Path) -> Path:
    """Provide a configured ``jupyter_lite_config.json``."""
    config = a_lite_dir / JUPYTER_LITE_CONFIG

    patch_config(
        config,
        PyodideLockAddon=dict(enabled=True),
        BrowserLocker=dict(temp_profile=True),
    )

    if (
        C.LINUX
        and os.environ.get("CI")
        and os.environ.get("JLPL_BROWSER") in C.CHROMIUMLIKE
    ):
        print("patching chromium-like args to avoid segfaults")
        patch_config(
            config,
            BrowserLocker=dict(extra_browser_argv=[C.CHROMIUM_NO_SANDBOX]),
        )

    return config
