"""Tornado handlers for ``BrowserLocker``."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

import json
from typing import TYPE_CHECKING, Any

from jupyterlite_core.constants import JSON_FMT

from jupyterlite_pyodide_lock.constants import (
    LOCK_HTML,
    PROXY,
    PYODIDE_LOCK,
    WAREHOUSE_UPLOAD_DATE,
)
from jupyterlite_pyodide_lock.utils import (
    epoch_to_warehouse_date,
    warehouse_date_to_epoch,
)

from .cacher import CachingRemoteFiles
from .freezer import MicropipFreeze
from .logger import Log
from .mime import ExtraMimeFiles
from .solver import SolverHTML

if TYPE_CHECKING:
    from collections.abc import Callable

    from jupyterlite_pyodide_lock.lockers.browser import BrowserLocker

    TRouteRule = tuple[str, type, dict[str, Any]]


def make_lock_date_epoch_replacer(locker: "BrowserLocker") -> "Callable[[str], str]":
    """Filter out releases newer than the lock date."""
    lock_date_epoch = locker.parent.lock_date_epoch
    lock_date_iso8601 = epoch_to_warehouse_date(lock_date_epoch)

    def _clamp_to_lock_date_epoch(json_str: bytes) -> bytes:
        release_data = json.loads(json_str.decode("utf-8"))
        release_data["releases"] = {
            release: artifacts
            for release, artifacts in release_data["releases"].items()
            if artifacts and all(map(_uploaded_before, artifacts))
        }
        return json.dumps(release_data, **JSON_FMT).encode("utf-8")

    def _uploaded_before(artifact: dict[str, Any]) -> bool:
        upload_iso8601 = artifact[WAREHOUSE_UPLOAD_DATE]
        upload_epoch = warehouse_date_to_epoch(upload_iso8601)

        if upload_epoch <= lock_date_epoch:
            return True

        locker.log.warning(
            "[tornado] [lock-date] %s uploaded %s (%s), newer than %s (%s)",
            artifact["filename"],
            upload_iso8601,
            upload_epoch,
            lock_date_iso8601,
            lock_date_epoch,
        )
        return False

    return _clamp_to_lock_date_epoch


def make_handlers(locker: "BrowserLocker") -> "tuple[TRouteRule]":
    """Create the default handlers used for serving proxied CDN assets and locking."""
    files_cdn = locker.pythonhosted_cdn_url.encode("utf-8")
    files_local = f"{locker.base_url}/{PROXY}/pythonhosted".encode()

    pypi_kwargs = {
        "rewrites": {"/json$": [(files_cdn, files_local)]},
        "mime_map": {r"/json$": "application/json"},
    }

    if locker.parent.lock_date_epoch:
        replacer = make_lock_date_epoch_replacer(locker)
        pypi_kwargs["rewrites"]["/json$"] += [
            (WAREHOUSE_UPLOAD_DATE.encode("utf-8"), replacer)
        ]

    solver_kwargs = {
        "context": locker._context,  # noqa: SLF001
        "log": locker.log,
    }
    fallback_kwargs = {
        "log": locker.log,
        "path": locker.parent.manager.output_dir,
    }

    return (
        # the page the client GETs as HTML
        (f"^/{LOCK_HTML}$", SolverHTML, solver_kwargs),
        # the page to which the client POSTs
        (f"^/{PYODIDE_LOCK}$", MicropipFreeze, {"locker": locker}),
        # logs
        ("^/log/(.*)$", Log, {"log": locker.log}),
        # remote proxies
        make_proxy(locker, "pythonhosted", locker.pythonhosted_cdn_url),
        make_proxy(locker, "pypi", locker.pypi_api_url, **pypi_kwargs),
        # fallback to ``output_dir``
        (r"^/(.*)$", ExtraMimeFiles, fallback_kwargs),
    )


def make_proxy(
    locker: "BrowserLocker",
    path: str,
    remote: str,
    route: str | None = None,
    **extra_config: Any,
) -> "TRouteRule":
    """Generate a proxied tornado handler rule."""
    route = route or f"^/{PROXY}/{path}/(.*)$"
    config = {
        "path": locker.cache_dir / path,
        "remote": remote,
        "log": locker.log,
        **extra_config,
    }
    return (route, CachingRemoteFiles, config)
