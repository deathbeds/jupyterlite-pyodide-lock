"""documentation for ``jupyterlite-pyodide-lock``."""

import datetime
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib


RTD = bool(json.loads(os.environ.get("READTHEDOCS", "False").lower()))

if RTD:
    buildinfo = Path(os.environ["READTHEDOCS_OUTPUT"]) / "html/.buildinfo"
    if buildinfo.exists():
        sys.exit(0)


CONF_PY = Path(__file__)
HERE = CONF_PY.parent
ROOT = HERE.parent
PYPROJ = ROOT / "pyproject.toml"
PROJ_DATA = tomllib.loads(PYPROJ.read_text(encoding="utf-8"))
RE_GH = (
    r"https://github.com"
    r"/(?P<github_user>.*?)"
    r"/(?P<github_repo>.*?)"
    r"/tree/(?P<github_version>.*)"
)
REPO_INFO = re.search(RE_GH, PROJ_DATA["project"]["urls"]["Source"])
NOW = datetime.datetime.now(tz=datetime.timezone.utc).date()

# metadata
author = PROJ_DATA["project"]["authors"][0]["name"]
project = PROJ_DATA["project"]["name"]
copyright = f"{NOW.year}, {author}"


# The full version, including alpha/beta/rc tags
release = PROJ_DATA["project"]["version"]

# The short X.Y version
version = ".".join(release.rsplit(".", 1))

# sphinx config
extensions = [
    "sphinx.ext.autodoc",
    "sphinx_autodoc_typehints",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "myst_nb",
    "sphinx.ext.autosectionlabel",
    "sphinx_copybutton",
    "autodoc_traits",
]

# content
autoclass_content = "both"
always_document_param_types = True
typehints_defaults = "comma"
typehints_use_signature_return = True
autodoc_default_options = {
    "members": True,
    "show-inheritance": True,
    "undoc-members": True,
}
autosectionlabel_prefix_document = True
myst_heading_anchors = 3

on_rtd = lambda pkg, proj: {pkg: (f"https://{proj}.readthedocs.io/en/stable", None)}

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    **on_rtd("jupyterlite_core", "jupyterlite"),
    **on_rtd("traitlets", "traitlets"),
    **on_rtd("jupyterlite_pyodide_kernel", "jupyterlite-pyodide-kernel"),
}


# warnings
suppress_warnings = ["autosectionlabel.*"]

# theme
templates_path = ["_templates"]
html_static_path = [
    "../dist",
    "../contrib/jupyterlite-pyodide-lock-webdriver/dist",
    "../build/docs-app",
    "_static",
]
html_theme = "pydata_sphinx_theme"
html_css_files = ["theme.css"]

html_theme_options = {
    "github_url": PROJ_DATA["project"]["urls"]["Source"],
    "use_edit_page_button": REPO_INFO is not None,
    "logo": {"text": PROJ_DATA["project"]["name"]},
    "icon_links": [
        {
            "name": "PyPI",
            "url": PROJ_DATA["project"]["urls"]["PyPI"],
            "icon": "fa-brands fa-python",
        }
    ],
    "navigation_with_keys": False,
    "pygment_light_style": "github-light-colorblind",
    "pygment_dark_style": "github-dark-colorblind",
    "header_links_before_dropdown": 10,
}

html_sidebars: dict[str, Any] = {"demo": []}

if REPO_INFO is not None:
    html_context = {**REPO_INFO.groupdict(), "doc_path": "docs"}
