"""Contants for jupyterlite-pyodide-lock."""

import os

from jupyterlite_pyodide_kernel.constants import PYODIDE_LOCK, PYODIDE_VERSION

__all__ = ["NAME", "LOCKER_ENTRYPOINT", "PYODIDE_LOCK_STEM", "PROXY", "LOCK_HTML"]

#: this distribution name
NAME = "jupyterlite-pyodide-lock"

#: environment variable for setting the timeout
ENV_VAR_TIMEOUT = "JUPYTERLITE_PYODIDE_LOCK_TIMEOUT"

#: the entry point name for locker implementations
LOCKER_ENTRYPOINT = f"{NAME.replace('-', '_')}.locker.v0"

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

#: the URL for the pyodide project
PYODIDE_GH = "https://github.com/pyodide/pyodide"

#: the default URL for a viable pyodide distribution
PYODIDE_CORE_URL = f"{PYODIDE_GH}/releases/download/{PYODIDE_VERSION}/pyodide-core-{PYODIDE_VERSION}.tar.bz2"

#: the default URL for python wheels
FILES_PYTHON_HOSTED = "https://files.pythonhosted.org"

#: browser CLI args, keyed by configurable
BROWSERS = {
    "firefox": {
        "launch": ["firefox"],
        "headless": ["--headless"],
        "private_mode": ["--private-window"],
        "profile": ["--new-instance", "--profile", "{PROFILE_DIR}"],
    },
    "chromium": {
        "launch": ["chromium-browser", "--new-window"],
        # doesn't appear to work
        # "headless": ["--headless"],
        "private_mode": ["--incognito"],
        "profile": ["--user-data-dir={PROFILE_DIR}"],
    },
}

#: is this windows
WIN = os.sys.platform[:3] == "win"

#: default locations of Program Files on Windows
WIN_PROGRAM_FILES_DIRS = {
    "PROGRAMFILES(x86)": "C:\\Program Files (x86)",
    "PROGRAMFILES": "C:\\Program Files",
}

#: locations in Program Files of browsers
WIN_BROWSER_DIRS = [
    "Mozilla Firefox",
]
