# jupyterlite-pyodide-lock

> Create pre-solved environments for jupyterlite-pyodide-kernel with pyodide-lock.

## Installing

```
pip install jupyterlite-pyodide-lock
```

or mamba/conda:

```bash
mamba install -c conda-forge jupyterlite-pyodide-lock
```

## Why Use This?

- during a build
  - doesn't require rebuilding a full custom `pyodide` distribution
  - all downloaded wheels can be optionally shipped along with the application
  - optionally uses of `SOURCE_DATE_EPOCH` will ensure newer packages aren't
    used
  - supports multiple sources of custom wheels and dependencies
- in the browser
  - fetches `pyodide-kernel` and dependencies in parallel while `pyodide` is
    starting, skpping `micropip` and many requests to a PyPI API
  - doesn't require `%pip install` for locked packages and their dependencies
    - once shipped, package versions loaded in the browser won't change over time

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
