"""a JupyterLite addon for patching pyodide-lock.json files"""

import json
import re
import urllib.parse
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any

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
from traitlets import Bool, Enum, Unicode

from .. import __version__
from ..constants import (
    LOAD_PYODIDE_OPTIONS,
    OPTION_LOCK_FILE_URL,
    OPTION_PACKAGES,
    PYODIDE_ADDON,
    PYODIDE_CDN_URL,
    PYODIDE_CORE_URL,
    PYODIDE_LOCK_STEM,
)
from ..lockers import get_locker_entry_points

if TYPE_CHECKING:  # pragma: no cover
    from jupyterlite_pyodide_kernel.addons.pyodide import PyodideAddon

    from ..lockers._base import BaseLocker

LOCKERS = get_locker_entry_points()


class PyodideLockAddon(_BaseAddon):
    """Patches a `pyodide` distribution to include `pyodide-kernel` and custom packages.

    Can handle PEP508 specs, wheels, and their dependencies.

    Special `pyodide`-specific `.zip` packages are _not_ supported.
    """

    __all__ = ["pre_status", "status", "post_init", "post_build"]

    # cli
    flags = {
        "pyodide-lock": (
            {"PyodideLockAddon": {"enabled": True}},
            "enable pyodide-lock features",
        ),
    }

    # traits
    enabled: bool = Bool(
        default_value=False,
        help="whether experimental pyodide-lock integration is enabled",
    ).tag(config=True)

    locker = Enum(
        default_value="browser",
        values=[*LOCKERS.keys()],
        help=(
            "approach to use for running pyodide and solving the lock: "
            "these will have further configuration options"
        ),
    ).tag(config=True)

    pyodide_url: str = Unicode(
        default_value=PYODIDE_CORE_URL,
        help="a URL, folder, or path to a pyodide distribution, patched into `PyodideAddon.pyodide_url`",
    )

    pyodide_cdn_url: str = Unicode(
        default_value=PYODIDE_CDN_URL,
        help="the URL prefix for all packages not managed by `pyodide-lock`",
    )

    specs: tuple[str] = TypedTuple(
        Unicode(),
        help="raw pep508 requirements for pyodide dependencies",
    ).tag(config=True)

    packages: tuple[str] = TypedTuple(
        Unicode(),
        help="URLs of packages, or local (folders of) packages for pyodide depdendencies",
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
            "`pyodide_kernel` dependencies to add to PyodideAddon.loadPyodideOptions.packages: "
            "these will be downloaded and installed, but _not_ imported to sys.modules"
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

    # API methods

    def pre_status(self, manager):
        """Patch configuration of `PyodideAddon` if needed."""
        if not self.enabled or self.pyodide_addon.pyodide_url:
            return

        self.pyodide_addon.pyodide_url = self.pyodide_url

        yield self.task(
            name="patch:pyodide",
            actions=[lambda: print("    PyodideAddon.pyodide_url was patched")],
        )

    def status(self, manager):
        """Report on the status of pyodide"""

        def _status():
            from textwrap import indent

            lines = [
                f"""version:      {__version__}""",
                f"""enabled:      {self.enabled}""",
                f"""all lockers:  {", ".join(LOCKERS.keys())}""",
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

    def post_init(self, manager):
        """Handle downloading of packages to the package cache"""
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

    def post_build(self, manager):
        """Collect all the packages and generate a `pyodide-lock.json` file

        This includes those provided by federated labextensions (such as
        `jupyterlite-pyodide-kernel` iteself), copied during `build:federated_extensions`.
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

        config_str = f"""{args} {self.locker} {self.locker_config}"""

        yield self.task(
            name="lock",
            uptodate=[config_changed(config_str)],
            actions=[(self.lock, [], args)],
            file_dep=[
                *args["packages"],
                *lock_dep_wheels,
                self.pyodide_addon.output_pyodide / PYODIDE_LOCK,
            ],
            targets=[args["lockfile"]],
        )

        jupyterlite_json = self.manager.output_dir / JUPYTERLITE_JSON

        yield self.task(
            name="patch",
            actions=[(self.patch_lite_config, [jupyterlite_json])],
            file_dep=[jupyterlite_json, self.lockfile],
        )

    # actions
    def lock(self, packages: list[Path], specs: list[str], lockfile: Path):
        """Generate the lockfile"""
        locker_ep: type["BaseLocker"] = LOCKERS.get(self.locker)

        if locker_ep is None:  # pragma: no cover
            return False

        try:
            locker_class = locker_ep.load()
        except Exception as err:  # pragma: no cover
            self.log.error("Failed to load locker %s: %s", self.locker, err)
            return False

        # build
        locker: "BaseLocker" = locker_class(
            parent=self,
            specs=specs,
            packages=packages,
            lockfile=lockfile,
        )

        locker.resolve_sync()
        return self.lockfile.exists()

    def patch_lite_config(self, jupyterlite_json: Path):
        print(f"Patching {jupyterlite_json} for pyodide-lock", flush=True)

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
        print(f"Patched {jupyterlite_json} for pyodide-lock", flush=True)

    # derived properties
    @property
    def pyodide_addon(self) -> "PyodideAddon":
        """The manager's pyodide addon, which will be reconfigured if needed."""
        return self.manager._addons[PYODIDE_ADDON]

    @property
    def well_known_packages(self) -> Path:
        return self.manager.lite_dir / "static" / PYODIDE_LOCK_STEM

    @property
    def lockfile(self) -> Path:
        return self.lock_output_dir / PYODIDE_LOCK

    @property
    def lock_output_dir(self) -> Path:
        """The folder where the `pyodide-lock.json` and packages will be stored."""
        return self.manager.output_dir / "static" / PYODIDE_LOCK_STEM

    @property
    def package_cache(self) -> Path:
        return self.manager.cache_dir / PYODIDE_LOCK_STEM

    @property
    def federated_wheel_dirs(self) -> list[Path]:
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
            self.log.warning("Failed to check %s locker config: %s", self.locker, err)
            return None

    # task generators
    def resolve_one_file_requirement(self, path_or_url: str | Path, cache_root: Path):
        """Download a wheel, and copy to the cache"""
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
                    self.log.warning("%s is not a wheel, ignoring", local_path)
                else:
                    yield from self.copy_wheel(local_path)

            else:  # pragma: no cover
                raise FileNotFoundError(path_or_url)

    def copy_wheel(self, wheel):
        """Copy one wheel to output"""
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
        package_dirs = [
            self.lock_output_dir,
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


def list_packages(package_dir: Path):
    """Get all wheels we know how to handle in a directory"""
    return sorted(sum([[*package_dir.glob(f"*{pkg}")] for pkg in [*ALL_WHL]], []))
