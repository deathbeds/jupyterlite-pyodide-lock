"""JupyterLite addon base for ``pyodide-lock.json``."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

from __future__ import annotations

from logging import Logger
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jupyterlite_pyodide_kernel.addons._base import _BaseAddon  # noqa: PLC2701
from jupyterlite_pyodide_kernel.constants import PYODIDE_LOCK
from traitlets import Bool

from jupyterlite_pyodide_lock.constants import PYODIDE_ADDON, PYODIDE_LOCK_STEM

if TYPE_CHECKING:  # pragma: no cover
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
        help="whether experimental 'pyodide-lock' integration is enabled",
    ).tag(config=True)  # type: ignore[assignment]

    # properties
    @property
    def pyodide_addon(self) -> PyodideAddon:
        """The manager's pyodide addon, which will be reconfigured if needed."""
        return self.manager._addons[PYODIDE_ADDON]  # noqa: SLF001

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
