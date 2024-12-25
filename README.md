# jupyterlite-pyodide-lock

> Build reproducible Jupyter Lite sites with [jupyterlite-pyodide-kernel][jlpk]
> and [pyodide-lock][pl].

View the full documentation on [ReadTheDocs][rtfd].

## Example

> **⚠️ EXPERIMENTAL**
>
> These packages are not yet released. See the [GitHub repo][gh] for development
> status.

[gh]: https://github.com/deathbeds/jupyterlite-pyodide-lock


## Overview

By default, a `pyodide` distribution provides a precise set of package versions
known to work together in the browser.

`micropip` gives site users the ability to install packages from PyPI, made more
familiar to IPython users with the `%pip` magic provided by `jupyterlite-pyodide-kernel`,
which itself uses `micropip` to provide additional packages to enable interactive
computing.

`micropip` (and `%pip`) are powerful for interactive usage, but can cause significant
headaches when upstream versions (or their dependencies) change in ways that either
no longer work with `pyodide`, or no longer match the expected versions of JupyterLab
extensions in a deployed JupyterLite site.

`jupyterlite-pyodide-lock` provides a way to use your browser to perform a
validated solve at _build time_, creating a `pyodide-lock.json` which precisely
controls the _run time_ behavior of package downloading and installation.


[jlpk]: https://github.com/jupyterlite/pyodide-kernel
[pl]: https://github.com/pyodide/pyodide-lock
[rtfd]: https://jupyterlite-pyodide-lock.rtfd.org/en/latest
