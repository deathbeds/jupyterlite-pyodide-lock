# jupyterlite-pyodide-lock

> Create pre-solved environments for jupyterlite-pyodide-kernel with pyodide-lock.

## Installing

> This package is not yet released. See `CONTRIBUTING.md` for development.
>
> ```bash
> pip install jupyterlite-pyodide-lock
> ```
>
> or mamba/conda:
>
> ```bash
> mamba install -c conda-forge jupyterlite-pyodide-lock
> ```

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
{ 'PyodideLockAddon': { 'enabled': true, 'specs': [
          # pep508 spec
          'ipywidgets >=8.1,<8.2',
        ], 'packages': [
          # a wheel
          '../dist/ipywidgets-8.1.2-py3-none-any.whl',
          # a folder of wheels
          '../dist',
        ] } }
```

#### Lockers

The _Locker_ is responsible for starting a browser, executing `micopip.install` and
`micropip.freeze` to try to get a viable lock file solution.

```yaml
{ 'PyodideLockAddon': {
      'enabled': true,
      # the default locker: uses naive a `subprocess.Popen` approach
      'locker': 'browser',
    }, 'BrowserLocker': {
      # requires `firefox` or `firefox.exe` on PATH
      'browser': 'firefox',
      'headless': true,
      'private_mode': true,
      'temp_profile': true,
    } }
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

```yaml
{
  'PyodideAddon':
    {
      'pyodide_url': f"https://github.com/pyodide/pyodide/releases/download/0.25.0/pyodide-core-0.25.0.tar.bz2",
    },
  'PyodideLockAddon': { 'enabled': true, 'lock_date_epoch': 1712980201 },
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

The latter approch, using version control metadata, is recommended, as it shifts the
burden of bookkeeping to a verifiable source.

</details>
