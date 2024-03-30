"""Contants for jupyterlite-pyodide-lock."""

from jupyterlite_pyodide_kernel.constants import PYODIDE_LOCK

__all__ = ["NAME", "LOCKER_ENTRYPOINT", "PYODIDE_LOCK_STEM", "PROXY", "LOCK_HTML"]

#: this distribution name
NAME = "jupyterlite-pyodide-lock"

#: the entry point name for locker implementations
LOCKER_ENTRYPOINT = f"{NAME}.locker.v0"

#: a base name for lock-related filesssss
PYODIDE_LOCK_STEM = PYODIDE_LOCK.split(".")[0]

#: the URL prefix for proxies
PROXY = "_proxy"

#: the name of the hosted HTML app
LOCK_HTML = "lock.html"

#: configuration key for the loadPyodide options
LOAD_PYODIDE_OPTIONS = "loadPyodideOptions"

#: configuration key for the lockfile URL
OPTION_LOCK_FILE_URL = "lockFileURL"
