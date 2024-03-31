"""`pyodide-lock.json` resolvers."""

import warnings
from functools import lru_cache

from jupyterlite_core.addons import entry_points

from ..constants import LOCKER_ENTRYPOINT, NAME


@lru_cache(1)
def get_locker_entry_points(force=None):
    """Discover (and cache) modern entrypoints as a ``dict`` with sorted keys.

    Pass some noise (like `date.date`) to the ``force`` argument to reload.
    """
    all_entry_points = {}
    for entry_point in entry_points(group=LOCKER_ENTRYPOINT):
        name = entry_point.name
        if name in all_entry_points:  # pragma: no cover
            warnings.warn(f"[{NAME}] [{name}] locker already registered.", stacklevel=2)
            continue
        all_entry_points[name] = entry_point
    return dict(sorted(all_entry_points.items()))
