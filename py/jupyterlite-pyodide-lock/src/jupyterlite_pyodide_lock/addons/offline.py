"""A JupyterLite addon for resolving remote ``pyodide-lock.json``."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

from __future__ import annotations

import json
import re
import urllib.parse
from copy import deepcopy
from hashlib import sha256
from typing import TYPE_CHECKING, Any, ClassVar

from doit.tools import config_changed
from jupyterlite_core.constants import JSON_FMT, JUPYTERLITE_JSON, UTF8
from jupyterlite_core.trait_types import TypedTuple
from jupyterlite_pyodide_kernel.constants import PYODIDE
from packaging.utils import canonicalize_name
from traitlets import Bool, Unicode, default

from jupyterlite_pyodide_lock import __version__
from jupyterlite_pyodide_lock.addons._base import BaseAddon
from jupyterlite_pyodide_lock.constants import (
    PYODIDE_LOCK_OFFLINE,
    PYODIDE_LOCK_STEM,
    RE_REMOTE_URL,
)

if TYPE_CHECKING:
    from logging import Logger
    from pathlib import Path

    from jupyterlite_core.manager import LiteManager
    from packaging.utils import NormalizedName

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

    extra_includes: tuple[str] = TypedTuple(
        Unicode(),
        help="more regular expressions for package names to download for offline usage",
    ).tag(config=True)

    excludes: tuple[str] = TypedTuple(
        Unicode(),
        help="regular expressions to exclude from downloading",
    ).tag(config=True)

    extra_excludes: tuple[str] = TypedTuple(
        Unicode(), help="more regular expressions to exclude from downloading"
    ).tag(config=True)

    prune: bool = Bool(
        default_value=False, help="prune packages not requested to be offline"
    ).tag(config=True)  # type: ignore[assignment]

    @default("excludes")
    def _default_excludes(self) -> tuple[str, ...]:
        """Provide default patterns of package names to ignore."""
        return (".*-tests$",)

    @default("includes")
    def _default_includes(self) -> tuple[str, ...]:
        """Provide default patterns of package names to always include.

        The list of default packages are buried inside the TypeScript side
        of ``jupyterlite-pyodide-kernel``:

        * ``packages/pyodide-kernel/src/worker.ts:initKernel``

        And can be extended by users:

        * ``packages/pyodide-kernel/src/tokens.ts:loadPyodideOptions``

        """
        return (
            "^comm$",
            "^ipykernel*",
            "^micropip$",
            "^piplite$",
            "^pyodide-kernel$",
            "^sqlite3$",
            "^ssl$",
        )

    # properties
    @property
    def offline_lockfile(self) -> Path:
        """A convenience property for a derived offline ``pyodide-lock`` output."""
        return self.lockfile.parent / PYODIDE_LOCK_OFFLINE

    @property
    def all_includes(self) -> list[str]:
        """Get all inclusion patterns."""
        return sorted({
            *self.includes,
            *self.extra_includes,
            *self.pyodide_lock_addon.extra_preload_packages,
        })

    @property
    def all_excludes(self) -> list[str]:
        """Get all exclusion patterns."""
        return sorted({*self.excludes, *self.extra_excludes})

    # JupyterLite API methods
    def status(self, manager: LiteManager) -> TTaskGenerator:
        """Report on the status of offline ``pyodide-lock``."""

        def _status() -> None:
            from textwrap import indent

            lines = [
                f"""enabled:      {self.enabled}""",
                f"""includes:     {"  ".join(self.all_includes)}""",
                f"""excludes:     {"  ".join(self.all_excludes)}""",
                f"""version:      {__version__}""",
                f"""static path:  {self.lock_output_dir}""",
            ]
            print(indent("\n".join(lines), "    "), flush=True)

        yield self.task(name="offline", actions=[_status])

    def post_build(self, manager: LiteManager) -> TTaskGenerator:
        """Collect all the packages and generate a ``pyodide-lock.json`` file."""
        if not self.enabled:  # pragma: no cover
            return

        config_str = f"""
            includes:  {self.all_includes}
            excludes:  {self.all_excludes}
            prune:     {self.prune}
        """

        yield dict(
            name="offline",
            actions=[self.resolve_offline],
            file_dep=[self.lockfile],
            targets=[self.offline_lockfile],
            uptodate=[config_changed(config_str)],
        )

        jupyterlite_json = self.output_dir / JUPYTERLITE_JSON

        yield self.task(
            name="patch",
            actions=[(self.patch_config, [jupyterlite_json, self.offline_lockfile])],
            file_dep=[jupyterlite_json, self.lockfile, self.offline_lockfile],
            uptodate=[config_changed(config_str)],
        )

    # offline logic
    def resolve_offline(self) -> bool:
        """Download and rewrite lockfile with selected packages and dependencies."""
        lock_data = json.loads(self.lockfile.read_text(**UTF8))

        raw_packages: dict[str, dict[str, Any]] = lock_data["packages"]

        leaf_included, dep_included = self.get_included_names(raw_packages)

        new_packages = self.get_pruned_packages(
            raw_packages, leaf_included, dep_included
        )

        lock_data["packages"] = new_packages

        out_dir = self.lockfile.parent
        stem = f"../../static/{PYODIDE_LOCK_STEM}"

        for pkg_name in sorted({*leaf_included, *dep_included}):
            self.resolve_one_offline(pkg_name, out_dir, stem, new_packages)

        self.offline_lockfile.write_text(json.dumps(lock_data, **JSON_FMT))

        return True

    def resolve_one_offline(
        self,
        pkg_name: str,
        out_dir: Path,
        stem: str,
        packages: dict[str, dict[str, Any]],
    ) -> None:
        """Rewrite a single package's info (if needed)."""
        pkg_info = packages[pkg_name]
        file_name = pkg_info["file_name"]
        if not re.match(RE_REMOTE_URL, file_name):
            self.log.debug(
                "[offline] [%s] already available locally %s", pkg_name, file_name
            )
            return
        url = urllib.parse.urlparse(file_name)
        whl_name = url.path.split("/")[-1]
        cache_whl = self.package_cache / whl_name
        pyodide_whl = self.pyodide_addon.output_pyodide / whl_name
        dest = out_dir / whl_name
        dest_url: str | None = None

        if not dest.exists() and pyodide_whl.exists():
            dest = pyodide_whl
            dest_url = f"../../static/{PYODIDE}/{whl_name}"

        if not dest.exists():
            if not cache_whl.exists():  # pragma: no cover
                self.log.info("[offline] [%s] fetching %s", pkg_name, file_name)
                self.fetch_one(file_name, cache_whl)
            self.copy_one(cache_whl, dest)

        pkg_info["file_name"] = dest_url or f"""{stem}/{whl_name}"""
        old_sha256 = pkg_info["sha256"]
        whl_sha256 = sha256(dest.read_bytes()).hexdigest()
        if old_sha256 != whl_sha256:  # pragma: no cover
            self.log.warning(
                "[offline] fixing sha256 for %s: lock:%s observed:%s wheel:%s",
                pkg_name,
                old_sha256,
                whl_sha256,
                whl_name,
            )
            pkg_info["sha256"] = whl_sha256

    def get_pruned_packages(
        self,
        raw_packages: dict[str, dict[str, Any]],
        leaf_included: set[NormalizedName],
        dep_included: set[NormalizedName],
    ) -> dict[str, dict[str, Any]]:
        """Provide a copy of packages, potentially with pruning."""
        any_included = {*leaf_included, *dep_included}
        raw_packages = deepcopy(raw_packages)

        if self.prune:
            new_packages = {
                pkg_name: pkg_info
                for pkg_name, pkg_info in raw_packages.items()
                if pkg_name in any_included
            }
        else:
            new_packages = raw_packages

        pruned_names = sorted(p for p in raw_packages if p not in new_packages)
        self.log.warning(
            "[offline]\t%s packages pruned: %s", len(pruned_names), pruned_names
        )
        self.log.warning(
            "[offline]\t%s packages remain: %s", len(new_packages), sorted(new_packages)
        )

        return new_packages

    def get_included_names(
        self, raw_packages: dict[str, dict[str, Any]]
    ) -> tuple[set[NormalizedName], set[NormalizedName]]:
        """Generate the lock."""
        includes = self.all_includes
        excludes = self.all_excludes

        leaf_included: set[NormalizedName] = set()
        check_deps: set[NormalizedName] = set()

        # get leaf deps on first pass
        for raw_name, pkg_info in raw_packages.items():
            pkg_name = canonicalize_name(raw_name)
            if not self.is_included(raw_name, includes=includes, excludes=excludes):
                self.log.debug("[offline] [%s] is excluded", pkg_name)
                continue
            leaf_included = {pkg_name, *leaf_included}
            check_deps = {*check_deps, *map(canonicalize_name, pkg_info["depends"])}

        self.log.debug(
            "[offline] %s leaf deps: %s", len(leaf_included), sorted(leaf_included)
        )
        self.log.debug(
            "[offline] %s deps to check: %s", len(check_deps), sorted(check_deps)
        )

        dep_included: set[NormalizedName] = set()

        while check_deps:
            pkg_name = check_deps.pop()
            if pkg_name in leaf_included or pkg_name in dep_included:
                continue
            dep_included = {*dep_included, pkg_name}
            new_deps = {*map(canonicalize_name, raw_packages[pkg_name]["depends"])}
            if new_deps:
                self.log.debug("[offline] dep %s depends on: %s", pkg_name, new_deps)
                check_deps = {*check_deps, *new_deps}

        return leaf_included, dep_included

    def is_included(
        self, pkg_name: str, includes: list[str], excludes: list[str]
    ) -> bool:
        """Get the URL and filename if a package should be downloaded."""
        if any(re.match(exclude, pkg_name) for exclude in excludes):
            return False

        if not any(re.match(include, pkg_name) for include in includes):
            return False

        return True
