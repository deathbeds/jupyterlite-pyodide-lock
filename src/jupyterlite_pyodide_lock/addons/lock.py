"""A JupyterLite addon for patching ``pyodide-lock.json`` files."""

import functools
import json
import operator
import os
import pprint
import re
import urllib.parse
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

import pkginfo
from doit.tools import config_changed
from jupyterlite_core.constants import JUPYTERLITE_JSON, LAB_EXTENSIONS, UTF8
from jupyterlite_core.trait_types import TypedTuple
from jupyterlite_pyodide_kernel.addons._base import _BaseAddon
from jupyterlite_pyodide_kernel.constants import (
    ALL_WHL,
    PKG_JSON_PIPLITE,
    PKG_JSON_WHEELDIR,
    PYODIDE_LOCK,
)
from traitlets import Bool, CInt, Enum, Unicode, default

from jupyterlite_pyodide_lock import __version__
from jupyterlite_pyodide_lock.constants import (
    ENV_VAR_LOCK_DATE_EPOCH,
    LOAD_PYODIDE_OPTIONS,
    OPTION_LOCK_FILE_URL,
    OPTION_PACKAGES,
    PYODIDE_ADDON,
    PYODIDE_CDN_URL,
    PYODIDE_CORE_URL,
    PYODIDE_LOCK_STEM,
    WAREHOUSE_UPLOAD_FORMAT,
)
from jupyterlite_pyodide_lock.lockers import get_locker_entry_points

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Generator
    from importlib.metadata import EntryPoint
    from logging import Logger

    from jupyterlite_core.manager import LiteManager
    from jupyterlite_pyodide_kernel.addons.pyodide import PyodideAddon

    from jupyterlite_pyodide_lock.lockers._base import BaseLocker

    TTaskGenerator = Generator[None, None, dict[str, Any]]

LOCKERS = get_locker_entry_points()


