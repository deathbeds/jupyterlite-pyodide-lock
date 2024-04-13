"""A handler that accepts log messages from the browser."""

import json
from typing import TYPE_CHECKING

from tornado.web import RequestHandler

if TYPE_CHECKING:  # pragma: no cover
    from logging import Logger


class Log(RequestHandler):
    """Log repeater from the browser."""

    def initialize(self, log: "Logger", **kwargs):
        self.log = log
        super().initialize(**kwargs)

    def post(self, pipe):
        """Accept a log message as the POST body."""
        body = json.loads(self.request.body.decode("utf-8"))
        try:
            message = body["message"]
        except:  # pragma: no cover
            pass
        self.log.debug("[pyodidejs] [%s] %s", pipe, message)
