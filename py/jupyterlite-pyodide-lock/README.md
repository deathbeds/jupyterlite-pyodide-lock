# jupyterlite-pyodide-lock

> Create pre-solved environments for jupyterlite-pyodide-kernel with pyodide-lock.

|            docs             |                                          install                                           |                build                 |
| :-------------------------: | :----------------------------------------------------------------------------------------: | :----------------------------------: |
| [![docs][docs-badge]][docs] | [![install from pypi][pypi-badge]][pypi] [![install from conda-forge][conda-badge]][conda] | [![build][workflow-badge]][workflow] |

[docs]: https://jupyterlite-pyodide-lock.rtfd.org
[docs-badge]:
  https://readthedocs.org/projects/jupyterlite-pyodide-lock/badge/?version=latest
[conda-badge]: https://img.shields.io/conda/vn/conda-forge/jupyterlite-pyodide-lock
[conda]: https://anaconda.org/conda-forge/jupyterlite-pyodide-lock
[pypi-badge]: https://img.shields.io/pypi/v/jupyterlite-pyodide-lock
[pypi]: https://pypi.org/project/jupyterlite-pyodide-lock
[workflow-badge]:
  https://github.com/deathbeds/jupyterlite-pyodide-lock/actions/workflows/test.yml/badge.svg?branch=main
[workflow]:
  https://github.com/deathbeds/jupyterlite-pyodide-lock/actions/workflows/test.yml?query=branch%3Amain

View the full documentation on [ReadTheDocs][rtfd].

[rtfd]: https://jupyterlite-pyodide-lock.rtfd.org/en/latest

## Installing

```bash
pip install jupyterlite-pyodide-lock
```

or:

```bash
mamba install -c conda-forge jupyterlite-pyodide-lock
```

## Usage

### Configure

#### Requirements

A number of ways to add requirements to the lock file are supported:

- adding wheels in `{lite_dir}/static/pyodide-lock`
- configuring `specs` as a list of PEP508 dependency specs
- configuring `packages` as a list of
  - URLs to remote wheels that will be downloaded and cached
  - local paths relative to `lite_dir` of `.whl` files (or folders of wheels)

```json
{
  "PyodideLockAddon": {
    "enabled": true,
    "specs": ["ipywidgets >=8.1,<8.2"],
    "packages": ["../dist/ipywidgets-8.1.2-py3-none-any.whl", "../dist"]
  }
}
```

#### Lockers

The _Locker_ is responsible for starting a browser, executing `micopip.install` and
`micropip.freeze` to try to get a viable lock file solution.

```json
{
  "PyodideLockAddon": {
    "enabled": true,
    "locker": "browser"
  },
  "BrowserLocker": {
    "browser": "firefox",
    "headless": true,
    "private_mode": true,
    "temp_profile": true
  }
}
```

A convenience CLI options will show some information about detected browsers:

```bash
jupyter pyodide-lock browsers
```

#### Reproducible Locks

By configuring the _lock date_ to a UNIX epoch timestamp, artifacts from a PyPI index
newer than that date will be filtered out before a lock is attempted.

Combined with a fixed `pyodide_url` archive, this should prevent known packages and
their dependencies from "drifting."

```json
{
  "PyodideAddon": {
    "pyodide_url": "https://github.com/pyodide/pyodide/releases/download/0.27.0/pyodide-core-0.27.0.tar.bz2"
  },
  "PyodideLockAddon": { "enabled": true, "lock_date_epoch": 1712980201 }
}
```

Alternately, this can be provided by environment variable:

```bash
JLPL_LOCK_DATE_EPOCH=$(date -u +%s) jupyter lite build
```

<details>

<summary>Getting a <code>lock_date_epoch</code></summary>

As shown in the example above, `date` can provide this:

```bash
date -u +%s
```

Or `python`:

```py
>>> from datetime import datetime, timezone
>>> int(datetime.now(tz=timezone.utc).timestamp())
```

... or `git`, for the last commit time of a file:

```bash
git log -1 --format=%ct requirements.txt
```

The latter approach, using version control metadata, is recommended, as it shifts the
burden of bookkeeping to a verifiable source.

</details>
