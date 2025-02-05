"""Utilities for working with the Warehouse API, and browsers."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

from __future__ import annotations

import logging
import os
import shutil
import socket
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import psutil

from .constants import (
    BROWSER_BIN_ALIASES,
    ENV_VARS_BROWSER_BINS,
    LOCALHOST,
    OSX,
    OSX_APP_DIRS,
    WAREHOUSE_UPLOAD_FORMAT,
    WAREHOUSE_UPLOAD_FORMAT_ANY,
    WIN,
    WIN_BROWSER_DIRS,
    WIN_BROWSER_REG_KEYS,
    WIN_PROGRAM_FILES_DIRS,
)

logger = logging.getLogger(__name__)


def warehouse_date_to_epoch(iso8601_str: str) -> int:
    """Convert a Warehouse upload date to a UNIX epoch timestamp."""
    formats = WAREHOUSE_UPLOAD_FORMAT_ANY
    for format_str in formats:
        try:
            return int(
                datetime.strptime(iso8601_str, format_str)
                .replace(tzinfo=timezone.utc)
                .timestamp()
            )
        except ValueError:
            continue

    msg = f"'{iso8601_str}' didn't match any of {formats}"  # pragma: no cover
    raise ValueError(msg)  # pragma: no cover


def epoch_to_warehouse_date(epoch: int) -> str:
    """Convert a UNIX epoch timestamp to a Warehouse upload date."""
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime(
        WAREHOUSE_UPLOAD_FORMAT
    )


def find_browser_binary(browser_binary: str, log: logging.Logger = logger) -> str:
    """Resolve an absolute path to a browser binary."""
    path_var = get_browser_search_path()

    exe: str | None = None

    extensions = [""]

    if WIN:  # pragma: no covers
        extensions += [".exe", ".bat"]
    candidates = []

    for base in ["", browser_binary, *BROWSER_BIN_ALIASES.get(browser_binary, [])]:
        for extension in extensions:
            candidates += [f"{base}{extension}"]

    for candidate in candidates:  # pragma: no cover
        exe = shutil.which(candidate, path=path_var)
        if exe:
            break

    if exe is None and browser_binary in ENV_VARS_BROWSER_BINS:  # pragma: no cover
        log.debug("[browser] fall back to well-known env vars...")
        for exe in ENV_VARS_BROWSER_BINS[browser_binary]:
            if exe and Path(exe).exists():
                break

    if exe is None and WIN:  # pragma: no cover
        log.debug("[browser] fall back to registry...")
        for key in WIN_BROWSER_REG_KEYS.get(browser_binary, []):
            from winreg import (  # type: ignore[attr-defined]
                HKEY_CURRENT_USER,
                OpenKey,
                QueryValue,
            )

            with OpenKey(HKEY_CURRENT_USER, key) as reg:
                exe = QueryValue(reg)
                if exe and Path(exe).exists():
                    break

    if exe is None or not Path(exe).exists():  # pragma: no cover
        log.warning("[browser] no '%s' on PATH (or other means)", browser_binary)
        msg = f"No browser found for '{browser_binary}'"
        raise ValueError(msg)

    return exe


def get_browser_search_path() -> str:  # pragma: no cover
    """Append well-known browser locations to PATH."""
    paths = [os.environ["PATH"]]

    if WIN:
        for env_var, default in WIN_PROGRAM_FILES_DIRS.items():
            program_files = os.environ.get(env_var, "").strip() or default
            for browser_dir in WIN_BROWSER_DIRS:
                path = (Path(program_files) / browser_dir).resolve()
                if path.exists():
                    paths += [str(path)]
    elif OSX:
        for prefix in [Path.home(), Path("/")]:
            for app_dir in OSX_APP_DIRS:
                path = Path(prefix / app_dir).resolve()
                if path.exists():
                    paths += [str(path)]

    return os.pathsep.join(paths)


def get_unused_port(host: str = LOCALHOST) -> int:
    """Get an unused ipv4 port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((host, 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    sock.close()
    return int(port)


def terminate_all(
    *parents: psutil.Process,
    log: logging.Logger | None = None,
) -> tuple[list[psutil.Process], list[psutil.Process]]:
    """Terminate a processes and their children and wait for them to exit."""
    log = log or logger
    procs = [
        *[
            p
            for parent in parents
            for p in (parent.children(recursive=True) if parent else [])
        ],
        *parents,
    ]

    if not procs:  # pragma: no cover
        log.warning("unexpectedly no processes to stop from: %s", parents)

    for p in procs:
        log.warning("stopping process %s", p)
        try:
            p.terminate()
        except psutil.NoSuchProcess:  # pragma: no cover
            log.debug("was already stopped %s", p)

    result: tuple[list[psutil.Process], list[psutil.Process]] = psutil.wait_procs(
        r for r in procs if r.is_running()
    )
    return result


def url_wheel_filename(url_or_name: str) -> str | None:
    """Check whether a string is a wheel URL, and return the filename."""
    parsed = urlparse(url_or_name)
    if parsed.path.endswith(".whl"):
        return parsed.path.split("/")[-1]
    return None
