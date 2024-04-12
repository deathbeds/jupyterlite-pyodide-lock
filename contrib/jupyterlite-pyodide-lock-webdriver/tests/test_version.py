from typing import Any


def test_version(the_pyproject: dict[str, Any]) -> None:
    from jupyterlite_pyodide_lock_webdriver import __version__

    assert __version__ == the_pyproject["project"]["version"]
