"""A ``tornado`` handler that serves a ``pyodide`` application, solves, and quits."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from jupyterlite_core.constants import UTF8
from tornado.template import Template
from tornado.web import RequestHandler

if TYPE_CHECKING:
    from logging import Logger


class SolverHTML(RequestHandler):
    """Render a static HTML page to run ``micropip.freeze``."""

    context: dict[str, str]
    log: Logger
    template: Template

    def initialize(self, context: dict[str, str], *args: Any, **kwargs: Any) -> None:
        """Initialize handler instance members."""
        log = kwargs.pop("log")
        super().initialize(*args, **kwargs)
        self.context = context
        self.log = log
        self.template = Template(
            (Path(__file__).parent / "lock.html.j2").read_text(**UTF8)
        )

    async def get(self, *args: Any, **kwargs: Any) -> None:
        """Handle a GET request."""
        rendered = self.template.generate(**self.context)
        self.log.debug("[solver] lock HTML\n%s", rendered)
        await self.finish(rendered)
