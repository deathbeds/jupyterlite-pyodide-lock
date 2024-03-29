"""Solve `pyodide-lock` with the browser."""

import asyncio
import json
import pprint
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path
from typing import (
    TYPE_CHECKING,
)
from typing import (
    Any as _Any,
)
from typing import (
    Dict as _Dict,
)
from typing import (
    List as _List,
)
from typing import (
    Optional as _Optional,
)
from typing import (
    Tuple as _Tuple,
)
from typing import (
    Type as _Type,
)

from jupyterlite_core.constants import JSON_FMT, UTF8
from jupyterlite_core.trait_types import TypedTuple
from traitlets import Dict, Instance, Int, Tuple, Type, Unicode, default

from ..constants import LOCK_HTML, PROXY, PYODIDE_LOCK
from ._base import BaseLocker

if TYPE_CHECKING:
    from logging import Logger

    from tornado.httpserver import HTTPServer
    from tornado.web import Application


#: default browser aliases
BROWSERS = {
    "firefox": ["firefox", "--headless", "--private-window"],
}


#: a type for tornado rules
THandler = _Tuple[str, _Type, _Dict[str, _Any]]


class BrowserLocker(BaseLocker):
    """Start a web server and browser page to build a `pyodide-lock.json`.

    The server serves a number of mostly-static files, with a fallback to any
    files in the `output_dir`.

    GET of the page the client loads
    - /lock.html

    POST/GET of the initial baseline lockfile, to be updated with the lock solution
    - /pyodide-lock.json

    GET of a Warehhouse/pythonhosted CDN proxied to configured remote URLs:
    - /_proxy/pypi
    - /_proxy/pythonhosted

    If a `static/pyodide` distribution is not found, these will also be proxied
    to the configured URL.
    """

    log: "Logger"

    browser = Unicode("firefox", help="an alias for a pre-configured browser").tag(
        config=True
    )
    browser_argv = TypedTuple(
        Unicode(), help="the non-URL arguments for the browser process"
    ).tag(config=True)
    port = Int(help="the port on which to listen").tag(config=True)
    host = Unicode("127.0.0.1", help="the host on which to bind").tag(config=True)
    protocol = Unicode("http", help="the protocol to serve").tag(config=True)
    tornado_settings = Dict(help="override settings used by the tornado server").tag(
        config=True
    )

    # runtime
    _context: _Dict[str, _Any] = Dict()
    _web_app: "Application" = Instance("tornado.web.Application")
    _http_server: "HTTPServer" = Instance("tornado.httpserver.HTTPServer")
    _handlers: _Tuple[THandler] = TypedTuple(Tuple(Unicode(), Type(), Dict()))

    # API methods
    async def resolve(self) -> Path:
        """the main solve"""
        self.preflight()
        self.log.info("Starting server at:   %s", self.base_url)
        server = self._http_server
        try:
            server.listen(self.port, self.host)
            await self.fetch()
        finally:
            server.stop()
        found = self.collect()
        self.fix_lock(found)

    # derived properties
    @property
    def cache_dir(self):
        """the location of cached files discovered during the solve"""
        return self.parent.manager.cache_dir / "browser-locker"

    @property
    def lockfile_cache(self):
        """the location of the updated lockfile"""
        return self.cache_dir / PYODIDE_LOCK

    @property
    def base_url(self):
        """the effective base URL"""
        return f"{self.protocol}://{self.host}:{self.port}"

    # helper functions
    def preflight(self):
        """prepare the cache"""

        # references for actual wheel URLs in PyPI API responses are rewritten
        # to include the random port on download
        pypi_cache = self.cache_dir / "pypi"
        if pypi_cache.exists():
            shutil.rmtree(pypi_cache)

    def collect(self) -> _Dict[str, Path]:
        """copy all packages in the cached lockfile to `output_dir`, and fix lock"""
        cached_lock = json.loads(self.lockfile_cache.read_text(**UTF8))
        packages = cached_lock["packages"]
        if not packages:
            self.log.error("No packages found after solve in %s", self.lockfile_cache)
            return

        found = {}
        self.log.info("collecting %s packages", len(packages))
        for name, package in packages.items():
            try:
                found.update(self.collect_one_package(name, package))
            except Exception:
                self.log.error("Failed to collect %s: %s", name, package, exc_info=1)

        return found

    def collect_one_package(self, name: str, package: _Dict[str, _Any]) -> _List[Path]:
        found: _Optional[Path] = None
        file_name: str = package["file_name"]
        pyodide_output = self.parent.output_pyodide

        if file_name.startswith(self.base_url):
            stem = file_name.replace(f"{self.base_url}/", "")
            if stem.startswith(PROXY):
                stem = stem.replace(f"{PROXY}/", "")
                found = self.cache_dir / stem
            else:
                found = self.parent.manager.output_dir / stem
        elif pyodide_output.exists():
            in_pyodide = pyodide_output / file_name
            if in_pyodide.exists():
                new_file_name = f"../pyodide/{file_name}"

        if found and found.exists():
            return {found.name: found}
        return {}

    def fix_lock(self, found: _Dict[str, Path]):
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
            lock_json = json.load(tmp_lock.open())

        if lock_dir.exists():
            shutil.rmtree(lock_dir)

        lock_dir.mkdir(parents=True, exist_ok=True)
        root_path = self.parent.manager.output_dir.as_posix()

        for package in lock_json["packages"].values():
            self.fix_one_package(
                root_path,
                lock_dir,
                package,
                found.get(package["file_name"].split("/")[-1]),
            )

        lockfile.write_text(json.dumps(lock_json, **JSON_FMT), **UTF8)

    def fix_one_package(
        self,
        root_posix: str,
        lock_dir: Path,
        package: _Dict[str, _Any],
        found_path: Path,
    ):
        file_name = package["file_name"]
        new_file_name = file_name

        if found_path:
            path_posix = found_path.as_posix()
            self.log.debug("checking if in output\n\t%s \n\t%s", path_posix, root_posix)
            if path_posix.startswith(root_posix):
                # build relative path to existing file
                new_file_name = found_path.as_posix().replace(root_posix, "../..")
            else:
                # copy to be sibling of lockfile, leaving name unchanged
                dest = lock_dir / file_name
                shutil.copy2(found_path, dest)

        package["file_name"] = new_file_name

    async def fetch(self):
        if self.lockfile_cache.exists():
            self.lockfile_cache.unlink()

        args = [*self.browser_argv, f"{self.base_url}/{LOCK_HTML}"]
        self.log.debug("browser args: %s", args)
        browser = subprocess.Popen(args)

        try:
            while not self.lockfile_cache.exists():
                await asyncio.sleep(1)
        finally:
            browser.terminate()

    # trait defaults
    @default("argv")
    def _default_argv(self):
        argv = [*BROWSERS.get(self.browser)]
        argv[0] = shutil.which(argv[0]) or shutil.which(f"{argv[0]}.exe")
        return argv

    @default("_web_app")
    def _default_web_app(self):
        """build the web application"""
        from tornado.web import Application

        handlers = self._handlers
        self.log.debug("handlers:\n%s", pprint.pformat(handlers))
        return Application(self._handlers, **self.tornado_settings)

    @default("tornado_settings")
    def _default_tornado_settings(self):
        return {"debug": True, "autoreload": False}

    @default("_handlers")
    def _default_handlers(self):
        from .handlers import make_handlers

        return make_handlers(self)

    @default("_http_server")
    def _default_http_server(self):
        from tornado.httpserver import HTTPServer

        return HTTPServer(self._web_app)

    @default("port")
    def _default_port(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((self.host, 0))
        sock.listen(1)
        port = sock.getsockname()[1]
        sock.close()
        return port

    @default("browser_argv")
    def _default_browser_argv(self):
        argv = [*BROWSERS[self.browser]]
        argv[0] = shutil.which(argv[0]) or shutil.which(f"{argv[0]}.exe")
        return argv

    @default("_context")
    def _default_context(self):
        return {"micropip_args_json": json.dumps(self.micropip_args)}

    @default("micropip_args")
    def _default_micropip_args(self):
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
    def _default_extra_micropip_args(self):
        return {}
