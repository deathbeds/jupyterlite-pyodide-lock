from jupyterlite_pyodide_lock import __version__
from jupyterlite_pyodide_lock.constants import NAME

LITE = ["jupyter", "lite"]


def test_cli_status(script_runner):
    """do various invocations work"""
    returned_status = script_runner.run([*LITE, "status"])
    assert returned_status.success
    ours = returned_status.stdout.split(NAME)[1]
    assert __version__ in returned_status.stdout
