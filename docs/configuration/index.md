# Configuration

Configuring JupyterLite to use `pyodide-lock` requires adding some data to
`jupyter_lite_config.json`.

> **Note**
>
> Starting with the [core](./core.ipynb)'s
> `PyodideLockAddon` basic `BrowserLocker` is recommended.
> The [`WebDriverLocker`](./webdriver.ipynb) is more appropriate
> for projects that already use [selenium](https://selenium-python.readthedocs.io/)
> for browser automation.

## Locker-specific Configuration

```{toctree}
:maxdepth: 4

core
webdriver
```
