# jupyterlite-pyodide-lock-webdriver

> A `jupyterlite-pyodide-lock` lock strategy using the [WebDriver] standard.

[webdriver]: https://www.w3.org/TR/webdriver

## Install

> This package is not yet released. See `CONTRIBUTING.md` for development.
>
> ```bash
> pip install jupyterlite-pyodide-lock-webdriver
> ```

## Usage

### Configure

> See the `jupyterlite-pyodide-lock` documentation for more information.

```yaml
# examples/jupyter_lite_config.json
{
  'PyodideLockAddon': { 'enabled': true, 'locker': 'WebDriverLocker' },
  'WebDriverLocker': { 'browser': 'firefox' },
}
```