class PyodideLockAddon(_BaseAddon):
    """Patches a ``pyodide``  to include ``pyodide-kernel`` and custom packages.

    Can handle PEP508 specs, wheels, and their dependencies.

    Special ``pyodide``-specific ``.zip`` packages are `not` supported.
    """

    __all__: ClassVar = ["pre_status", "status", "post_init", "post_build"]

    log: "Logger"

    # cli
    flags: ClassVar = {
        "pyodide-lock": (
            {"PyodideLockAddon": {"enabled": True}},
            "enable 'pyodide-lock' features",
        ),
    }

    aliases: ClassVar = {
        "pyodide-lock-date-epoch": "PyodideLockAddon.lock_date_epoch",
    }

    # traits
    enabled: bool = Bool(
        default_value=False,
        help="whether experimental 'pyodide-lock' integration is enabled",
    ).tag(config=True)

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
    )

    pyodide_cdn_url: str = Unicode(
        default_value=PYODIDE_CDN_URL,
        help="the URL prefix for all packages not managed by ``pyodide-lock``",
    )

    specs: tuple[str] = TypedTuple(
        Unicode(),
        help="raw pep508 requirements for pyodide dependencies",
    ).tag(config=True)

    packages: tuple[str] = TypedTuple(
        Unicode(),
        help=(
            "URLs of packages, or local (folders of) packages for pyodide"
            " depdendencies"
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
    ).tag(config=True)

    # API methods

    def pre_status(self, manager: "LiteManager") -> "TTaskGenerator":
        """Patch configuration of ``PyodideAddon`` if needed."""
        if not self.enabled or self.pyodide_addon.pyodide_url:
            return

        self.pyodide_addon.pyodide_url = self.pyodide_url

        yield self.task(
            name="patch:pyodide",
            actions=[lambda: print("    PyodideAddon.pyodide_url was patched")],
        )

    def status(self, manager: "LiteManager") -> "TTaskGenerator":
        """Report on the status of ``pyodide-lock``."""

        def _status() -> None:
            from textwrap import indent

            lines = [
                f"""version:      {__version__}""",
                f"""enabled:      {self.enabled}""",
                f"""all lockers:  {", ".join(LOCKERS.keys())}""",
                f"""lock date:    {self.lock_date_epoch}""",
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

    def post_init(self, manager: "LiteManager") -> "TTaskGenerator":
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

    def post_build(self, manager: "LiteManager") -> "TTaskGenerator":
        """Collect all the packages and generate a ``pyodide-lock.json`` file.

        This includes those provided by federated labextensions (such as
        ``jupyterlite-pyodide-kernel`` iteself), copied during
        ``build:federated_extensions``.
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
            lock date:     {self.lock_date_epoch}
            locker:        {self.locker}
            locker_config: {self.locker_config}
            args:          {pprint.pformat(args)}
        """

        yield self.task(
            name="lock",
            uptodate=[config_changed(config_str)],
            actions=[(self.lock, [], args)],
            file_dep=[
                *args["packages"],
                *lock_dep_wheels,
                self.pyodide_addon.output_pyodide / PYODIDE_LOCK,
            ],
            targets=[self.lockfile],
        )

        jupyterlite_json = self.manager.output_dir / JUPYTERLITE_JSON

        yield self.task(
            name="patch",
            actions=[(self.patch_config, [jupyterlite_json])],
            file_dep=[jupyterlite_json, self.lockfile],
        )

    # actions
    def lock(self, packages: list[Path], specs: list[str], lockfile: Path) -> bool:
        """Generate the lockfile."""
        locker_ep: "EntryPoint" = LOCKERS.get(self.locker)

        if locker_ep is None:  # pragma: no cover
            return False

        try:
            locker_class = locker_ep.load()
        except Exception as err:  # pragma: no cover
            self.log.error("[lock] failed to load locker %s: %s", self.locker, err)
            return False

        # build
        locker: "BaseLocker" = locker_class(
            parent=self,
            specs=specs,
            packages=packages,
            lockfile=lockfile,
        )

        if self.lockfile.exists():
            self.lockfile.unlink()
        locker.resolve_sync()
        return self.lockfile.exists()

    def patch_config(self, jupyterlite_json: Path) -> None:
        """Update the runtime ``jupyter-lite-config.json``."""
        self.log.debug("[lock] patching %s for pyodide-lock", jupyterlite_json)

        settings = self.get_pyodide_settings(jupyterlite_json)
        rel = self.lockfile.relative_to(self.manager.output_dir).as_posix()
        lock_hash = sha256(self.lockfile.read_bytes()).hexdigest()
        load_pyodide_options = settings.setdefault(LOAD_PYODIDE_OPTIONS, {})

        preload = [
            *load_pyodide_options.get(OPTION_PACKAGES, []),
            *self.preload_packages,
            *self.extra_preload_packages,
        ]

        load_pyodide_options.update(
            {
                OPTION_LOCK_FILE_URL: f"./{rel}?sha256={lock_hash}",
                OPTION_PACKAGES: sorted(set(preload)),
            },
        )

        self.set_pyodide_settings(jupyterlite_json, settings)
        self.log.info("[lock] patched %s for pyodide-lock", jupyterlite_json)

    # traitlets
    @default("lock_date_epoch")
    def _default_lock_date_epoch(self) -> int | None:
        if ENV_VAR_LOCK_DATE_EPOCH not in os.environ:
            return None
        return int(json.loads(os.environ[ENV_VAR_LOCK_DATE_EPOCH]))

    # derived properties
    @property
    def pyodide_addon(self) -> "PyodideAddon":
        """The manager's pyodide addon, which will be reconfigured if needed."""
        return self.manager._addons[PYODIDE_ADDON]  # noqa: SLF001

    @property
    def well_known_packages(self) -> Path:
        """The location of ``.whl`` in the ``{lite_dir}`` to pick up."""
        return self.manager.lite_dir / "static" / PYODIDE_LOCK_STEM

    @property
    def lockfile(self) -> Path:
        """The ``pyodide-lock.json`` file in the ``{output_dir}``."""
        return self.lock_output_dir / PYODIDE_LOCK

    @property
    def lock_output_dir(self) -> Path:
        """The folder where the ``pyodide-lock.json`` and packages will be stored."""
        return self.manager.output_dir / "static" / PYODIDE_LOCK_STEM

    @property
    def package_cache(self) -> Path:
        """The root of the ``pyodide-lock`` cache."""
        return self.manager.cache_dir / PYODIDE_LOCK_STEM

    @property
    def federated_wheel_dirs(self) -> list[Path]:
        """The locations of wheels referenced by federated labextensions."""
        pkg_jsons: list[Path] = []
        extensions = self.manager.output_dir / LAB_EXTENSIONS
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
    ) -> "TTaskGenerator":
        """Download a wheel, and copy to the cache."""
        if re.findall(r"^https?://", path_or_url):
            url = urllib.parse.urlparse(path_or_url)
            name = f"""{url.path.split("/")[-1]}"""
            cached = cache_root / name
            if not cached.exists():
                yield self.task(
                    name=f"fetch:{name}",
                    doc=f"fetch the wheel {name}",
                    actions=[(self.fetch_one, [path_or_url, cached])],
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

                if suffix not in [".whl"]:  # pragma: no cover
                    self.log.warning("[lock] %s is not a wheel, ignoring", local_path)
                else:
                    yield from self.copy_wheel(local_path)

            else:  # pragma: no cover
                raise FileNotFoundError(path_or_url)

    def copy_wheel(self, wheel: Path) -> "TTaskGenerator":
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

    def get_packages(self) -> dict[str, Path]:
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
            named_packages[metadata.name] = wheel

        return sorted(named_packages.values())


def list_packages(package_dir: Path) -> list[Path]:
    """Get all wheels we know how to handle in a directory."""
    return sorted(
        functools.reduce(
            operator.iadd, ([[*package_dir.glob(f"*{pkg}")] for pkg in [*ALL_WHL]])
        )
    )
