# jupyterlite-pyodide-lock-webdriver

> A `jupyterlite-pyodide-lock` lock strategy using the [WebDriver] standard.

[webdriver]: https://www.w3.org/TR/webdriver

|            docs             |                                          install                                           |                build                 |
| :-------------------------: | :----------------------------------------------------------------------------------------: | :----------------------------------: |
| [![docs][docs-badge]][docs] | [![install from pypi][pypi-badge]][pypi] [![install from conda-forge][conda-badge]][conda] | [![build][workflow-badge]][workflow] |

[docs]: https://jupyterlite-pyodide-lock.rtfd.org
[docs-badge]:
  https://readthedocs.org/projects/jupyterlite-pyodide-lock/badge/?version=latest
[conda-badge]:
  https://img.shields.io/conda/vn/conda-forge/jupyterlite-pyodide-lock-webdriver
[conda]: https://anaconda.org/conda-forge/jupyterlite-pyodide-lock-webdriver
[pypi-badge]: https://img.shields.io/pypi/v/jupyterlite-pyodide-lock-webdriver
[pypi]: https://pypi.org/project/jupyterlite-pyodide-lock-webdriver
[workflow-badge]:
  https://github.com/deathbeds/jupyterlite-pyodide-lock/actions/workflows/test.yml/badge.svg?branch=main
[workflow]:
  https://github.com/deathbeds/jupyterlite-pyodide-lock/actions/workflows/test.yml?query=branch%3Amain

View the full documentation on [ReadTheDocs][rtfd].

[rtfd]: https://jupyterlite-pyodide-lock.rtfd.org/en/latest

## Install

```bash
pip install jupyterlite-pyodide-lock-webdriver
```

or

```bash
conda install jupyterlite-pyodide-lock-webdriver
```

## Usage

### Configure

> See the `jupyterlite-pyodide-lock` documentation for more information.

```json
{
  "PyodideLockAddon": { "enabled": true, "locker": "WebDriverLocker" },
  "WebDriverLocker": { "browser': 'firefox" }
}
```
