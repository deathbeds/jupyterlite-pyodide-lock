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

if TYPE_CHECKING:  # pragma: no cover
    from logging import Logger

    from .browser import BrowserLocker


def make_handlers(locker: "BrowserLocker"):
    files_cdn = locker.pythonhosted_cdn_url.encode("utf-8")
    files_local = f"{locker.base_url}/{PROXY}/pythonhosted".encode()

    pypi_kwargs = {
        "rewrites": {"/json$": [(files_cdn, files_local)]},
        "mime_map": {
            r"/json$": "application/json",
        },
    }

    pyodide_handlers = []

    return (
        # the page the client GETs as HTML
        (
            f"^/{LOCK_HTML}$",
            SolverHTML,
            {"context": locker._context, "log": locker.log},
        ),
        # the page to which the client POSTs
        (f"^/{PYODIDE_LOCK}$", MicropipFreeze, {"locker": locker}),
        # logs
        ("^/log/(.*)$", Log, {"log": locker.log}),
        # remote proxies
        make_proxy(locker, "pythonhosted", locker.pythonhosted_cdn_url),
        make_proxy(locker, "pypi", locker.pypi_api_url, **pypi_kwargs),
        *pyodide_handlers,
        # fallback to `output_dir`
        (
            r"^/(.*)$",
            ExtraMimeFiles,
            {
                "log": locker.log,
                "path": locker.parent.manager.output_dir,
                "mime_map": {r"\.whl$": "application/x-zip"},
            },
        ),
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


class ExtraMimeFiles(StaticFileHandler):
    log: "Logger"

    #: map URL regex to content type
    mime_map: dict[str, str]

    def initialize(self, log, mime_map=None, **kwargs):
        super().initialize(**kwargs)
        self.mime_map = mime_map or {}
        self.log = log

    def get_content_type(self) -> str:
        from_parent = super().get_content_type()
        from_map = None
        if self.absolute_path is None:  # pragma: no cover
            return from_parent
        for pattern, mimetype in self.mime_map.items():
            if not re.search(pattern, self.absolute_path):  # pragma: no cover
                continue
            from_map = mimetype
            break

        self.log.debug(
            "serving %s as %s (of %s %s)",
            self.absolute_path,
            from_map or from_parent,
            from_parent,
            from_map,
        )
        return from_map or from_parent


class CachingRemoteFiles(ExtraMimeFiles):
    """a handler which serves files from a cache, downloading them as needed."""

    #: remote URL root
    remote: str
    #: HTTP client
    client: AsyncHTTPClient
    #: URL patterns that should have text replaced
    rewrites: dict[str, _Any]

    def initialize(self, remote, rewrites=None, **kwargs):
        super().initialize(**kwargs)
        self.remote = remote
        self.client = AsyncHTTPClient()
        self.rewrites = rewrites or {}

    async def get(self, path: str, include_body: bool = True) -> None:
        """actually fetch a file"""
        cache_path = self.root / path
        if cache_path.exists():  # pragma: no cover
            pass
        else:
            await self.cache_file(path, cache_path)
        return await super().get(path, include_body)

    async def cache_file(self, path: str, cache_path: Path):
        """get the file, and rewrite it."""
        url = f"{self.remote}/{path}"
        self.log.debug("fetching:    %s", url)
        res = await self.client.fetch(url)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        body = res.body

        for url_pattern, replacements in self.rewrites.items():
            if re.search(url_pattern, path) is None:  # pragma: no cover
                self.log.debug("%s is not %s", url, url_pattern)
                continue
            for marker, replacement in replacements:
                if marker not in body:  # pragma: no cover
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

    async def get(self, *args, **kwargs):
        template = jinja2.Template(self.TEMPLATE)
        rendered = template.render(self.context)
        self.log.debug("Serving HTML\n%s", rendered)
        await self.finish(rendered)

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
                    packages: ["micropip"],
                });

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


class MicropipFreeze(RequestHandler):
    """Accept raw `micropip.freeze` output from the client and write it to disk."""

    locker: "BrowserLocker"

    def initialize(self, locker: "BrowserLocker", **kwargs):
        self.locker = locker
        super().initialize(**kwargs)

    async def post(self):
        """Accept a `pyodide-lock.json` as the POST body."""
        # parse and write out the re-normalized lockfile
        lock_json = json.loads(self.request.body)
        if "packages" in lock_json:
            lockfile = self.locker.lockfile_cache
            lockfile.parent.mkdir(parents=True, exist_ok=True)
            lockfile.write_text(json.dumps(lock_json, **JSON_FMT), **UTF8)
            self.locker.log.info("Wrote raw `micropip.freeze` to %s", lockfile)
        else:
            self.locker.log.error("Unexpected `micropip.freeze` response %s", lock_json)

        self.locker._solve_halted = True

        await self.finish()


class Log(RequestHandler):
    """Log repeater from the browser."""

    def initialize(self, log: "Logger", **kwargs):
        self.log = log
        super().initialize(**kwargs)

    def post(self, pipe):
        """Accept a log message as the POST body."""
        self.log.debug("pyodide %s: %s", pipe, json.loads(self.request.body))
