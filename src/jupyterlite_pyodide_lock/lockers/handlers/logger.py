"""A handler that accepts log messages from the browser."""

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
        self.log.debug("[pyodidejs] [%s] %s", pipe, self.request.body.decode("utf-8"))
