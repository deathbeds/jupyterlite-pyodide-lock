"""JupyterLite addon base for ``pyodide-lock.json``."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

from __future__ import annotations

from hashlib import sha256
from logging import Logger
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jupyterlite_pyodide_kernel.addons._base import _BaseAddon  # noqa: PLC2701
from jupyterlite_pyodide_kernel.constants import PYODIDE_JS, PYODIDE_LOCK
from jupyterlite_pyodide_kernel.constants import PYODIDE_URL as OPTION_PYODIDE_URL
from traitlets import Bool

from jupyterlite_pyodide_lock.constants import (
    LOAD_PYODIDE_OPTIONS,
    OPTION_LOCK_FILE_URL,
    OPTION_PACKAGES,
    PYODIDE_ADDON,
    PYODIDE_LOCK_ADDON,
    PYODIDE_LOCK_OFFLINE_ADDON,
    PYODIDE_LOCK_STEM,
)

if TYPE_CHECKING:
    from collections.abc import Generator
    from logging import Logger

    from jupyterlite_pyodide_kernel.addons.pyodide import PyodideAddon

    TTaskGenerator = Generator[dict[str, Any], None, None]


class BaseAddon(_BaseAddon):  # type: ignore[misc]
    """A base for ``jupyterlite-pyodide-lock`` addons."""

    log: Logger

    # traits
    enabled: bool = Bool(
        default_value=False,
        help="whether 'pyodide-lock' integration is enabled",
    ).tag(config=True)  # type: ignore[assignment]

    # properties
    @property
    def addons(self) -> dict[str, _BaseAddon]:
        addons: dict[str, _BaseAddon] = self.manager._addons  # noqa: SLF001
        return addons

    @property
    def pyodide_addon(self) -> PyodideAddon:
        """The manager's pyodide addon, which will be reconfigured if needed."""
        return self.addons[PYODIDE_ADDON]

    @property
    def pyodide_lock_addon(self) -> BaseAddon:
        """The manager's pyodide-lock addon."""
        addon: BaseAddon = self.addons[PYODIDE_LOCK_ADDON]
        return addon

    @property
    def pyodide_lock_offline_addon(self) -> BaseAddon:
        """The manager's pyodide-lock offline addon."""
        addon: BaseAddon = self.addons[PYODIDE_LOCK_OFFLINE_ADDON]
        return addon

    @property
    def output_dir(self) -> Path:
        """Provide `jupyterlite_core.addons.base.LiteBuildConfig.output_dir`."""
        return Path(self.manager.output_dir)

    @property
    def lite_dir(self) -> Path:
        """Provide `jupyterlite_core.addons.base.LiteBuildConfig.lite_dir`."""
        return Path(self.manager.lite_dir)

    @property
    def cache_dir(self) -> Path:
        """Provide `jupyterlite_core.addons.base.LiteBuildConfig.cache_dir`."""
        return Path(self.manager.cache_dir)

    @property
    def lock_output_dir(self) -> Path:
        """The folder where the ``pyodide-lock.json`` and packages will be stored."""
        return self.output_dir / "static" / f"{PYODIDE_LOCK_STEM}"

    @property
    def lockfile(self) -> Path:
        """The ``pyodide-lock.json`` file in the ``{output_dir}``."""
        return self.lock_output_dir / f"{PYODIDE_LOCK}"

    @property
    def package_cache(self) -> Path:
        """The root of the ``pyodide-lock`` cache."""
        return self.cache_dir / f"{PYODIDE_LOCK_STEM}"

    def patch_config(self, jupyterlite_json: Path, lockfile: Path) -> None:
        """Update the runtime ``jupyter-lite-config.json``."""
        self.log.debug("[lock] patching %s for pyodide-lock", jupyterlite_json)

        settings = self.get_pyodide_settings(jupyterlite_json)

        output_js = self.pyodide_addon.output_pyodide / PYODIDE_JS
        url = f"./{output_js.relative_to(self.output_dir).as_posix()}"

        settings[OPTION_PYODIDE_URL] = url

        rel = lockfile.relative_to(self.output_dir).as_posix()
        lock_hash = sha256(lockfile.read_bytes()).hexdigest()
        load_pyodide_options = settings.setdefault(LOAD_PYODIDE_OPTIONS, {})

        lock_addon = self.pyodide_lock_addon

        if TYPE_CHECKING:
            from jupyterlite_pyodide_lock.addons.lock import PyodideLockAddon

            assert isinstance(lock_addon, PyodideLockAddon)

        preload = [
            *load_pyodide_options.get(OPTION_PACKAGES, []),
            *lock_addon.preload_packages,
            *lock_addon.extra_preload_packages,
        ]

        load_pyodide_options.update(
            {
                OPTION_LOCK_FILE_URL: f"./{rel}?sha256={lock_hash}",
                OPTION_PACKAGES: sorted(set(preload)),
            },
        )

        self.set_pyodide_settings(jupyterlite_json, settings)
        self.log.info("[lock] patched %s for %s", jupyterlite_json, lockfile.name)
