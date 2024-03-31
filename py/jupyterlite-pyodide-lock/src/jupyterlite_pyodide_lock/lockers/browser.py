"""Solve `pyodide-lock` with the browser."""

import asyncio
import atexit
import json
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
from typing import (
    Union as _Union,
)

from jupyterlite_core.constants import JSON_FMT, UTF8
from jupyterlite_core.trait_types import TypedTuple
from traitlets import Bool, Dict, Instance, Int, Tuple, Type, Unicode, default

from ..constants import LOCK_HTML, PROXY, PYODIDE_LOCK, PYODIDE_LOCK_STEM
from ._base import BaseLocker

if TYPE_CHECKING:  # pragma: no cover
    from logging import Logger

    from tornado.httpserver import HTTPServer
    from tornado.web import Application


#: default browser aliases
BROWSERS = {
    "firefox": ["firefox"],
    "chromium": ["chromium-browser"],
}

HEADLESS_MODE = {
    "firefox": ["--headless"],
    "chromium": ["--headless"],
}

PRIVATE_MODE = {
    "firefox": ["--private-window"],
    "chromium": ["--incognito"],
}

NEW_PROFILE = {
    "firefox": ["--new-instance", "--profile", "."],
    "chromium": ["--user-data-dir", "."],
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

    browser_argv = TypedTuple(
        Unicode(),
        help=(
            "the non-URL arguments for the browser process: if configured, "
            "`browser`, `headless`, `private_mode`, `new_profile` are ignored"
        ),
    ).tag(config=True)

    browser = Unicode("firefox", help="an alias for a pre-configured browser").tag(
        config=True
    )
    headless = Bool(True, help="run the browser in headless mode").tag(config=True)
    private_mode = Bool(True, help="run the browser in private mode").tag(config=True)
    new_profile = Bool(False, help="run the browser with a temporary profile").tag(
        config=True
    )

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
    _solve_halted: bool = Bool(False)

    # API methods
    async def resolve(self) -> _Union[bool, None]:
        """the main solve"""
        self.preflight()
        self.log.info("Starting server at:   %s", self.base_url)

        server = self._http_server

        try:
            server.listen(self.port, self.host)
            await self.fetch()
        finally:
            server.stop()

        if not self.lockfile_cache.exists():
            self.log.error("No lockfile was created at %s", self.lockfile)
            return False

        found = self.collect()
        self.fix_lock(found)

        return True

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

        found = {}
        self.log.info("collecting %s packages", len(packages))
        for name, package in packages.items():
            try:
                self.log.debug("collecting %s", name)
                found.update(self.collect_one_package(name, package))
            except Exception:  # pragma: no cover
                self.log.error("Failed to collect %s: %s", name, package, exc_info=1)

        return found

    def collect_one_package(self, name: str, package: _Dict[str, _Any]) -> _List[Path]:
        found: _Optional[Path] = None
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
            self.log.debug("File did not need fixing %s", file_name)
        else:
            self.log.debug("File fixed %s -> %s", file_name, new_file_name)

        package["file_name"] = new_file_name

    async def fetch(self):
        if self.lockfile_cache.exists():
            self.lockfile_cache.unlink()

        with tempfile.TemporaryDirectory() as td:
            args = [*self.browser_argv, f"{self.base_url}/{LOCK_HTML}"]
            self.log.debug("browser args: %s", args)
            browser = subprocess.Popen(args, cwd=td)

            def cleanup():
                if browser.returncode is not None:  # pragma: no cover
                    self.log.info("Browser is already closed")

                self.log.info("Closing browser")
                browser.terminate()
                browser.wait()

            atexit.register(cleanup)

            try:
                while not self._solve_halted:
                    await asyncio.sleep(1)
                cleanup()
            finally:
                cleanup()

    # trait defaults
    @default("_web_app")
    def _default_web_app(self):
        """build the web application"""
        from tornado.web import Application

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

        if True:  # pragma: no cover
            if self.headless:
                argv += HEADLESS_MODE[self.browser]

            if self.private_mode:
                argv += PRIVATE_MODE[self.browser]

            if self.new_profile:
                argv += NEW_PROFILE[self.browser]

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
