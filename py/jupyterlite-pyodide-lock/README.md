# jupyterlite-pyodide-lock

> Create pre-solved environments for jupyterlite-pyodide-kernel with pyodide-lock.

## Installing

> This package is not yet released. See `CONTRIBUTING.md` for development.
>
> ```
> pip install jupyterlite-pyodide-lock
> ```
>
> or mamba/conda:
>
> ```bash
> mamba install -c conda-forge jupyterlite-pyodide-lock
> ```

## Why Use This?

- in the browser
  - fetches `pyodide-kernel`, its dependencies, and configured packages in parallel
    while `pyodide` is starting, skpping `micropip.install` and its requests to
    the PyPI API
  - doesn't require `%pip install` for locked packages and their dependencies
    - notebooks and scripts still need to be well-formed, e.g. `import my_package`
    - once shipped, package versions loaded in the browser won't change over time
- during a build
  - doesn't require rebuilding a full custom `pyodide` distribution
    - but will patch an custom deployed `pyodide`
    - all downloaded wheels can be optionally shipped along with the application
  - optionally clamp PyPI packages to a known timestamp to ensure newer packages
    aren't found during a future solve
  - supports multiple sources of custom wheels and dependencies

### Feature Comparison

A number of approaches are available for getting reproducible JupyterLite runtime
python environments, either with `jupyterlite-pyodide-kernel` or other kernels.
Choosing one requires some trades of simplicity, reproducibility, flexibility,
and performance.

> **Note**
>
> Each tool is evolving, so the tables below should be verified against the
> different tools when making a decision.

<details>

<summary>A <b>visitor</b> to a JupyterLite site's needs may be the top priority...</summary>

|                               feature | `jupyterlite-pyodide-lock` | `piplite`    | [jupyterlite-xeus] | [micropip]  |
| ------------------------------------: | -------------------------- | ------------ | ------------------ | ----------- |
| needs separate `install` and `import` | no (for locked packages)   | yes (`%pip`) | no                 | no          |
|           allows install by PyPI name | yes                        | yes          | no                 | yes         |
|               allows install from URL | yes                        | yes          | no                 | yes         |
|        blocks interaction per package | run cell                   | run cell     | start kernel       | run cell    |
|                 caches in the browser | per package                | per package  | whole environment  | per package |

</details>

<details>

<summary>An <b>author</b> of a JupyterLite site may have additional needs...</summary>

|                                 feature | `jupyterlite-pyodide-lock`       | `piplite` | [jupyterlite-xeus]  | [pyodide-build]  |
| --------------------------------------: | -------------------------------- | --------- | ------------------- | ---------------- |
|     requires "heavy" build dependencies | real browser (and/or `selenium`) | no        | minimal, _see repo_ | many, _see repo_ |
|                      ships local wheels | yes                              | yes       | maybe?              | yes              |
|                ships noarch PyPI wheels | yes                              | yes       | yes                 | yes              |
|         ships pyodide emscripten wheels | yes                              | yes       | no                  | yes              |
|      ships arbitrary pyodide zip C libs | no                               | yes       | no                  | yes              |
| locks multiple versions of same package | no                               | yes       | no                  | no               |
|         optionally clamp to a timestamp | yes                              | no        | no                  | no               |

</details>

[jupyterlite-xeus]: https://github.com/jupyterlite/xeus
[emscripten-forge]: https://github.com/emscripten-forge
[pyodide-build]: https://github.com/pyodide/pyodide/tree/main/pyodide-build
[micropip]: https://github.com/pyodide/micropip

## Usage

### Configure

#### Requirements

A number of ways to add requirements to the lock file are supported:

- adding wheels in `{lite_dir}/static/pyodide-lock`
- configuring `specs` as a list of PEP508 dependency specs
- configuring `packages` as a list of
  - URLs to remote wheels that will be downloaded and cached
  - local paths relative to `lite_dir` of `.whl` files (or folders of wheels)

```yaml
# examples/jupyter_lite_config.json
{ "PyodideLockAddon": { "enabled": true, "specs": [
          # pep508 spec
          "ipywidgets >=8.1,<8.2",
        ], "packages": [
          # a wheel
          "../dist/ipywidgets-8.1.2-py3-none-any.whl",
          # a folder of wheels
          "../dist",
        ] } }
```

#### Lockers

The _Locker_ is responsible for starting a browser, executing `micopip.install`
and `micropip.freeze` to try to get a viable lock file solution.

```yaml
{ "PyodideLockAddon": {
      "enabled": true,
      # the default locker: uses naive a `subprocess.Popen` approach
      "locker": "browser",
    }, "BrowserLocker": {
      # requires `firefox` or `firefox.exe` on PATH
      "browser": "firefox",
      "headless": true,
      "private_mode": true,
      "temp_profile": true,
    } }
```

A convenience CLI options will show some information about detected browsers:

```bash
jupyter pyodide-lock browsers
```

#### Reproducible Locks

By configuring the _lock date_ to a UNIX epoch timestamp, artifacts from a PyPI
index newer than that date will be filtered out before a lock is attempted.

Combined with a fixed `pyodide_url` archive, this should prevent known packages
and their dependencies from "drifting."

```yaml
{
  "PyodideAddon":
    {
      "pyodide_url": f"https://github.com/pyodide/pyodide/releases/download/0.25.0/pyodide-core-0.25.0.tar.bz2",
    },
  "PyodideLockAddon": { "enabled": true, "lock_date_epoch": 1712980201 },
}
```

Alternately, this can be provided by environemnt variable:

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

...or `git`, for the last commit time of a file:

```bash
git log -1 --format=%ct requirements.txt
```

The latter approch, using version control metadata, is recommended, as it
shifts the burden of bookkeeping to a verifiable source.

</details>
