import re
from typing import TYPE_CHECKING
from pathlib import Path

from tornado.web import StaticFileHandler

if TYPE_CHECKING:  # pragma: no cover
    from logging import Logger


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
        as_posix = Path(self.absolute_path).as_posix()
        for pattern, mimetype in self.mime_map.items():
            if not re.search(pattern, as_posix):  # pragma: no cover
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
