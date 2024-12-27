"""A ``tornado`` handler for accepting ``micropip.freeze`` output and errors."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from jupyterlite_core.constants import JSON_FMT, UTF8
from tornado.web import RequestHandler

if TYPE_CHECKING:
    from jupyterlite_pyodide_lock.lockers.browser import BrowserLocker


class MicropipFreeze(RequestHandler):
    """Accept raw ``micropip.freeze`` output from the client and write it to disk."""

    locker: BrowserLocker

    def initialize(self, locker: BrowserLocker, **kwargs: Any) -> None:
        """Initialize instance members."""
        self.locker = locker
        super().initialize(**kwargs)

    async def post(self) -> None:
        """Accept a ``pyodide-lock.json`` as the POST body."""
        # parse and write out the re-normalized lockfile
        lock_json = json.loads(self.request.body)
        if "packages" in lock_json:
            lockfile = self.locker.lockfile_cache
            lockfile.parent.mkdir(parents=True, exist_ok=True)
            lockfile.write_text(json.dumps(lock_json, **JSON_FMT), **UTF8)
            self.locker.log.info("[micropip] wrote 'freeze' output to %s", lockfile)
        else:
            self.locker.log.error(
                "[micropip] unexpected 'freeze' response %s", lock_json
            )

        self.locker._solve_halted = True  # noqa: SLF001

        await self.finish()
