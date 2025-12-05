"""Locker implementation ``jupyterlite-pyodide-lock-uv``."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

from __future__ import annotations

from jupyterlite_pyodide_lock.lockers._base import BaseLocker  # noqa: PLC2701


class UvLocker(BaseLocker):
    """A locker that uses ``uv pip compile``."""

    async def fetch(self) -> None:
        """Get the lock."""
