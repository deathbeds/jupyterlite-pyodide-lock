"""web handlers for BrowserLocker"""

from typing import TYPE_CHECKING

from ...constants import LOCK_HTML, PROXY, PYODIDE_LOCK
from .cacher import CachingRemoteFiles
from .freezer import MicropipFreeze
from .logger import Log
from .mime import ExtraMimeFiles
from .solver import SolverHTML

if TYPE_CHECKING:  # pragma: no cover
    from ..browser import BrowserLocker


def make_handlers(locker: "BrowserLocker"):
    """Create the default handlers used for serving proxied CDN assets and locking"""
    files_cdn = locker.pythonhosted_cdn_url.encode("utf-8")
    files_local = f"{locker.base_url}/{PROXY}/pythonhosted".encode()

    pypi_kwargs = {
        "rewrites": {"/json$": [(files_cdn, files_local)]},
        "mime_map": {r"/json$": "application/json"},
    }
    solver_kwargs = {"context": locker._context, "log": locker.log}
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
        # fallback to `output_dir`
        (r"^/(.*)$", ExtraMimeFiles, fallback_kwargs),
    )


def make_proxy(
    locker: "BrowserLocker",
    path: str,
    remote: str,
    route: str = None,
    **extra_config,
):
    """Generate a proxied tornado handler rule"""
    route = route or f"^/{PROXY}/{path}/(.*)$"
    config = {
        "path": locker.cache_dir / path,
        "remote": remote,
        "log": locker.log,
        **extra_config,
    }
    return (route, CachingRemoteFiles, config)
