"""a JupyterLite addon for supporting pyodide-lock.json files"""

import json
import re
import urllib.parse
from hashlib import sha256
from pathlib import Path
from typing import (
    TYPE_CHECKING,
)
from typing import (
    List as _List,
)
from typing import (
    Tuple as _Tuple,
)
from typing import (
    Type as _Type,
)
from typing import (
    Union as _Union,
)

from jupyterlite_core.constants import JUPYTERLITE_JSON, LAB_EXTENSIONS
from jupyterlite_core.trait_types import TypedTuple
from jupyterlite_pyodide_kernel.addons._base import _BaseAddon
from jupyterlite_pyodide_kernel.constants import (
    ALL_WHL,
    PKG_JSON_PIPLITE,
    PKG_JSON_WHEELDIR,
    PYODIDE,
    PYODIDE_LOCK,
)
from traitlets import Bool, Enum, Unicode

from .. import __version__
from ..constants import LOAD_PYODIDE_OPTIONS, OPTION_LOCK_FILE_URL, PYODIDE_LOCK_STEM
from ..lockers import get_locker_entry_points

if TYPE_CHECKING:
    from ..lockers._base import BaseLocker

LOCKERS = get_locker_entry_points()


class PyodideLockAddon(_BaseAddon):
    """Creates and configures a `pyodide-lock.json`

    Can handle PEP508 specs, wheels, special pyodide packages, and their dependencies.
    """

    __all__ = ["status", "post_init", "post_build"]

    flags = {
        "pyodide-lock-enabled": (
            {"PyodideLockAddon": {"enabled": True}},
            "enable pyodide-lock features",
        )
    }

    # traits
    enabled: bool = Bool(
        default_value=False,
        help="whether experimental pyodide-lock integration is enabled",
    ).tag(config=True)

    specs: _Tuple[str] = TypedTuple(
        Unicode(), help="raw pep508 requirements for pyodide dependencies"
    ).tag(config=True)

    packages: _Tuple[str] = TypedTuple(
        Unicode(),
        help="URLs of packages, or local (folders of) packages for pyodide depdendencies",
    ).tag(config=True)

    locker = Enum(
        default_value="browser",
        values=[*LOCKERS.keys()],
        help="approach to use for running pyodide and solving the lock",
    ).tag(config=True)

    # API methods

    def status(self, manager):
        """report on the status of pyodide"""

        def _status():
            from textwrap import indent

            lines = [
                f"""version:      {__version__}""",
                f"""enabled:      {self.enabled}""",
                f"""all lockers:  {", ".join(LOCKERS.keys())}""",
            ]

            if self.enabled:
                lines += [
                    f"""locker:      {self.locker}""",
                    f"""specs:       {", ".join(self.specs)}""",
                    f"""packages:    {", ".join(self.packages)}""",
                ]

            print(indent("\n".join(lines), "    "), flush=True)

        yield self.task(name="lock", actions=[_status])

    def post_init(self, manager):
        """handle downloading of packages to the package cache"""
        if not self.enabled:
            return

        for path_or_url in self.packages:
            yield from self.resolve_one_file_requirement(
                path_or_url,
                self.package_cache,
                self.lock_output_dir,
            )

    def post_build(self, manager):
        """collect all the packages and generate a `pyodide-lock.json` file

        This includes those provided by federated labextensions (such as
        `jupyterlite-pyodide-kernel` iteself), copied during `build:federated_extensions`.
        """
        if not self.enabled:
            return

        args = {
            "packages": [],
            "specs": self.specs,
            "lockfile": self.lockfile,
        }

        package_dirs = [
            self.package_cache,
            self.well_known_packages,
            *self.federated_wheel_dirs,
        ]

        for path in package_dirs:
            for glob in ["*.zip", "*.whl"]:
                args["packages"] += [*path.glob(glob)]

        yield dict(
            name="lock",
            actions=[(self.lock, [], args)],
            file_dep=args["packages"],
            targets=[args["lockfile"]],
        )

        jupyterlite_json = self.manager.output_dir / JUPYTERLITE_JSON

        yield dict(
            name="patch",
            actions=[(self.patch_lite_config, [jupyterlite_json])],
            file_dep=[jupyterlite_json, self.lockfile],
        )

    # actions
    def lock(self, packages: _List[Path], specs: _List[str], lockfile: Path):
        """generate the lockfile"""
        locker_ep: _Type["BaseLocker"] = LOCKERS.get(self.locker)

        if locker_ep is None:
            return False

        try:
            locker_class = locker_ep.load()
        except Exception as err:
            self.log.error("Failed to load locker %s: %s", self.locker, err)
            return False

        # build
        locker: "BaseLocker" = locker_class(
            parent=self, specs=specs, packages=packages, lockfile=lockfile
        )

        locker.resolve_sync()
        return self.lockfile.exists()

    def patch_lite_config(self, jupyterlite_json: Path):
        settings = self.get_pyodide_settings(jupyterlite_json)
        rel = self.lockfile.relative_to(self.manager.output_dir).as_posix()
        lock_hash = sha256(self.lockfile.read_bytes()).hexdigest()
        settings.setdefault(LOAD_PYODIDE_OPTIONS, {}).update(
            {OPTION_LOCK_FILE_URL: f"./{rel}?sha256={lock_hash}"}
        )
        self.set_pyodide_settings(jupyterlite_json, settings)

    # derived properties
    @property
    def output_pyodide(self):
        """where pyodide will go in the output folder"""
        return self.manager.output_dir / "static" / PYODIDE

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
    def federated_wheel_dirs(self) -> _List[Path]:
        pkg_jsons: _List[Path] = []
        extensions = self.manager.output_dir / LAB_EXTENSIONS
        for glob in ["*/package.json", "@*/*/package.json"]:
            pkg_jsons += [*extensions.glob(glob)]

        wheel_paths: _List[Path] = []

        for pkg_json in sorted(pkg_jsons):
            pkg_data = json.load(pkg_json.open())
            wheel_dir = pkg_data.get(PKG_JSON_PIPLITE, {}).get(PKG_JSON_WHEELDIR)
            if wheel_dir:
                wheel_path = pkg_json.parent / f"{wheel_dir}"
                if wheel_path.exists():
                    wheel_paths += [wheel_path]

        return wheel_paths

    # utilties
    def resolve_one_file_requirement(
        self, path_or_url: _Union[str, Path], cache_root: Path
    ):
        """download a wheel, and copy to the cache"""
        local_path: Path = None

        if re.findall(r"^https?://", path_or_url):
            url = urllib.parse.urlparse(path_or_url)
            name = f"""{url.path.split("/")[-1]}"""
            dest = cache_root / name
            local_path = dest
            if not dest.exists():
                yield self.task(
                    name=f"fetch:{name}",
                    doc=f"fetch the wheel {name}",
                    actions=[(self.fetch_one, [path_or_url, dest])],
                    targets=[dest],
                )
        else:
            local_path = (self.manager.lite_dir / path_or_url).resolve()

            if local_path.is_dir():
                for wheel in list_packages(local_path):
                    yield from self.copy_wheel(wheel, cache_root)
            elif local_path.exists():
                suffix = local_path.suffix

                if suffix in [".whl", ".zip"]:
                    yield from self.copy_wheel(local_path, cache_root)

            else:  # pragma: no cover
                raise FileNotFoundError(path_or_url)


def list_packages(package_dir: Path):
    """get all wheels we know how to handle in a directory"""
    return sorted(
        sum([[*package_dir.glob(f"*{pkg}")] for pkg in [*ALL_WHL, ".zip"]], [])
    )
