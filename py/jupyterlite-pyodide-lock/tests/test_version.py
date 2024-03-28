import typing as T


def test_version(the_pyproject: T.Dict[str, T.Any]) -> None:
    from jupyterlite_pyodide_lock import __version__

    assert __version__ == the_pyproject["project"]["version"]
