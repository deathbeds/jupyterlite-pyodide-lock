import pytest


@pytest.mark.parametrize(["args"], [(["--pyodide-lock"],), ([],)])
def test_cli_status(lite, args):
    """do various invocations work"""
    from jupyterlite_pyodide_lock import __version__

    returned_status = lite("status", *args)
    assert returned_status.success
    ours = returned_status.stdout.split("status:pyodide-lock:lock")[1]
    assert __version__ in ours
