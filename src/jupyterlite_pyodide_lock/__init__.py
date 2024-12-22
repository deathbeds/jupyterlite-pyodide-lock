"""Create pre-solved environments for jupyterlite-pyodide-kernel."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

__all__ = ["__version__"]
__version__ = __import__("importlib.metadata").metadata.version(
    "jupyterlite-pyodide-lock",
)
