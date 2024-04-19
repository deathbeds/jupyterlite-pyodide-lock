# Configuration

Configuring JupyterLite to use `pyodide-lock` requires adding some data to 
`jupyter_lite_config.json`. 

> **Note**
> 
> Starting with the [core](./core.ipynb)'s 
> `PyodideLockAddon` and the naive `BrowserLocker` is recommended, 
> with [webdriver](./webdriver.ipynb)'s `WebDriverLocker` being more appropriate 
> for projects that already use [selenium](https://selenium-python.readthedocs.io/)
> for browser automation.

## Package-specific Configuration

```{toctree}
:maxdepth: 3

core
webdriver
```
