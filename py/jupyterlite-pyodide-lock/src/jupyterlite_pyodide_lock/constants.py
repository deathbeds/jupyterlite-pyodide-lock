"""Constants for jupyterlite-pyodide-lock."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

from __future__ import annotations

import os

from jupyterlite_pyodide_kernel.constants import PYODIDE_LOCK, PYODIDE_VERSION

__all__ = [
    "LOCKER_ENTRYPOINT",
    "LOCK_HTML",
    "NAME",
    "PROXY",
    "PYODIDE_LOCK_OFFLINE",
    "PYODIDE_LOCK_STEM",
]

#: this distribution name
NAME = "jupyterlite-pyodide-lock"

#: environment variable name for setting the browser
ENV_VAR_BROWSER = "JLPL_BROWSER"

#: environment variable name for setting the lock date
ENV_VAR_LOCK_DATE_EPOCH = "JLPL_LOCK_DATE_EPOCH"

#: environment variable for setting the timeout
ENV_VAR_TIMEOUT = "JLPL_TIMEOUT"

ENV_VAR_ALL = [ENV_VAR_BROWSER, ENV_VAR_LOCK_DATE_EPOCH, ENV_VAR_TIMEOUT]

#: the entry point name for locker implementations
LOCKER_ENTRYPOINT = f"{NAME.replace('-', '_')}.locker.v0"

#: a base name for lock-related files
PYODIDE_LOCK_STEM = PYODIDE_LOCK.split(".")[0]

#: the default name for a re-solved offline lockfile
PYODIDE_LOCK_OFFLINE = f"{PYODIDE_LOCK_STEM}-offline.json"

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

#: the entry point name of ``PyodideAddon``
PYODIDE_ADDON = "jupyterlite-pyodide-kernel-pyodide"

#: the entry point name of ``PyodideLockAddon``
PYODIDE_LOCK_ADDON = "jupyterlite-pyodide-lock"

#: the entry point name of ``PyodideLockAddon``
PYODIDE_LOCK_OFFLINE_ADDON = "jupyterlite-pyodide-lock-offline"

#: the default fallback URL prefix for pyodide packages
PYODIDE_CDN_URL = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full"

#: the URL for the pyodide project
PYODIDE_GH = "https://github.com/pyodide/pyodide"

#: the default URL for a viable pyodide distribution
PYODIDE_CORE_URL = (
    f"{PYODIDE_GH}/releases/download/{PYODIDE_VERSION}/"
    f"pyodide-core-{PYODIDE_VERSION}.tar.bz2"
)

#: a regular expression for crudely detecting remote URLs
RE_REMOTE_URL = r"^https?://"

#: the default URL for python wheels
FILES_PYTHON_HOSTED = "https://files.pythonhosted.org"

#: known patterns for file types not present on all platforms/pythons
FILE_EXT_MIME_MAP = {
    r"\.mjs$": "text/javascript",
    r"\.whl$": "application/x-zip",
    r"\.wasm$": "application/wasm",
}

#: the failed in the warehouse API used for release dates
WAREHOUSE_UPLOAD_DATE = "upload_time_iso_8601"

#: a string template for the warehouse iso8601 timestamp
WAREHOUSE_UPLOAD_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
WAREHOUSE_UPLOAD_FORMAT_SHORT = "%Y-%m-%dT%H:%M:%SZ"
WAREHOUSE_UPLOAD_FORMAT_ANY = [
    WAREHOUSE_UPLOAD_FORMAT,
    WAREHOUSE_UPLOAD_FORMAT_SHORT,
]

# browsers ###

#: browser alias for firefox
FIREFOX = "firefox"

#: browser alias for chromium
CHROMIUM = "chromium"

#: browser alias for chrome
CHROME = "chrome"

#: collection of chromium-like browsers
CHROMIUMLIKE = {CHROMIUM, CHROME}

#: unsafe, but often necessary, CLI argument for chromium in CI
CHROMIUM_NO_SANDBOX = "--no-sandbox"

BROWSERS = [FIREFOX, CHROMIUM, CHROME]
BROWSER_BIN = {
    CHROMIUM: "chromium-browser",
    FIREFOX: "firefox",
    CHROME: "google-chrome",
}

BROWSER_BIN_ALIASES = {BROWSER_BIN[CHROME]: ["chrome", "Google Chrome"]}

ENV_VARS_BROWSER_BINS = {BROWSER_BIN[CHROME]: ["CHROME_BIN"]}

#: is this Linux
LINUX = os.sys.platform[:3] == "lin"

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
    "Google\\Chrome\\Application",
]

WIN_BROWSER_REG_KEYS = {
    BROWSER_BIN[CHROME]: [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"
    ]
}

#: is this osx
OSX = os.sys.platform[:3] == "dar"


#: locations in Applications of browsers
OSX_APP_DIRS = [
    "Applications/Firefox.app",
    "Applications/Firefox.app/Contents/MacOS",
    "Applications/Google Chrome.app/Contents/MacOS",
]
