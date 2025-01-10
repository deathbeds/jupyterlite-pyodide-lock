"""A command line for ``pyodide-lock`` in JupyterLite."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

from __future__ import annotations

import contextlib
import os
import subprocess  # noqa: S404
import sys
import textwrap
from typing import Any, ClassVar

from jupyter_core.application import JupyterApp
from jupyterlite_core.app import DescribedMixin
from jupyterlite_core.constants import JSON_FMT, UTF8
from traitlets import Bool, Float, Unicode

from . import __version__
from .constants import BROWSER_BIN, BROWSER_BIN_ALIASES, BROWSERS, CHROMIUMLIKE, WIN
from .lockers.browser import BROWSERS as BROWSER_OPTS
from .utils import find_browser_binary, get_browser_search_path


class BrowsersApp(DescribedMixin, JupyterApp):
    """An app that lists discoverable browsers."""

    version: str = Unicode(default_value=__version__)  # type: ignore[assignment]
    format: str = Unicode(allow_none=True).tag(config=True)  # type: ignore[assignment]
    check_versions: bool = Bool(default_value=False).tag(config=True)  # type: ignore[assignment]
    check_timeout: float = Float(default_value=5.0).tag(config=True)  # type: ignore[assignment]

    flags: ClassVar[dict[str, tuple[dict[str, Any], str]]] = {  # type: ignore[misc]
        "json": (
            {"BrowsersApp": {"format": "json"}},
            "output json",
        ),
        "check": (
            {"BrowsersApp": {"check_versions": True}},
            "check browser versions",
        ),
    }

    def start(self) -> None:
        """Run the application."""
        results = {
            "status": 1,
            "ok": False,
            "search_path": get_browser_search_path().split(os.path.pathsep),
            "browsers": {
                browser: self.collect_browser(browser) for browser in BROWSERS
            },
        }

        if not self.check_versions:
            results["status"] = 0
        else:
            found = [b for b, r in results["browsers"].items() if r["version"]]
            results["status"] = 0 if found else 1

        results["ok"] = not results["status"]

        if self.format == "json":
            self.emit_json(results)
        else:
            self.emit_console(results)

        self.exit(results["status"])

    def collect_browser(self, browser: str) -> dict[str, Any]:
        """Gather data for a single browser."""
        browser_bin = BROWSER_BIN[browser]
        aliases = BROWSER_BIN_ALIASES.get(browser_bin)
        result = {
            "binary": browser_bin,
            "aliases": aliases,
            "found": None,
            "version": None,
        }

        found_bin: str | None = None

        with contextlib.suppress(ValueError):
            result["found"] = found_bin = find_browser_binary(browser_bin, log=self.log)

        if self.check_versions and found_bin:
            result["version"] = self.get_browser_version(browser, found_bin)

        return result

    def get_browser_version(
        self, browser: str, found_bin: str
    ) -> str | None:  # pragma: no cover
        """Try to get a browser version."""
        if WIN and browser in CHROMIUMLIKE:
            return "<unreliable on Windows>"

        args = [found_bin, "--version"] + BROWSER_OPTS[browser]["headless"]

        proc = subprocess.Popen(  # noqa: S603
            args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **UTF8
        )

        output = None

        with contextlib.suppress(subprocess.TimeoutExpired):
            output = f"{proc.communicate(timeout=self.check_timeout)[0]}".strip()

        return output

    def emit_json(self, results: dict[str, Any]) -> None:
        """Emit raw results JSON."""
        import json

        sys.stdout.write(json.dumps(results, **JSON_FMT))

    def emit_console(self, results: dict[str, Any]) -> None:
        """Print out logs for browsers."""
        self.log.info(
            "search path:\n%s",
            textwrap.indent("\n".join(results["search_path"]), "\t"),
        )
        for browser, result in results["browsers"].items():
            self.emit_console_one_browser(browser, result)

    def emit_console_one_browser(self, browser: str, result: dict[str, Any]) -> None:
        """Print out logs for one browser."""
        self.log.info(
            "[%s] %s (aliases: %s)",
            browser,
            result["binary"],
            result["aliases"],
        )

        if not result["found"]:  # pragma: no cover
            self.log.warning("[%s] NOT found", browser)
            return

        self.log.info("[%s] found:\t%s", browser, result["found"])

        if result["version"]:  # pragma: no cover
            self.log.info(
                "[%s] version:\n%s", browser, textwrap.indent(result["version"], "\t")
            )


class PyodideLockApp(DescribedMixin, JupyterApp):
    """Tools for working with 'pyodide-lock' in JupyterLite."""

    version: str = Unicode(default_value=__version__)  # type: ignore[assignment]

    subcommands: ClassVar = {  # type: ignore[assignment,misc]
        k: (v, f"{v.__doc__}".splitlines()[0].strip())
        for k, v in dict(
            browsers=BrowsersApp,
        ).items()
    }


main = launch_new_instance = PyodideLockApp.launch_instance

if __name__ == "__main__":  # pragma: no cover
    main()
