"""web handlers for BrowserLocker"""

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any as _Any

import jinja2
from jupyterlite_core.constants import JSON_FMT, UTF8
from tornado.httpclient import AsyncHTTPClient
from tornado.web import RequestHandler, StaticFileHandler

from ..constants import LOCK_HTML, PROXY, PYODIDE_LOCK

if TYPE_CHECKING:
    from logging import Logger

    from .browser import BrowserLocker


def make_handlers(locker: "BrowserLocker"):
    files_cdn = locker.pythonhosted_cdn_url.encode("utf-8")
    files_local = f"{locker.base_url}/{PROXY}/pythonhosted".encode()

    pypi_kwargs = {
        "rewrites": {"/json$": [(files_cdn, files_local)]},
        "mime_map": {"/json$": "application/json"},
    }
    lock_kwargs = {
        "lockfile": locker.lockfile_cache,
    }

    pyodide_handlers = []

    if not locker.parent.pyodide_addon.output_pyodide.exists():
        route = "^/static/pyodide/(.*)$"
        pyodide_handlers += [
            make_proxy(locker, "pyodide", locker.pyodide_cdn_url, route=route),
        ]

    return (
        # the page the client GETs as HTML
        (
            f"^/{LOCK_HTML}$",
            SolverHTML,
            {"context": locker._context, "log": locker.log},
        ),
        # the page to which the client POSTs
        (f"^/{PYODIDE_LOCK}$", PyodideLock, lock_kwargs),
        # logs
        ("^/log/(.*)$", Log, {"log": locker.log}),
        # remote proxies
        make_proxy(locker, "pythonhosted", locker.pythonhosted_cdn_url),
        make_proxy(locker, "pypi", locker.pypi_api_url, **pypi_kwargs),
        *pyodide_handlers,
        # fallback to `output_dir`
        ("^/(.*)$", StaticFileHandler, {"path": locker.parent.manager.output_dir}),
    )


def make_proxy(
    locker: "BrowserLocker", path: str, remote: str, route: str = None, **extra_config
):
    """generate a proxied tornado handler rule"""
    from .handlers import CachingRemoteFiles

    route = route or f"^/{PROXY}/{path}/(.*)$"
    config = {
        "path": locker.cache_dir / path,
        "remote": remote,
        "log": locker.log,
        **extra_config,
    }
    return (route, CachingRemoteFiles, config)


class CachingRemoteFiles(StaticFileHandler):
    """a handler which serves files from a cache, downloading them as needed."""

    #: remote URL root
    remote: str
    #: HTTP client
    client: AsyncHTTPClient
    #: URL patterns that should have text replaced
    rewrites: dict[str, _Any]
    #: map URL regex to content type
    mime_map: dict[str, str]
    log: "Logger"

    def initialize(self, remote, log, rewrites=None, mime_map=None, **kwargs):
        super().initialize(**kwargs)
        self.log = log
        self.remote = remote
        self.client = AsyncHTTPClient()
        self.rewrites = rewrites or {}
        self.mime_map = mime_map or {}

    async def get(self, path: str, include_body: bool = True) -> None:
        """actually fetch a file"""
        cache_path = self.root / path
        if not cache_path.exists():
            await self.cache_file(path, cache_path)
        return await super().get(path, include_body)

    def get_content_type(self) -> str:
        if self.absolute_path is not None:
            for pattern, mimetype in self.mime_map.items():
                if re.search(pattern, self.absolute_path):
                    return mimetype
        return super().get_content_type()

    async def cache_file(self, path: str, cache_path: Path):
        """get the file, and rewrite it."""
        url = f"{self.remote}/{path}"
        self.log.debug("fetching:    %s", url)
        res = await self.client.fetch(url)
        if not cache_path.parent.exists():
            cache_path.parent.mkdir(parents=True)

        body = res.body

        for url_pattern, replacements in self.rewrites.items():
            if re.search(url_pattern, path) is None:
                self.log.debug("%s is not %s", url, url_pattern)
                continue
            for marker, replacement in replacements:
                if marker not in body:
                    self.log.debug("%s does not contain %s", url, marker)
                else:
                    self.log.debug("found:     %s contains %s", url, marker)
                    body = body.replace(marker, replacement)

        cache_path.write_bytes(body)


class SolverHTML(RequestHandler):
    context: dict
    log: "Logger"

    def initialize(self, context, *args, **kwargs):
        log = kwargs.pop("log")
        super().initialize(*args, **kwargs)
        self.context = context
        self.log = log

    def get(self, *args, **kwargs):
        template = jinja2.Template(self.TEMPLATE)
        rendered = template.render(self.context)
        self.write(rendered)

    TEMPLATE = """
        <html>
            <script type="module">
                import { loadPyodide } from './static/pyodide/pyodide.mjs';

                async function post(url, body) {
                    return await fetch(
                        url, {
                        method: "POST",
                        headers: {"Content-Type": "application/json"},
                        body
                    });
                }

                function tee(pipe, message) {
                    console.log(pipe, message);
                    void post(`/log/${pipe}`, JSON.stringify({ message }, null, 2));
                }

                const pyodide = await loadPyodide({
                    stdout: tee.bind(this, 'stdout'),
                    stderr: tee.bind(this, 'stderr'),
                });

                await pyodide.loadPackage("micropip");

                await pyodide.runPythonAsync(`
                    try:
                        import micropip, js, json
                        await micropip.install(
                            **json.loads(
                                '''
                                {{ micropip_args_json }}
                                '''
                            )
                        )
                        js.window.PYODIDE_LOCK = micropip.freeze()
                    except Exception as err:
                        js.window.PYODIDE_ERROR = str(err)
                `);

                await post(
                    "./pyodide-lock.json",
                    window.PYODIDE_LOCK
                        || JSON.stringify({"error": window.PYODIDE_ERROR})
                );
                window.close();
            </script>
        </html>
    """


class PyodideLock(RequestHandler):
    """Accept a `pyodide-lock.json` from the client and write it to disk."""

    lockfile: Path

    def initialize(self, lockfile: Path, log: "Logger", **kwargs):
        self.lockfile = lockfile
        self.log = log
        super().initialize(**kwargs)

    def post(self):
        """Accept a `pyodide-lock.json` as the POST body."""
        # parse and write out the re-normalized lockfile
        lock_json = json.loads(self.request.body)
        if "packages" not in lock_json:
            self.log.error("Unexpected response %s", lock_json)
            return

        self.lockfile.parent.mkdir(parents=True, exist_ok=True)
        self.lockfile.write_text(json.dumps(lock_json, **JSON_FMT), **UTF8)
        self.log.info("Wrote %s", self.lockfile)


class Log(RequestHandler):
    """Log repeater from the browser."""

    def initialize(self, log: "Logger", **kwargs):
        self.log = log
        super().initialize(**kwargs)

    def post(self, pipe):
        """Accept a log message as the POST body."""
        self.log.debug("pyodide %s: %s", pipe, json.loads(self.request.body))
