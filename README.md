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
    - once shipped, package versions loaded in the browser won't change over time
- during a build
  - doesn't require rebuilding a full custom `pyodide` distribution
    - but will patch an custom deployed `pyodide`
    - all downloaded wheels can be optionally shipped along with the application
  - optionally uses `SOURCE_DATE_EPOCH` to ensure newer packages aren't
    found during a solve
  - supports multiple sources of custom wheels and dependencies

## Usage

### Configure

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

### Build

Running `jupyter lite build` with the above example will:

- find all the referenced wheels, including `pyodide-kernel` dependencies
- start a web server
  - start a browser
    - load a page with pyodide
    - run `micropip.install`
    - run `micropip.freeze`
    - POST the results back
    - close the browser
  - stop the web server
- normalize the paths in the lockfile
- deploy `{output_dir}/static/pyodide-lock/pyodide-lock.json` and all new wheels
- configure `jupyter-lite.json` to reference the lockfile
