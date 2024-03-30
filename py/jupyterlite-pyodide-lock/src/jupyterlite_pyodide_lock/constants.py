"""Contants for jupyterlite-pyodide-lock."""

from jupyterlite_pyodide_kernel.constants import PYODIDE_LOCK, PYODIDE_VERSION

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

#: configuration key for preloaded packages
OPTION_PACKAGES = "packages"

#: the entry point name of `PyodideAddon`
PYODIDE_ADDON = "jupyterlite-pyodide-kernel-pyodide"

#: the default fallback URL prefix for pyodide packages
PYODIDE_CDN_URL = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full"

#: the default URL for a viable pyodide distribution
PYODIDE_CORE_URL = f"https://github.com/pyodide/pyodide/releases/download/{PYODIDE_VERSION}/pyodide-core-{PYODIDE_VERSION}.tar.bz2"
