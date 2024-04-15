"""Tests of the ``jupyter-lite`` CLI with ``jupyterlite-pyodide-lock-webdriver``."""

import os
from pathlib import Path

import pyodide_lock
import pytest
from jupyterlite_core.constants import UTF8
from jupyterlite_pyodide_kernel.constants import PYODIDE_LOCK
from jupyterlite_pyodide_lock.constants import CHROMIUM, ENV_VAR_BROWSER

from .conftest import expect_no_diff


def test_cli_good_build(lite_cli, a_lite_config_with_widgets: Path) -> None:
    """Verify a build works, twice."""
    from jupyterlite_pyodide_lock.constants import PYODIDE_LOCK_STEM

    if os.environ.get("CI") and os.environ.get(ENV_VAR_BROWSER) == CHROMIUM:
        return pytest.skip("'chromedriver' doesn't work with 'chromium' on CI")

    a_lite_dir = a_lite_config_with_widgets.parent
    out = a_lite_dir / "_output"
    lock_dir = out / "static" / PYODIDE_LOCK_STEM
    lock = lock_dir / PYODIDE_LOCK

    lite_cli("build", "--debug")
    lock_text = lock.read_text(**UTF8)

    # this would fail pydantic
    pyodide_lock.PyodideLockSpec.from_json(lock)

    lite_cli("build", "--debug")
    relock_text = lock.read_text(**UTF8)

    expect_no_diff(lock_text, relock_text, "build", "rebuild")
