"""Tests of version information."""

from typing import Any


def test_version(the_pyproject: dict[str, Any]) -> None:
    """Verify the runtime version agrees with the metadata."""
    from jupyterlite_pyodide_lock import __version__

    assert __version__ == the_pyproject["project"]["version"]
