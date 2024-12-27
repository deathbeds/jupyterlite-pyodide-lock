# jupyterlite-pyodide-lock

> Build reproducible Jupyter Lite sites with [jupyterlite-pyodide-kernel][jlpk] and
> [pyodide-lock][pl].

View the full documentation on [ReadTheDocs][rtfd].

[jlpk]: https://github.com/jupyterlite/pyodide-kernel
[pl]: https://github.com/pyodide/pyodide-lock
[rtfd]: https://jupyterlite-pyodide-lock.rtfd.org/en/latest

> **⚠️ EXPERIMENTAL**
>
> These packages are not yet released. See the [GitHub repo][gh] for development status.

[gh]: https://github.com/deathbeds/jupyterlite-pyodide-lock

## Overview

`jupyterlite-pyodide-lock` avoids **run time** `pyodide` and `jupyterlite` package
management ambiguity by using a full web browser at **build time** to customize a
`pyodide-lock.json`.

## Examples

Use `jupyterlite-pyodide-lock` to [minimally](#minimal-example) provide a more
controlled baseline `pyodide` runtime environment, or ensure complex dependencies like
[widgets](#widgets-example) are consistent over time.

### Minimal Example

<details>

<summary>
  <i>Ensure <code>pyodide-kernel</code>'s dependencies are locked, assuming
  <code>pip</code> and <code>firefox</code>.</i>
</summary>

#### Create the Minimal Build Environment

- make a `requirements.txt`

  ```text
  jupyterlite-core ==0.4.5
  jupyterlite-pyodide-kernel ==0.4.6
  jupyterlite-pyodide-lock ==0.1.0a0
  ```

- Run:

  ```bash
  pip install -r requirements.txt
  ```

#### Configure the Minimal Site

- build a `jupyter_lite_config.json`:

  ```json
  {
    "PyodideLockAddon": {
      "enabled": true
    }
  }
  ```

#### Build the Minimal Site

- build a `jupyter_lite_config.json`:

  ```bash
  jupyter lite build
  ```

#### Check the Minimal Site Works

- start a simple, local development server

  ```bash
  cd _output
  python -m http.server -b 127.0.0.1
  ```

- visit the site at `http://127.0.0.1:8000/`
- make a new Notebook
  - use basic `python` features

</details>

### Widgets Example

<details>

<summary>
  <i>Build a JupyterLite site with all the packages needed to run
  <code>ipywidgets</code> in a Notebook, assuming <code>mamba</code>.</i>
</summary>

#### Create the Widget Build Environment

- make an `environment.yml`

  ```yaml
  channels:
    - conda-forge
    - nodefaults
  dependencies:
    - ipywidgets ==8.1.5
    - jupyterlite-core ==0.4.5
    - jupyterlite-pyodide-kernel ==0.4.6
    - jupyterlite-pyodide-lock-recommended ==0.1.0a0
  ```

  - _the `-recommended` package includes `firefox` and `geckodriver`_
  - _optionally use a tool like [`conda-lock`][conda-lock] or [`pixi`][pixi] to create a
    lockfile for the build environment_

[conda-lock]: https://github.com/conda-incubator/conda-lock
[pixi]: https://github.com/prefix-dev/pixi

- Run:

  ```bash
  mamba env update --file environment.yml --prefix .venv
  source activate .venv # or just `activate .venv` on windows
  ```

#### Configure the Widgets Site

- build a `jupyter_lite_config.json`:

  ```json
  {
    "PyodideLockAddon": {
      "enabled": true,
      "specs": ["ipywidgets ==8.1.5"]
    },
    "PyodideLockOfflineAddon": {
      "enabled": true,
      "extra_includes": ["ipywidgets"]
    }
  }
  ```

  - _note the tight `ipywidgets` pin, ensuring compatibility with the build environment_

#### Build the Site with Widgets

- build a `jupyter_lite_config.json`:

  ```bash
  jupyter lite build
  ```

#### Check Widgets Works Offline

- disconnect from the internet ✈️
  - _this step is optional, but is the most reliable way to validate a reproducible
    site_
- start a simple, local development server

  ```bash
  cd _output
  python -m http.server -b 127.0.0.1
  ```

- visit the site at `http://127.0.0.1:8000/`
- make a new Notebook

  - see that `ipywidgets` can be imported, and widgets work:

    ```python
    import ipywidgets
    ipywidgets.FloatSlider()
    ```

</details>

## Motivation

- By default, a `pyodide` distribution provides a precise set of hundreds of package
  versions known to work together in the browser, described in its `pyodide-lock.json`.

- Among these packages is `micropip`, which gives site users the ability to install
  packages _not_ included in `pyodide-lock.json`. These may be distributed with an HTML
  page, downloaded from PyPI, or anywhere on the internet. `jupyterlite-pyodide-kernel`
  uses this capability to install itself, and its dependencies.

  - At run time, `piplite` provides a `micropip`-based shim for the IPython `%pip`
    magic, the most portable approach for interactive package management in Notebook
    documents.

- `micropip` (and `%pip`) are powerful for interactive usage, but can cause headaches
  when upstream versions (or their dependencies) change in ways that either no longer
  provide the same API expected by the exact versions of `pyodide`, `pyodide-kernel`,
  and JupyterLab extensions in a deployed JupyterLite site.

`jupyterlite-pyodide-lock` gives content authors tools to manage their effective
`pyodide` distribution, making it easier to build, verify, and maintain predictable,
interactive computing environments for future site visitors.
