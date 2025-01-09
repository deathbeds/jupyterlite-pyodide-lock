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
from traitlets import Bool, Unicode

from . import __version__
from .constants import BROWSER_BIN, BROWSER_BIN_ALIASES, BROWSERS
from .utils import find_browser_binary, get_browser_search_path


class BrowsersApp(DescribedMixin, JupyterApp):
    """An app that lists discoverable browsers."""

    version: str = Unicode(default_value=__version__)

    format: str = Unicode(allow_none=True).tag(config=True)

    check_versions: bool = Bool(default_value=False).tag(config=True)

    flags: ClassVar = {
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
            "search_path": get_browser_search_path().split(os.path.pathsep),
            "browsers": {
                browser: self.collect_browser(browser) for browser in BROWSERS
            },
        }

        if self.format == "json":
            self.emit_json(results)
        else:
            self.emit_console(results)

        return_code = 0

        if self.check_versions:
            found = [b for b, r in results["browsers"].items() if r["version"]]
            if not found:
                return_code = 1

        self.exit(return_code)

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

        with contextlib.suppress(ValueError):
            result["found"] = find_browser_binary(browser_bin, log=self.log)

        if self.check_versions and result["found"]:
            with contextlib.suppress(subprocess.CalledProcessError):
                result["version"] = subprocess.check_output(  # noqa: S603
                    [result["found"], "--version"], **UTF8
                ).strip()

        return result

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

        if not result["found"]:
            self.log.warning("[%s] NOT found", browser)
            return

        self.log.info("[%s] found:\t%s", browser, result["found"])

        if result["version"]:
            self.log.info("[%s] version:\t%s", browser, result["version"])


class PyodideLockApp(DescribedMixin, JupyterApp):
    """Tools for working with 'pyodide-lock' in JupyterLite."""

    version: str = Unicode(default_value=__version__)

    subcommands: ClassVar = {
        k: (v, v.__doc__.splitlines()[0].strip())
        for k, v in dict(
            browsers=BrowsersApp,
        ).items()
    }


main = launch_new_instance = PyodideLockApp.launch_instance

if __name__ == "__main__":  # pragma: no cover
    main()
