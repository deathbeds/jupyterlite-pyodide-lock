"""Host a tornado web application to solve``pyodide-lock.json`` ."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

from __future__ import annotations

import atexit
import json
import shutil
import socket
import tempfile
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
)

from jupyterlite_core.constants import JSON_FMT, UTF8
from jupyterlite_core.trait_types import TypedTuple
from traitlets import Bool, Dict, Instance, Int, Tuple, Type, Unicode, default

from jupyterlite_pyodide_lock.constants import (
    LOCK_HTML,
    PROXY,
    PYODIDE_LOCK,
    PYODIDE_LOCK_STEM,
)

from ._base import BaseLocker
from .handlers import make_handlers

if TYPE_CHECKING:
    from logging import Logger

    from tornado.httpserver import HTTPServer
    from tornado.web import Application

    from .handlers import TRouteRule


#: a type for tornado rules
THandler = tuple[str, type, dict[str, Any]]


class TornadoLocker(BaseLocker):
    """Start a web server and a browser (somehow) to build a ``pyodide-lock.json``.

    For an example strategy, see :class:`..browser.BrowserLocker`.

    The server serves a number of mostly-static files, with a fallback to any
    files in the ``output_dir``.

    ``GET`` of the page the client loads:

        * ``/lock.html``

    ``POST/GET`` of the initial baseline lockfile, to be updated with the lock solution:

        * ``/pyodide-lock.json``

    ``POST`` of log messages:

        * ``/log``

    GET of a Warehouse/pythonhosted CDN proxied to configured remote URLs:

        * ``/_proxy/pypi``
        * ``/_proxy/pythonhosted``

    If an ``{output_dir}/static/pyodide`` distribution is found, these will also
    be proxied from the configured URL.
    """

    log: Logger

    port = Int(help="the port on which to listen").tag(config=True)
    host = Unicode("127.0.0.1", help="the host on which to bind").tag(config=True)
    protocol = Unicode("http", help="the protocol to serve").tag(config=True)
    tornado_settings = Dict(help="override settings used by the tornado server").tag(
        config=True,
    )

    # runtime
    _context: dict[str, Any] = Dict()
    _web_app: Application = Instance("tornado.web.Application")
    _http_server: HTTPServer = Instance(
        "tornado.httpserver.HTTPServer", allow_none=True
    )
    _handlers: tuple[THandler, ...] = TypedTuple(Tuple(Unicode(), Type(), Dict()))
    _solve_halted: bool = Bool(default_value=False)

    # API methods
    async def resolve(self) -> bool | None:
        """Launch a web application, then delegate to actually run the solve."""
        self.preflight()
        self.log.info("Starting server at:   %s", self.base_url)

        server = self._http_server

        atexit.register(self.cleanup)

        try:
            server.listen(self.port, self.host)
            await self.fetch()
        finally:
            self.cleanup()

        if not self.lockfile_cache.exists():
            self.log.exception("No lockfile was created at %s", self.lockfile)
            return False

        found = self.collect()
        self.fix_lock(found)

        return True

    def cleanup(self) -> None:
        """Handle any cleanup tasks, as needed by specific implementations."""
        if self._http_server:
            self.log.debug("[tornado] stopping http server")
            self._http_server.stop()
            self._http_server = None
            return
        self.log.debug("[tornado] already cleaned up")

    # derived properties
    @property
    def cache_dir(self) -> Path:
        """The location of cached files discovered during the solve."""
        return self.parent.manager.cache_dir / "browser-locker"

    @property
    def lockfile_cache(self) -> Path:
        """The location of the updated lockfile."""
        return self.cache_dir / PYODIDE_LOCK

    @property
    def base_url(self) -> str:
        """The effective base URL."""
        return f"{self.protocol}://{self.host}:{self.port}"

    @property
    def lock_html_url(self) -> str:
        """The as-served URL for the lock HTML page."""
        return f"{self.base_url}/{LOCK_HTML}"

    # helper functions
    def preflight(self) -> None:
        """Prepare the cache.

        The PyPI cache is removed before each build, as the JSON cache is
        invalidated by both references to the temporary ``files.pythonhosted.org``
        proxy and a potential change to ``lock_date_epoch``.
        """
        pypi_cache = self.cache_dir / "pypi"
        if pypi_cache.exists():
            self.log.debug("[tornado] clearing pypi cache %s", pypi_cache)
            shutil.rmtree(pypi_cache)

        if self.lockfile_cache.exists():
            self.lockfile_cache.unlink()

    def collect(self) -> dict[str, Path]:
        """Copy all packages in the cached lockfile to ``output_dir``, and fix lock."""
        cached_lock = json.loads(self.lockfile_cache.read_text(**UTF8))
        packages = cached_lock["packages"]

        found = {}
        self.log.info("collecting %s packages", len(packages))
        for name, package in packages.items():
            try:
                found.update(self.collect_one_package(package))
            except Exception:  # pragma: no cover
                self.log.exception("Failed to collect %s: %s", name, package)

        return found

    def collect_one_package(self, package: dict[str, Any]) -> dict[str, Path]:
        """Find a package in the cache."""
        found: Path | None = None
        file_name: str = package["file_name"]

        if file_name.startswith(self.base_url):
            stem = file_name.replace(f"{self.base_url}/", "")
            if stem.startswith(PROXY):
                stem = stem.replace(f"{PROXY}/", "")
                found = self.cache_dir / stem
            else:
                found = self.parent.manager.output_dir / stem

        if found and found.exists():
            return {found.name: found}

        return {}

    def fix_lock(self, found: dict[str, Path]) -> None:
        """Fill in missing metadata from the ``micropip.freeze`` output."""
        from pyodide_lock import PyodideLockSpec
        from pyodide_lock.utils import add_wheels_to_spec

        lockfile = self.parent.lockfile
        lock_dir = lockfile.parent

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            tmp_lock = tdp / PYODIDE_LOCK
            shutil.copy2(self.lockfile_cache, tmp_lock)
            [shutil.copy2(path, tdp / path.name) for path in found.values()]
            spec = PyodideLockSpec.from_json(tdp / PYODIDE_LOCK)
            tmp_wheels = sorted(tdp.glob("*.whl"))
            spec = add_wheels_to_spec(spec, tmp_wheels)
            spec.to_json(tmp_lock)
            lock_json = json.loads(tmp_lock.read_text(**UTF8))

        lock_dir.mkdir(parents=True, exist_ok=True)
        root_path = self.parent.manager.output_dir.as_posix()

        prune = {path.name: path for path in lock_dir.glob("*.whl")}
        for package in lock_json["packages"].values():
            prune.pop(package["file_name"], None)
            self.fix_one_package(
                root_path,
                lock_dir,
                package,
                found.get(package["file_name"].split("/")[-1]),
            )

        for filename, path in prune.items():
            self.log.warning("[tornado] [fix] pruning unlocked %s", filename)
            path.unlink()

        lockfile.write_text(json.dumps(lock_json, **JSON_FMT), **UTF8)

    def fix_one_package(
        self,
        root_posix: str,
        lock_dir: Path,
        package: dict[str, Any],
        found_path: Path,
    ) -> None:
        """Update a ``pyodide-lock`` URL for deployment."""
        file_name = package["file_name"]
        new_file_name = file_name

        if found_path:
            path_posix = found_path.as_posix()
            if path_posix.startswith(root_posix):
                # build relative path to existing file
                new_file_name = found_path.as_posix().replace(root_posix, "../..")
            else:
                # copy to be sibling of lockfile, leaving name unchanged
                dest = lock_dir / file_name
                shutil.copy2(found_path, dest)
                new_file_name = f"../../static/{PYODIDE_LOCK_STEM}/{file_name}"
        else:
            new_file_name = f"{self.parent.pyodide_cdn_url}/{file_name}"

        if file_name == new_file_name:  # pragma: no cover
            self.log.debug("[tornado] file did not need fixing %s", file_name)

        package["file_name"] = new_file_name

    async def fetch(self) -> None:  # pragma: no cover
        """Actually perform the solve."""
        msg = f"{self.__class__.__name__} must implement 'fetch'"
        raise NotImplementedError(msg)

    # trait defaults
    @default("_web_app")
    def _default_web_app(self) -> Application:
        """Build the web application."""
        from tornado.web import Application

        return Application(self._handlers, **self.tornado_settings)

    @default("tornado_settings")
    def _default_tornado_settings(self) -> dict[str, Any]:
        return {"debug": True, "autoreload": False}

    @default("_handlers")
    def _default_handlers(self) -> TRouteRule:
        return make_handlers(self)

    @default("_http_server")
    def _default_http_server(self) -> HTTPServer:
        from tornado.httpserver import HTTPServer

        return HTTPServer(self._web_app)

    @default("port")
    def _default_port(self) -> int:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((self.host, 0))
        sock.listen(1)
        port = sock.getsockname()[1]
        sock.close()
        return port

    @default("_context")
    def _default_context(self) -> dict[str, Any]:
        return {"micropip_args_json": json.dumps(self.micropip_args)}

    @default("micropip_args")
    def _default_micropip_args(self) -> dict[str, Any]:
        args = {}
        # defaults
        args.update(pre=False, verbose=True, keep_going=True)
        # overrides
        args.update(self.extra_micropip_args)

        # build requirements
        output_base_url = self.parent.manager.output_dir.as_posix()
        requirements = [
            pkg.as_posix().replace(output_base_url, self.base_url, 1)
            for pkg in self.packages
        ] + self.specs

        # required
        args.update(
            requirements=requirements,
            index_urls=[f"{self.base_url}/{PROXY}/pypi/{{package_name}}/json"],
        )
        return args

    @default("extra_micropip_args")
    def _default_extra_micropip_args(self) -> dict[str, Any]:
        return {}
