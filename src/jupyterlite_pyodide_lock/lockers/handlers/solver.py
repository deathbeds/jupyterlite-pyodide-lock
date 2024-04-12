from pathlib import Path
from typing import TYPE_CHECKING

from jupyterlite_core.constants import UTF8
from tornado.template import Template
from tornado.web import RequestHandler

if TYPE_CHECKING:  # pragma: no cover
    from logging import Logger


class SolverHTML(RequestHandler):
    context: dict[str, str]
    log: "Logger"
    template: "Template"

    def initialize(self, context, *args, **kwargs):
        log = kwargs.pop("log")
        super().initialize(*args, **kwargs)
        self.context = context
        self.log = log
        self.template = Template(
            (Path(__file__).parent / "lock.html.j2").read_text(**UTF8)
        )

    async def get(self, *args, **kwargs):
        rendered = self.template.generate(**self.context)
        self.log.debug("[tornado] lock HTML\n%s", rendered)
        await self.finish(rendered)
