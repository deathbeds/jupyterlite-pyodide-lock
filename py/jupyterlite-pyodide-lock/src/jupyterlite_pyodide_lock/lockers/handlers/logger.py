"""A handler that accepts log messages from the browser."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from tornado.web import RequestHandler

if TYPE_CHECKING:
    from logging import Logger


class Log(RequestHandler):
    """Log repeater from the browser."""

    def initialize(self, log: Logger, **kwargs: Any) -> None:
        """Initialize handler instance members."""
        self.log = log
        super().initialize(**kwargs)

    def post(self, pipe: str) -> None:
        """Accept a log message as the POST body."""
        body = json.loads(self.request.body.decode("utf-8"))

        try:
            message = body["message"]
            self.log.debug("[pyodidejs] [%s] %s", pipe, message)
        except Exception:  # pragma: no cover
            self.log.debug("[pyodidejs] [%s] %s", pipe, body)
