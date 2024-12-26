"""A JupyterLite addon for patching ``pyodide-lock.json`` files."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

from __future__ import annotations

import functools
import json
import operator
import os
import pprint
import re
import urllib.parse
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, ClassVar

import pkginfo
from doit.tools import config_changed
from jupyterlite_core.constants import JUPYTERLITE_JSON, LAB_EXTENSIONS, UTF8
from jupyterlite_core.trait_types import TypedTuple
from jupyterlite_pyodide_kernel.constants import (
    ALL_WHL,
    PKG_JSON_PIPLITE,
    PKG_JSON_WHEELDIR,
    PYODIDE_LOCK,
)
from traitlets import CInt, Enum, Unicode, default

from jupyterlite_pyodide_lock import __version__
from jupyterlite_pyodide_lock.addons._base import BaseAddon
from jupyterlite_pyodide_lock.constants import (
    ENV_VAR_LOCK_DATE_EPOCH,
    PYODIDE_CDN_URL,
    PYODIDE_CORE_URL,
    PYODIDE_LOCK_STEM,
    RE_REMOTE_URL,
    WAREHOUSE_UPLOAD_FORMAT,
)
from jupyterlite_pyodide_lock.lockers import get_locker_entry_points

if TYPE_CHECKING:
    from importlib.metadata import EntryPoint
    from logging import Logger
    from pathlib import Path

    from jupyterlite_core.manager import LiteManager

    from jupyterlite_pyodide_lock.addons._base import TTaskGenerator
    from jupyterlite_pyodide_lock.lockers._base import BaseLocker

LOCKERS = get_locker_entry_points()


class PyodideLockAddon(BaseAddon):
    """Patches a ``pyodide``  to include ``pyodide-kernel`` and custom packages.

    Can handle PEP508 specs, wheels, and their dependencies.

    Special ``pyodide``-specific ``.zip`` packages are not supported.
    """

    #: advertise JupyterLite lifecycle hooks
    __all__: ClassVar = ["pre_status", "status", "post_init", "post_build"]

    log: Logger

    # cli
    aliases: ClassVar = {
        "pyodide-lock-date-epoch": "PyodideLockAddon.lock_date_epoch",
    }

    # traitlets
    locker = Enum(
        default_value="BrowserLocker",
        values=[*LOCKERS.keys()],
        help=(
            "approach to use for running 'pyodide' and solving the lock: "
            "these will have further configuration options under the same-named"
            "configurable"
        ),
    ).tag(config=True)

    pyodide_url: str = Unicode(
        default_value=PYODIDE_CORE_URL,
        help=(
            "a URL, folder, or path to a pyodide distribution, patched into"
            " ``PyodideAddon.pyodide_url``"
        ),
    )  # type: ignore[assignment]

    pyodide_cdn_url: str = Unicode(
        default_value=PYODIDE_CDN_URL,
        help="the URL prefix for all packages not managed by ``pyodide-lock``",
    )  # type: ignore[assignment]

    specs: tuple[str] = TypedTuple(
        Unicode(),
        help="PEP-508 specifications for pyodide dependencies",
    ).tag(config=True)

    packages: tuple[str] = TypedTuple(
        Unicode(),
        help=(
            "URLs of packages, or local (folders of) packages for pyodide dependencies"
        ),
    ).tag(config=True)

    preload_packages: tuple[str] = TypedTuple(
        Unicode(),
        default_value=[
            "ssl",
            "sqlite3",
            "ipykernel",
            "comm",
            "pyodide_kernel",
            "ipython",
        ],
        help=(
            "``pyodide_kernel`` dependencies to add to"
            " ``PyodideAddon.loadPyodideOptions.packages``: "
            " these will be downloaded and installed, but _not_ imported to sys.modules"
        ),
    ).tag(config=True)

    extra_preload_packages: tuple[str] = TypedTuple(
        Unicode(),
        help=(
            "extra packages to add to PyodideAddon.loadPyodideOptions.packages: "
            "these will be downloaded and installed, but _not_ imported to sys.modules"
        ),
    ).tag(config=True)

    bootstrap_wheels: tuple[str] = TypedTuple(
        Unicode(),
        default_value=("micropip", "packaging"),
        help="packages names from the lockfile to ensure before attempting a lock",
    ).tag(config=True)

    lock_date_epoch: int = CInt(
        allow_none=True,
        min=1,
        help=(
            "Trigger reproducible locks, clamping available "
            "package timestamps to this value"
        ),
    ).tag(config=True)  # type: ignore[assignment]

    # JupyterLite API methods
    def pre_status(self, manager: LiteManager) -> TTaskGenerator:
        """Patch configuration of ``PyodideAddon`` if needed."""
        if not self.enabled or self.pyodide_addon.pyodide_url:
            return

        self.pyodide_addon.pyodide_url = self.pyodide_url

        yield self.task(
            name="patch:pyodide",
            actions=[lambda: print("    PyodideAddon.pyodide_url was patched")],
        )

    def status(self, manager: LiteManager) -> TTaskGenerator:
        """Report on the status of ``pyodide-lock``."""

        def _status() -> None:
            from textwrap import indent

            lines = [
                f"""enabled:      {self.enabled}""",
                f"""all lockers:  {", ".join(LOCKERS.keys())}""",
                f"""lock date:    {self.lock_date_epoch}""",
                f"""version:      {__version__}""",
            ]

            if self.lock_date_epoch:
                lde_ts = datetime.fromtimestamp(self.lock_date_epoch, tz=timezone.utc)
                lines += [
                    """              """
                    f"""(iso8601: {lde_ts.strftime(WAREHOUSE_UPLOAD_FORMAT)})""",
                ]

            if self.enabled:
                lines += [
                    f"""locker:       {self.locker}""",
                    f"""specs:        {", ".join(self.specs)}""",
                    f"""packages:     {", ".join(self.packages)}""",
                    f"""fallback:     {self.pyodide_cdn_url}""",
                ]

            print(indent("\n".join(lines), "    "), flush=True)

        yield self.task(name="lock", actions=[_status])

    def post_init(self, manager: LiteManager) -> TTaskGenerator:
        """Handle downloading of packages to the package cache."""
        if not self.enabled:  # pragma: no cover
            return

        for path_or_url in [
            *self.packages,
            *map(str, list_packages(self.well_known_packages)),
        ]:
            yield from self.resolve_one_file_requirement(
                path_or_url,
                self.package_cache,
            )

    def post_build(self, manager: LiteManager) -> TTaskGenerator:
        """Collect all the packages and generate a ``pyodide-lock.json`` file.

        This includes those provided by federated labextensions (such as
        ``jupyterlite-pyodide-kernel`` itself), copied during
        ``build:federated_extensions``, which will be left in-place.
        """
        if not self.enabled:  # pragma: no cover
            return

        out = self.pyodide_addon.output_pyodide
        out_lockfile = out / PYODIDE_LOCK
        out_lock = json.loads(out_lockfile.read_text(**UTF8))

        lock_dep_wheels = []

        for dep in self.bootstrap_wheels:
            file_name = out_lock["packages"][dep]["file_name"]
            out_whl = out / file_name
            if out_whl.exists():
                continue
            lock_dep_wheels += [out_whl]
            url = f"{self.pyodide_cdn_url}/{file_name}"
            yield self.task(
                name=f"bootstrap:{dep}",
                actions=[(self.fetch_one, [url, out_whl])],
                targets=[out_whl],
            )

        args = {
            "packages": self.get_packages(),
            "specs": self.specs,
            "lockfile": self.lockfile,
        }

        config_str = f"""
            args:                   {pprint.pformat(args)}
            lock date:              {self.lock_date_epoch}
            locker:                 {self.locker}
            locker_config:          {self.locker_config}
        """

        yield self.task(
            name="lock",
            uptodate=[config_changed(config_str)],
            actions=[(self.lock, [], args)],
            file_dep=[  # type: ignore[misc]
                *args["packages"],
                *lock_dep_wheels,
                self.pyodide_addon.output_pyodide / PYODIDE_LOCK,
            ],
            targets=[self.lockfile],
        )

        if self.pyodide_lock_offline_addon.enabled:
            self.log.warning("[lock] deferring patch to PyodideLockOfflineAddon")
            return

        jupyterlite_json = self.output_dir / JUPYTERLITE_JSON

        yield self.task(
            name="patch",
            actions=[(self.patch_config, [jupyterlite_json, self.lockfile])],
            file_dep=[jupyterlite_json, self.lockfile],
            uptodate=[config_changed(config_str)],
        )

    # actions
    def lock(self, packages: list[Path], specs: list[str], lockfile: Path) -> bool:
        """Generate the lockfile."""
        locker_ep: EntryPoint | None = LOCKERS.get(self.locker)

        if locker_ep is None:  # pragma: no cover
            return False

        try:
            locker_class = locker_ep.load()
        except Exception:  # pragma: no cover
            self.log.exception("[lock] failed to load locker %s", self.locker)
            return False

        # build
        locker: BaseLocker = locker_class(
            parent=self,
            specs=specs,
            packages=packages,
            lockfile=lockfile,
        )

        if self.lockfile.exists():
            self.lockfile.unlink()

        locker.resolve_sync()

        return self.lockfile.exists()

    # traitlets
    @default("lock_date_epoch")
    def _default_lock_date_epoch(self) -> int | None:
        if ENV_VAR_LOCK_DATE_EPOCH not in os.environ:
            return None
        return int(json.loads(os.environ[ENV_VAR_LOCK_DATE_EPOCH]))

    # derived properties
    @property
    def well_known_packages(self) -> Path:
        """The location of ``.whl`` in the ``{lite_dir}`` to pick up."""
        return self.lite_dir / "static" / f"{PYODIDE_LOCK_STEM}"

    @property
    def federated_wheel_dirs(self) -> list[Path]:
        """The locations of wheels referenced by federated labextensions."""
        pkg_jsons: list[Path] = []
        extensions = self.output_dir / LAB_EXTENSIONS
        for glob in ["*/package.json", "@*/*/package.json"]:
            pkg_jsons += [*extensions.glob(glob)]

        wheel_paths: list[Path] = []

        for pkg_json in sorted(pkg_jsons):
            pkg_data = json.loads(pkg_json.read_text(**UTF8))
            wheel_dir = pkg_data.get(PKG_JSON_PIPLITE, {}).get(PKG_JSON_WHEELDIR)
            if not wheel_dir:  # pragma: no cover
                continue
            wheel_path = pkg_json.parent / f"{wheel_dir}"
            if not wheel_path.exists():  # pragma: no cover
                self.log.warning(
                    "`%s` in %s does not exist",
                    PKG_JSON_WHEELDIR,
                    pkg_json,
                )
            else:
                wheel_paths += [wheel_path]

        return wheel_paths

    @property
    def locker_config(self) -> Any:
        """A preview of the locker config."""
        try:
            ep = LOCKERS[self.locker]
            configurable = ep.value.split(":")[-1]
            return self.config.get(configurable)
        except KeyError as err:  # pragma: no cover
            self.log.warning(
                "[lock] failed to check %s locker config: %s", self.locker, err
            )
            return None

    # task generators
    def resolve_one_file_requirement(
        self, path_or_url: str | Path, cache_root: Path
    ) -> TTaskGenerator:
        """Download a wheel, and copy to the cache."""
        if re.findall(RE_REMOTE_URL, f"{path_or_url}"):
            url = urllib.parse.urlparse(f"{path_or_url}")
            name = f"""{url.path.split("/")[-1]}"""
            cached = cache_root / name
            if not cached.exists():
                yield self.task(
                    name=f"fetch:{name}",
                    doc=f"fetch the wheel {name}",
                    actions=[(self.fetch_one, [f"{path_or_url}", cached])],
                    targets=[cached],
                )
            yield from self.copy_wheel(cached)
        else:
            local_path = (self.manager.lite_dir / path_or_url).resolve()

            if local_path.is_dir():
                for wheel in list_packages(local_path):
                    yield from self.copy_wheel(wheel)

            elif local_path.exists():
                suffix = local_path.suffix

                if suffix != ".whl":  # pragma: no cover
                    self.log.warning("[lock] %s is not a wheel, ignoring", local_path)
                else:
                    yield from self.copy_wheel(local_path)

            else:  # pragma: no cover
                raise FileNotFoundError(path_or_url)

    def copy_wheel(self, wheel: Path) -> TTaskGenerator:
        """Copy one wheel to ``{output_dir}``."""
        dest = self.lock_output_dir / wheel.name
        if dest == wheel:  # pragma: no cover
            return
        yield self.task(
            name=f"copy:whl:{wheel.name}",
            file_dep=[wheel],
            targets=[dest],
            actions=[(self.copy_one, [wheel, dest])],
        )

    def get_packages(self) -> list[Path]:
        """Find all file-based packages to install with ``micropip``."""
        package_dirs = [
            *self.federated_wheel_dirs,
        ]

        wheels: list[Path] = []

        for path in package_dirs:
            wheels += [*path.glob("*.whl")]

        named_packages = {}

        for wheel in sorted(wheels, key=lambda x: x.name):
            metadata = pkginfo.get_metadata(str(wheel))
            if not metadata:  # pragma: no cover
                self.log.error("[lock] failed to parse wheel metadata for %s", wheel)
                continue
            named_packages[metadata.name] = wheel

        return sorted(named_packages.values())


def list_packages(package_dir: Path) -> list[Path]:
    """Get all wheels we know how to handle in a directory."""
    return sorted(
        functools.reduce(
            operator.iadd, ([[*package_dir.glob(f"*{pkg}")] for pkg in [*ALL_WHL]])
        )
    )
