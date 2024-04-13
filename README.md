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

## Usage

### Configure

#### Requirements

A number of `requirements` specifications are supported:

```yaml
# examples/jupyter_lite_config.json
{
  "PyodideLockAddon": {
    "enabled": true,
    "requirements": [
      # wheels in {lite_dir}/static/pyodide-lock will be found
      "ipywidgets >=8.1,<8.2"     # pep508 spec
      "../dist",                  # (folders of) wheels
      "-r requirements.txt",      # requirements files
      "../pyproject.toml[lite]"   # pyproject.toml with an extra
    ]
  }
}
```

#### Lockers

The _Locker_ is responsible for starting a browser, executing `micopip.install`
and `micropip.freeze` to try to get a viable lock file solution.

```yaml
{
  "PyodideLockAddon": {
    "enabled": true,
    "locker": "browser"     # the default locker: uses `subprocess`
  },
  "BrowserLocker": {
    "browser": "firefox",   # requires `firefox` or `firefox.exe` on PATH
    "headless": true,
    "private_mode": true,
    "temp_profile": true
  }
}
```

#### Reproducible Locks

By configuring the _lock date_ to a UNIX epoch timestamp, artifacts from a PyPI
index newer than that date will be filtered out before a lock is attempted.

Combined with a fixed `pyodide_url` archive, this should prevent known packages
and their dependencies from "drifting."

```yaml
{
  "PyodideAddon": {
    "pyodide_url": f"https://github.com/pyodide/pyodide/releases/download/0.25.0/pyodide-core-0.25.0.tar.bz2"
  },
  "PyodideLockAddon": {
    "enabled": true,
    "lock_date_epoch": 1712980201
  }
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
