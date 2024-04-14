import os
import shutil
from datetime import datetime, timezone
from logging import Logger, getLogger
from pathlib import Path

logger = getLogger(__name__)

from .constants import (
    BROWSER_BIN_ALIASES,
    ENV_VARS_BROWSER_BINS,
    OSX,
    OSX_APP_DIRS,
    WAREHOUSE_UPLOAD_FORMAT,
    WAREHOUSE_UPLOAD_FORMAT_ANY,
    WIN,
    WIN_BROWSER_DIRS,
    WIN_BROWSER_REG_KEYS,
    WIN_PROGRAM_FILES_DIRS,
)


def warehouse_date_to_epoch(iso8601_str: str) -> int:
    for format_str in WAREHOUSE_UPLOAD_FORMAT_ANY:
        try:
            return int(
                datetime.strptime(iso8601_str, format_str)
                .replace(tzinfo=timezone.utc)
                .timestamp()
            )
        except ValueError:
            continue
    raise ValueError(  # pragma: no cover
        f"'{iso8601_str}' didn't match any of {WAREHOUSE_UPLOAD_FORMAT_ANY}"
    )


def epoch_to_warehouse_date(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime(
        WAREHOUSE_UPLOAD_FORMAT
    )


def find_browser_binary(browser_binary: str, log: Logger = logger) -> str:
    """Resolve an absolute path to a browser binary."""
    path_var = get_browser_search_path()

    bin: None | str = None

    extensions = [""]

    if WIN:  # pragma: no covers
        extensions += [".exe", ".bat"]
    candidates = []

    for base in ["", browser_binary, *BROWSER_BIN_ALIASES.get(browser_binary, [])]:
        for extension in extensions:
            candidates += [f"{base}{extension}"]

    for candidate in candidates:  # pragma: no cover
        bin = shutil.which(candidate, path=path_var)
        if bin:
            break

    if bin is None and browser_binary in ENV_VARS_BROWSER_BINS:  # pragma: no cover
        log.debug("[browser] fall back to well-known env vars...")
        for bin in ENV_VARS_BROWSER_BINS[browser_binary]:
            if bin and Path(bin).exists():
                break

    if bin is None and WIN:  # pragma: no cover
        log.debug("[browser] fall back to registry...")
        for key in WIN_BROWSER_REG_KEYS.get(browser_binary, []):
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as reg:
                bin = winreg.QueryValue(reg)
                if bin and Path(bin).exists():
                    break

    if bin is None or not Path(bin).exists():  # pragma: no cover
        log.warning("[browser] no '%s' on PATH (or other means)", browser_binary)
        raise ValueError("No browser found for '%s'", browser_binary)

    return bin


def get_browser_search_path() -> str:  # pragma: no cover
    """Append well-known browser locations to PATH."""
    paths = [os.environ["PATH"]]

    if WIN:
        for env_var, default in WIN_PROGRAM_FILES_DIRS.items():
            program_files = os.environ.get(env_var, default)
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
