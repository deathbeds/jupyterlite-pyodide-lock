# jupyterlite-pyodide-lock

> Build reproducible Jupyter Lite sites with [jupyterlite-pyodide-kernel][jlpk]
> and [pyodide-lock][pl].

View the full documentation on [ReadTheDocs][rtfd].

[jlpk]: https://github.com/jupyterlite/pyodide-kernel
[pl]: https://github.com/pyodide/pyodide-lock
[rtfd]: https://jupyterlite-pyodide-lock.rtfd.org/en/latest

## Example

> **⚠️ EXPERIMENTAL**
>
> These packages are not yet released. See the [GitHub repo][gh] for development
> status.

[gh]: https://github.com/deathbeds/jupyterlite-pyodide-lock

To build an offline-hostable JupyterLite site:

- Get `mamba`, `micromamba`, `conda`, or some other `$CONDA_EXE` (e.g. [Miniforge][mf])
- Make an `environment.yml` with the `recommended` packages:

  ```yaml
  channels:
    - conda-forge
    # the next line will eventually be removed
    - https://jupyterlite-pyodide-lock.rtfd.org/en/latest/_static
  dependencies:
    - jupyterlite-pyodide-lock-recommended ==0.1.0a0
  ```


- Configure `jupyter_lite_config.json` to install packages:

  ```json
  {
    "PyodideLockAddon": {
      "enabled": true,
      "offline": true,
      "specs": ["ipywidgets >=8.1,<8.2"]
    }
  }
  ```

  - for locally-built (or pre-downloaded) wheels, configure `packages`, e.g.
    `{"PyodideLockAddon": {"packages": ["some-noarch.whl", "dist/]}}`

- Activate the `jlpl` environment and run:

  ```bash
  jupyter lite archive
  ```

- In `_output`, there should be:
  - `static/pyodide-lock`, containing a
    - `pyodide-lock.json` and all the novel packages for
    - `static/pyodide` a minimal subset of the `pyodide` distribution

- Start an HTTP server of the built site:

  ```bash
  cd _output
  python -m http.server -b 127.0.0.1
  ```

- Open your browser to `https://127.0.0.1:8000`

- In-browser `Python (Pyodide)` kernels should have all the packages installed,
  ready to `import ipywidgets`.

[mf]: https://github.com/conda-forge/miniforge

### Next Steps

- add more packages and repeat
- learn more on [ReadTheDocs][rtfd]
