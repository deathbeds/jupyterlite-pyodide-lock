"""A ``tornado`` handler with some extra MIME handling."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tornado.web import StaticFileHandler

from jupyterlite_pyodide_lock.constants import FILE_EXT_MIME_MAP

if TYPE_CHECKING:
    from logging import Logger


class ExtraMimeFiles(StaticFileHandler):
    """Serve static files, with configurable MIME types."""

    log: Logger

    #: map URL regex to content type
    mime_map: dict[str, str]

    def initialize(
        self, log: Logger, mime_map: dict[str, str] | None = None, **kwargs: Any
    ) -> None:
        """Initialize handler instance members."""
        super().initialize(**kwargs)
        self.mime_map = dict(FILE_EXT_MIME_MAP)
        self.mime_map.update(mime_map or {})
        self.log = log

    def get_content_type(self) -> str:
        """Find an overloaded MIME type."""
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
            "[tornado] serving %s as %s (of %s %s)",
            self.absolute_path,
            from_map or from_parent,
            from_parent,
            from_map,
        )
        return from_map or from_parent
