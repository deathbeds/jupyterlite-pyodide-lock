# jupyterlite-pyodide-lock

> Build reproducible Jupyter Lite sites with [jupyterlite-pyodide-kernel][jlpk] and
> [pyodide-lock][pl].

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

[jlpk]: https://github.com/jupyterlite/pyodide-kernel
[pl]: https://github.com/pyodide/pyodide-lock
[rtfd]: https://jupyterlite-pyodide-lock.rtfd.org/en/latest

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
  jupyterlite-core ==0.7.0
  jupyterlite-pyodide-kernel ==0.7.0
  jupyterlite-pyodide-lock ==0.1.2
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
    - ipywidgets ==8.1.8
    - jupyterlite-core ==0.7.0
    - jupyterlite-pyodide-kernel ==0.7.0
    - jupyterlite-pyodide-lock-recommended ==0.1.2
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
      "constraints": ["traitlets ==5.14.3"],
      "specs": ["ipywidgets ==8.1.8"],
      "extra_preload_packages": ["ipywidgets"]
    },
    "PyodideLockOfflineAddon": {
      "enabled": true
    }
  }
  ```

  - _note the tight `ipywidgets` pin, ensuring compatibility with the build environment_
  - _while not required, the `constraints` option allows for controlling transitive
    dependencies_
    - _this feature requires `micropip >=0.9.0`, which is only compatible with
      `pyodide >=0.27`_

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
  packages _not_ included in `pyodide-lock.json`. These may be served along with an HTML
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
