"""A command line for ``pyodide-lock`` in JupyterLite."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

from __future__ import annotations

import contextlib
import os
import sys
import textwrap
from typing import ClassVar

from jupyter_core.application import JupyterApp
from jupyterlite_core.app import DescribedMixin
from jupyterlite_core.constants import JSON_FMT
from traitlets import Unicode

from .constants import BROWSER_BIN, BROWSER_BIN_ALIASES, BROWSERS
from .utils import find_browser_binary, get_browser_search_path


class BrowsersApp(DescribedMixin, JupyterApp):
    """An app that lists discoverable browsers."""

    format: str = Unicode(allow_none=True).tag(config=True)

    flags: ClassVar = {
        "json": (
            {"BrowsersApp": {"format": "json"}},
            "output json",
        ),
    }

    def start(self) -> None:
        """Run the application."""
        results = {
            "search_path": get_browser_search_path().split(os.path.pathsep),
            "browsers": {},
        }

        for browser in BROWSERS:
            browser_bin = BROWSER_BIN[browser]
            aliases = BROWSER_BIN_ALIASES.get(browser_bin)
            result = results["browsers"][browser] = {
                "binary": browser_bin,
                "aliases": aliases,
                "found": None,
            }
            with contextlib.suppress(ValueError):
                result["found"] = find_browser_binary(browser_bin, log=self.log)

        if self.format == "json":
            import json

            sys.stdout.write(json.dumps(results, **JSON_FMT))
            return

        self.log.info(
            "[browsers] search path:\n%s",
            textwrap.indent("\n".join(results["search_path"]), "\t"),
        )
        for browser in BROWSERS:
            result = results["browsers"][browser]
            self.log.info(
                "[browsers] %s: %s (aliases: %s)",
                browser,
                result["binary"],
                result["aliases"],
            )
            if result["found"]:
                self.log.info("[browsers] %s found:\n\t%s", browser, result["found"])
            else:  # pragma: no cover
                self.log.warning("[browsers] %s NOT found", browser)


class PyodideLockApp(DescribedMixin, JupyterApp):
    """Tools for working with 'pyodide-lock' in JupyterLite."""

    subcommands: ClassVar = {
        k: (v, v.__doc__.splitlines()[0].strip())
        for k, v in dict(
            browsers=BrowsersApp,
        ).items()
    }


main = launch_new_instance = PyodideLockApp.launch_instance

if __name__ == "__main__":  # pragma: no cover
    main()
