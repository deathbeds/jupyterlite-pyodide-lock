"""Test configuration and fixtures for ``jupyterlite-pyodide-lock-webdriver``."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

from __future__ import annotations

# the below is copied from ``jupyterlite-pyodide-lock``'s ``conftest.py``
# shared fixtures ###
import difflib
import json
import os
import pprint
import shutil
import subprocess
import sys
import textwrap
import time
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, Any

import psutil
from jupyterlite_core.constants import JSON_FMT, JUPYTER_LITE_CONFIG, UTF8

from jupyterlite_pyodide_lock import constants as C  # noqa: N812
from jupyterlite_pyodide_lock.utils import (
    get_unused_port,
    terminate_all,
    warehouse_date_to_epoch,
)

try:
    import tomllib
except ImportError:
    import tomli as tomllib


import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

    from selenium.webdriver import Firefox
    from selenium.webdriver.remote.webelement import WebElement

    TLiteRunResult = tuple[int, str | None]


HERE = Path(__file__).parent
PKG = HERE.parent
PPT = PKG / "pyproject.toml"

PY_HOSTED = "https://files.pythonhosted.org/packages/py3"
LITE_BUILD_CONFIG = {
    "LiteBuildConfig": {
        "federated_extensions": [
            f"{PY_HOSTED}/j/jupyterlab-widgets/jupyterlab_widgets-3.0.10-py3-none-any.whl"
        ]
    }
}

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

#: a notebook without cells
EMPTY_NOTEBOOK = {
    "metadata": {
        "kernelspec": {
            "display_name": "Python (Pyodide)",
            "language": "python",
            "name": "python",
        },
        "language_info": {
            "codemirror_mode": {"name": "ipython", "version": 3},
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3",
            "version": "3.12.8",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

CSS_RUN_BUTTON = (
    ".jp-ToolbarButtonComponent[data-command='notebook:run-cell-and-select-next']"
)
EXPECT_WIDGETS_RUN = (
    "from ipywidgets import FloatSlider; FloatSlider()",
    ".jupyter-widgets.widget-slider",
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


class LiteRunner:
    """A wrapper for common CLI test activities."""

    lite_dir: Path
    next_screen: int
    next_run: int
    _ff: Firefox | None = None

    def __init__(self, lite_dir: Path) -> None:
        """Store the project for later."""
        self.lite_dir = lite_dir
        self.next_screen = 0
        self.next_run = 0

    @property
    def run_dir(self) -> Path:
        """Get a path for this run's data."""
        return self.lite_dir.parent / f"cli-{self.next_run}"

    @property
    def geckodriver_log(self) -> Path:
        """Get a log location."""
        return self.run_dir / "geckodriver.log"

    @property
    def ff(self) -> Firefox:
        """Get Firefox, or die trying."""
        if not self._ff:
            msg = "Firefox not initialized"
            raise ValueError(msg)
        return self._ff

    def __call__(
        self,
        *args: str,
        expect_rc: int = 0,
        expect_text: str | None = None,
        expect_runnable: list[tuple[str, str]] | None = None,
        **popen_kwargs: Any,
    ) -> TLiteRunResult:
        """Run a CLI command, optionally checking stream and/or web output."""
        self.next_run += 1
        self.run_dir.mkdir(parents=True, exist_ok=True)
        out_dir = self.lite_dir / "_output"
        cache_dir = self.lite_dir / ".cache"
        if out_dir.exists():
            shutil.rmtree(out_dir)
        if expect_runnable:
            # lab extensions don't get re-added
            shutil.rmtree(cache_dir, ignore_errors=True)
            [[p.unlink(), 1] for p in self.lite_dir.glob("*doit*")]
        a_lite_config = self.lite_dir / JUPYTER_LITE_CONFIG
        env = dict(os.environ)

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
            env.update(popen_kwargs.pop("env"))

        env["JUPYTERLITE_NO_JUPYTERLAB_SERVER"] = "1"

        if expect_runnable:
            self.make_notebook(expect_runnable)

        if a_lite_config.exists():
            run_conf = self.run_dir / a_lite_config.name
            print(f"... copying config to {run_conf}", file=sys.stderr)
            shutil.copy2(a_lite_config, run_conf)

        log = self.run_dir / "cli.log.txt"
        print(f"... writing log to {log}", file=sys.stderr)

        with log.open("w", **UTF8) as log_fp:
            kwargs = dict(
                cwd=str(popen_kwargs.get("cwd", self.lite_dir)),
                stdout=log_fp,
                stderr=subprocess.STDOUT,
                env=env,
                **UTF8,
            )
            kwargs.update(**popen_kwargs)
            proc = psutil.Popen(["jupyter-lite", *args], **kwargs)
            proc.communicate()

        if expect_rc is not None:
            print("[rc]", proc.returncode)
            assert proc.returncode == expect_rc

        if expect_text:
            text = log.read_text(**UTF8)
            assert expect_text in text

        if expect_runnable:
            self.run_web(expect_runnable)

        return proc.returncode, log.read_text(**UTF8)

    def make_notebook(self, expect_runnable: list[tuple[str, str]]) -> None:
        """Write a test notebook with the expected code."""
        files = self.lite_dir / "files"
        nb = files / "test.ipynb"
        cells = [
            {"cell_type": "code", "source": code} for code, _css in expect_runnable
        ]
        nb_content = {"cells": cells, **EMPTY_NOTEBOOK}
        nb.parent.mkdir(exist_ok=True, parents=True)
        nb.write_text(json.dumps(nb_content), **UTF8)

    def capture(self, prefix: str = "test") -> None:
        """Capture a screenshot."""
        path = self.run_dir / f"{self.next_screen:02}-{prefix}.png"
        print(f"... screenshot {path}", file=sys.stderr)
        self.ff.get_full_page_screenshot_as_file(str(path))
        self.next_screen += 1

    def run_web(self, expect_runnable: list[tuple[str, str]]) -> None:
        """Serve the site to Firefox, run some Python, check for a selector."""
        from jupyterlite_pyodide_lock.constants import WIN

        if WIN:
            sys.stderr.write("Not trying on windows\n")
            return
        out = self.lite_dir / "_output"
        out_nb = out / "files/test.ipynb"
        assert (out / "api/contents/all.json").exists()
        assert out_nb.exists()
        port = get_unused_port()
        srv_args = [sys.executable, "-m", "http.server", "-b", C.LOCALHOST, port]
        log = self.run_dir / "http.log.txt"
        with log.open("w", **UTF8) as log_fp:
            srv = psutil.Popen(
                [*map(str, srv_args)],
                cwd=str(out),
                stdout=log_fp,
                stderr=subprocess.STDOUT,
            )

            self.make_firefox()

            url = f"http://{C.LOCALHOST}:{port}/lab/index.html?path=test.ipynb"

            try:
                self.run_with_server(url, expect_runnable)
            finally:
                if self._ff:
                    self._ff.quit()
                self._ff = None
                terminate_all(srv)

    def run_with_server(self, url: str, expect_runnable: list[tuple[str, str]]) -> None:
        """Run the server."""
        self.ff.get(url)
        time.sleep(5)
        self.capture("startup")
        try:
            run = self.wait_for_element(CSS_RUN_BUTTON)
            self.capture()
            for i, (_code, selector) in enumerate(expect_runnable):
                run.click()
                if not i:
                    time.sleep(20)
                self.wait_for_element(selector)
                self.capture()
        except Exception as err:  # noqa: BLE001
            print(err, file=sys.stderr)
            self.capture("error")

    def wait_for_element(self, css: str, timeout: int = 30) -> WebElement:
        """Wait for a CSS element to appear."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC  # noqa: N812
        from selenium.webdriver.support.wait import WebDriverWait

        return WebDriverWait(self.ff, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, css))
        )

    def make_firefox(self) -> None:
        """Make a firefox webdriver."""
        import selenium.webdriver as SE  # noqa: N812

        ff_bin = shutil.which("firefox") or shutil.which("firefox.exe")
        gd_bin = shutil.which("geckodriver") or shutil.which("geckodriver.exe")
        if not (ff_bin and gd_bin):
            msg = f"can't find one of:  firefox: {ff_bin}  geckodriver: {gd_bin}"
            raise FileNotFoundError(msg)
        options = SE.FirefoxOptions()
        options.set_preference("devtools.console.stdout.content", value=True)
        options.binary_location = ff_bin
        service = SE.FirefoxService(
            executable_path=gd_bin,
            log_output=str(self.geckodriver_log),
            service_args=["--log", "trace"],
            env={"MOZ_HEADLESS": "1"},
        )
        self._ff = SE.Firefox(options=options, service=service)


@pytest.fixture(scope="session")
def the_pyproject() -> dict[str, Any]:
    """Provide the python project data."""
    return dict(tomllib.loads(PPT.read_text(**UTF8)))


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
def lite_cli(a_lite_dir: Path) -> LiteRunner:
    """Provide a ``jupyter lite`` runner in a project."""
    return LiteRunner(a_lite_dir)


@pytest.fixture(params=sorted(WIDGETS_CONFIG))
def a_widget_approach(request: pytest.FixtureRequest) -> str:
    """Provide a key for which ``ipywidgets`` lock approach to try."""
    return f"{request.param}"


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
        PyodideLockAddon=dict(**(approach or {})),
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
    old_text = json.dumps(config, **JSON_FMT)
    for cls_name, values in configurables.items():
        config.setdefault(cls_name, {}).update(values)
    new_text = json.dumps(config, **JSON_FMT)
    config_path.write_text(new_text, **UTF8)
    print("patched config")
    print(simple_diff(OLD=old_text, NEW=new_text))
    return config_path


def fetch(url: str, dest: Path) -> None:
    """Download a file to a destination path, creating its parent folder if needed."""
    with urllib.request.urlopen(url) as response:  # noqa: S310
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as fd:
            shutil.copyfileobj(response, fd)


def simple_diff(**paths: str) -> str:
    """Get the string of the diff two texts."""
    ((left, left_text), (right, right_text)) = [*paths.items()]

    diff = [
        *difflib.unified_diff(
            left_text.strip().splitlines(),
            right_text.strip().splitlines(),
            left,
            right,
        ),
    ]
    return "\n".join(diff)


def expect_no_diff(left_text: str, right_text: str, left: str, right: str) -> None:
    """Verify two texts contain no differences."""
    diff = simple_diff(**{left: left_text, right: right_text})
    assert not diff


# shared fixtures ###
# the above is copied from ``jupyterlite-pyodide-lock``'s ``conftest.py``


@pytest.fixture
def a_lite_config(a_lite_dir: Path) -> Path:
    """Provide a configured ``jupyter_lite_config.json``."""
    config = a_lite_dir / JUPYTER_LITE_CONFIG

    patch_config(
        config,
        PyodideLockAddon=dict(enabled=True, locker="WebDriverLocker"),
        **LITE_BUILD_CONFIG,
    )

    if (
        C.LINUX
        and os.environ.get("CI")
        and os.environ.get("JLPL_BROWSER") in C.CHROMIUMLIKE
    ):
        print("patching chromium-like args to avoid segfaults")
        patch_config(
            config,
            WebDriverLocker=dict(
                webdriver_option_arguments=[
                    C.CHROMIUM_NO_SANDBOX,
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ]
            ),
        )

    return config
