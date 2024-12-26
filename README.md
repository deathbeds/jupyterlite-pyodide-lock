# jupyterlite-pyodide-lock

> Build reproducible Jupyter Lite sites with [jupyterlite-pyodide-kernel][jlpk]
> and [pyodide-lock][pl].

View the full documentation on [ReadTheDocs][rtfd].

> **⚠️ EXPERIMENTAL**
>
> These packages are not yet released. See the [GitHub repo][gh] for development
> status.

[gh]: https://github.com/deathbeds/jupyterlite-pyodide-lock


## Overview

`jupyterlite-pyodide-lock` avoids **run time** `pyodide` and `jupyterlite` package
management ambiguity by using a full web browser at **build time**  to customize a
`pyodide-lock.json`.


## Motivation

By default, a `pyodide` distribution provides a precise set of package versions
known to work together in the browser, described in its `pyodide-lock.json`.

Among these packages is `micropip`, which gives site users the ability to install
packages _not_ included in `pyodide-lock.json`. These may be distributed with an
HTML page, downloaded from PyPI, or anywhere on the internet.
`jupyterlite-pyodide-kernel` uses this capability to install itself, and its
dependencies.

At run time, `piplite` provides a `micropip`-based shim for the IPython `%pip`
magic, the most portable approach for interactive package management in Notebook documents.

`micropip` (and `%pip`) are powerful for interactive usage, but can cause
headaches when upstream versions (or their dependencies) change in ways that
either no longer provide the same API expected by the exact versions of `pyodide`,
`pyodide-kernel`, and JupyterLab extensions in a deployed JupyterLite site.

`jupyterlite-pyodide-lock` gives content authors tools to manage the effective
`pyodide` distribution, making it easier to build, verify, and maintain predictable,
interactive computing environments for future site visitors.

[jlpk]: https://github.com/jupyterlite/pyodide-kernel
[pl]: https://github.com/pyodide/pyodide-lock
[rtfd]: https://jupyterlite-pyodide-lock.rtfd.org/en/latest
