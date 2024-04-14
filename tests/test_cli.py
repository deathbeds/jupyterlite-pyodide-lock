"""Tests of the ``jupyter-lite`` CLI with ``jupyterlite-pyodide-lock``."""

from pathlib import Path

import pyodide_lock
import pytest
from jupyterlite_core.constants import UTF8
from jupyterlite_pyodide_kernel.constants import PYODIDE_LOCK
from jupyterlite_pyodide_lock.constants import LOCK_DATE_EPOCH

from .conftest import expect_no_diff, patch_config

MESSAGES = {
    "not-a-locker": (
        "The 'locker' trait of a PyodideLockAddon instance expected any of"
    ),
    "cant-find-wheel": "Can't find a pure python wheel",
}


@pytest.mark.parametrize("args", [["--pyodide-lock"], []])
def test_cli_status(lite_cli, args) -> None:
    """Verify various status invocations work."""
    from jupyterlite_pyodide_lock import __version__

    lite_cli(*["status", *args], expect_stdout=__version__)


@pytest.mark.parametrize(
    ["bad_config", "message"],
    [({"locker": "not-a-locker"}, "not-a-locker")],
)
def test_cli_bad_config(
    lite_cli,
    a_lite_config: Path,
    bad_config,
    message: str,
) -> None:
    patch_config(a_lite_config, PyodideLockAddon=bad_config)
    lite_cli("status", expect_rc=0, expect_stderr=MESSAGES[message])


def test_cli_good_build(lite_cli, a_lite_config_with_widgets: Path) -> None:
    """Verify a build works, twice."""
    from jupyterlite_pyodide_lock.constants import PYODIDE_LOCK_STEM

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


def test_cli_bad_build(lite_cli, a_lite_config: Path) -> None:
    """Verify an impossible package solve fails."""
    patch_config(a_lite_config, PyodideLockAddon={"enabled": True, "specs": ["torch"]})
    lite_cli("build", "--debug", expect_rc=1)


def test_cli_lock_date_epoch(
    lite_cli,
    a_widget_approach: str,
    a_lite_config_with_widgets: Path,
    a_bad_widget_lock_date_epoch: int,
    a_good_widget_lock_date_epoch: int,
) -> None:
    """Verify a lock clamped by good environment variable, failed by bad config."""
    if a_widget_approach != "specs_pep508":
        return pytest.skip(f"LOCK_DATE_EPOCH does not affect {a_widget_approach}")

    good_env = {LOCK_DATE_EPOCH: str(a_good_widget_lock_date_epoch)}
    lite_cli("build", "--debug", env=good_env)

    patch_config(
        a_lite_config_with_widgets,
        PyodideLockAddon=dict(lock_date_epoch=a_bad_widget_lock_date_epoch),
    )
    lite_cli("build", "--debug", expect_rc=1)
