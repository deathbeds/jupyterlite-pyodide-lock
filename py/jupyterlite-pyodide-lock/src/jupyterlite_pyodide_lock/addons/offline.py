"""A JupyterLite addon for resolving remote ``pyodide-lock.json``."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

from __future__ import annotations

import json
import re
import urllib.parse
from typing import TYPE_CHECKING, Any, ClassVar

from jupyterlite_core.constants import JSON_FMT, UTF8
from jupyterlite_core.trait_types import TypedTuple
from traitlets import Bool, Unicode, default

from jupyterlite_pyodide_lock import __version__
from jupyterlite_pyodide_lock.addons._base import BaseAddon
from jupyterlite_pyodide_lock.constants import PYODIDE_LOCK_STEM, RE_REMOTE_URL

if TYPE_CHECKING:  # pragma: no cover
    from logging import Logger

    from jupyterlite_core.manager import LiteManager

    from jupyterlite_pyodide_lock.addons._base import TTaskGenerator


class PyodideLockOfflineAddon(BaseAddon):
    """Rewrite ``pyodide-lock.json`` with locally-downloaded packages."""

    #: advertise JupyterLite lifecycle hooks
    __all__: ClassVar = ["status", "post_build"]

    log: Logger

    includes: tuple[str] = TypedTuple(
        Unicode(),
        help="regular expressions for package names to download for offline usage",
    ).tag(config=True)

    excludes: tuple[str] = TypedTuple(
        Unicode(),
        help="regular expressions to exclude from downloading",
    ).tag(config=True)

    extra_exclude: tuple[str] = TypedTuple(
        Unicode(), help="additional regular expressions to exclude from downloading"
    ).tag(config=True)

    prune: bool = Bool(
        default_value=False, help="prune packages not available offline"
    ).tag(config=True)  # type: ignore[assignment]

    @default("offline_excludes")
    def _default_excludes(self) -> tuple[str, ...]:
        """Provide a default set of regular expressions of package names to ignore."""
        return (".*-tests$",)

    # JupyterLite API methods
    def status(self, manager: LiteManager) -> TTaskGenerator:
        """Report on the status of offline ``pyodide-lock``."""

        def _status() -> None:
            from textwrap import indent

            lines = [
                f"""version:      {__version__}""",
            ]
            print(indent("\n".join(lines), "    "), flush=True)

        yield self.task(name="offline", actions=[_status])

    def resolve_offline(self) -> bool:
        """Download and rewrite lockfile with selected packages and dependencies."""
        includes = (*self.includes,)
        excludes = (*self.excludes, *self.extra_exclude)

        lock_data = json.loads(self.lockfile.read_text(**UTF8))

        to_download: dict[str, str] = {}
        file_stem = f"../../static/{PYODIDE_LOCK_STEM}"

        for pkg_name, pkg_info in lock_data["packages"].items():
            pkg_dl = self.resolve_one_offline(pkg_name, pkg_info, includes, excludes)
            if pkg_dl:
                to_download.update(dict(pkg_dl))
                pkg_info["file_name"] = f"{file_stem}/{pkg_dl[1]}"

        out_dir = self.lockfile.parent

        for url, wheel_name in to_download.items():
            cache_whl = self.package_cache / wheel_name
            if not cache_whl.exists():
                self.fetch_one(url, cache_whl)
            self.copy_one(cache_whl, out_dir / wheel_name)

        self.lockfile.write_text(json.dumps(lock_data, **JSON_FMT))

        return True

    def resolve_one_offline(
        self,
        pkg_name: str,
        pkg_info: dict[str, Any],
        includes: tuple[str, ...],
        excludes: tuple[str, ...],
    ) -> dict[str, str]:
        """Get the URL and filename if a package should be downloaded."""
        stem = "[lock] [offline]"
        skip = f"{stem} skipping download of"

        url = urllib.parse.urlparse(pkg_info["url"])
        name = f"""{url.path.split("/")[-1]}"""

        if not re.match(RE_REMOTE_URL, pkg_name):
            self.log.debug("%s local %s", skip, name)
            return {}

        if any(re.match(exclude, pkg_name) for exclude in excludes):
            self.log.debug("%s excluded %s", skip, name)
            return {}

        if not any(re.match(include, pkg_name) for include in includes):
            self.log.debug("%s not-included %s", skip, name)
            return {}

        self.log.info("%s might download %s", stem, name)

        return {url: name}
