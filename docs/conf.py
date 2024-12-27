"""documentation for ``jupyterlite-pyodide-lock``."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sphinx.application import Sphinx


RTD = "READTHEDOCS"
NL = "\n"
CONF_PY = Path(__file__)
HERE = CONF_PY.parent
ROOT = HERE.parent
SPX_J2 = HERE / "sphinx-j2.toml"


if not os.getenv("PIXI_PROJECT_ROOT"):
    # provide a fake root doc
    root_doc = "rtd"

    def setup(app: Sphinx) -> None:
        """Customize the sphinx build lifecycle."""

        def _run_pixi(*_args: Any) -> None:
            args = ["pixi", "run", "docs-rtd"]
            env = {k: v for k, v in os.environ.items() if "PIXI_" not in k}
            subprocess.check_call(args, env=env, cwd=str(ROOT))  # noqa: S603

        app.connect("build-finished", _run_pixi)

else:

    def load_from_pyproject_toml() -> dict[str, Any]:
        """Read templated sphinx config."""
        import json

        import tomllib
        from jinja2 import Template

        spx_j2 = tomllib.loads(SPX_J2.read_text(encoding="utf-8"))
        print(*spx_j2.keys())  # noqa: T201
        ctx = {
            k: tomllib.load((HERE / f"{v}").open("rb"))
            for k, v in spx_j2["context"].items()
        }
        config = json.loads(Template(json.dumps(spx_j2["template"])).render(**ctx))
        config.update(
            intersphinx_mapping={k: (v, None) for k, v in spx_j2["intersphinx"].items()}
        )
        return config

    globals().update(load_from_pyproject_toml())
