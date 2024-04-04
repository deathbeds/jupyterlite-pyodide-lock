"""Create pre-solved environments for jupyterlite-pyodide-kernel"""

__all__ = ["__version__"]
__version__ = __import__("importlib.metadata").metadata.version(
    "jupyterlite-pyodide-lock",
)
