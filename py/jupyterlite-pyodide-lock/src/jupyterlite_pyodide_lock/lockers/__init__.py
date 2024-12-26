"""`pyodide-lock.json` resolvers."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

from __future__ import annotations

import warnings
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from jupyterlite_core.addons import entry_points

from jupyterlite_pyodide_lock.constants import LOCKER_ENTRYPOINT, NAME

if TYPE_CHECKING:
    from importlib.metadata import EntryPoint


@lru_cache(1)
def get_locker_entry_points(force: Any = None) -> dict[str, EntryPoint]:
    """Discover (and cache) modern entrypoints as a ``dict`` with sorted keys.

    Pass some noise (like ``date.date``) to the ``force`` argument to reload.
    """
    all_entry_points = {}
    for entry_point in entry_points(group=LOCKER_ENTRYPOINT):
        name = entry_point.name
        if name in all_entry_points:  # pragma: no cover
            warnings.warn(f"[{NAME}] [{name}] locker already registered.", stacklevel=2)
            continue
        all_entry_points[name] = entry_point
    return dict(sorted(all_entry_points.items()))
