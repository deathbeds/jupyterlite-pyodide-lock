<section class="jlpl-hero">

🕹️ Try the [demo](./demo.md)

</section>


```{include} ../README.md

```

## Why Use This?

- in the browser
  - fetches `pyodide-kernel`, its dependencies, and configured packages in parallel
    while `pyodide` is starting, skipping `micropip.install` and its requests to
    the PyPI API
  - doesn't require `%pip install` for locked packages and their dependencies
    - notebooks and scripts still need to be well-formed, e.g. `import my_package`
    - once shipped, package versions loaded in the browser won't change over time
- during a build
  - doesn't require rebuilding a full custom `pyodide` distribution
    - but will patch an custom deployed `pyodide`
    - all downloaded wheels can be optionally shipped along with the application
  - optionally clamp PyPI packages to a known timestamp to ensure newer packages
    aren't found during a future solve
  - supports multiple sources of custom wheels and dependencies

### Feature Comparison

A number of approaches are available for getting reproducible JupyterLite runtime
python environments, either with `jupyterlite-pyodide-kernel` or other kernels.
Choosing one requires some trades of simplicity, reproducibility, flexibility,
and performance.

> **⏱️ Note**
>
> Each tool is evolving, so the tables below should be verified against the
> different tools when making a decision.

<details>

<summary>A <b>visitor</b> to a JupyterLite site's needs may be the top priority...</summary>

| feature                               | `jupyterlite-pyodide-lock` | `piplite`    | [jupyterlite-xeus] | [micropip]  |
| :------------------------------------ | -------------------------- | ------------ | ------------------ | ----------- |
| needs separate `install` and `import` | no (for locked packages)   | yes (`%pip`) | no                 | no          |
| allows install by PyPI name           | yes                        | yes          | yes                | yes         |
| allows install from URL               | yes                        | yes          | no                 | yes         |
| blocks interaction per package        | run cell                   | run cell     | start kernel       | run cell    |
| caches in the browser                 | per package                | per package  | whole environment  | per package |

</details>

<details>

<summary>An <b>author</b> of a JupyterLite site may have additional needs...</summary>

| feature                                 | `jupyterlite-pyodide-lock`       | `piplite` | [jupyterlite-xeus]  | [pyodide-build]  |
| :-------------------------------------- | -------------------------------- | --------- | ------------------- | ---------------- |
| requires "heavy" build dependencies     | real browser (and/or `selenium`) | no        | minimal, _see repo_ | many, _see repo_ |
| ships local wheels                      | yes                              | yes       | maybe?              | yes              |
| ships noarch PyPI wheels                | yes                              | yes       | yes                 | yes              |
| ships pyodide emscripten wheels         | yes                              | yes       | no                  | yes              |
| ships arbitrary pyodide zip C libs      | no                               | yes       | no                  | yes              |
| locks multiple versions of same package | no                               | yes       | no                  | no               |
| optionally clamp to a timestamp         | yes                              | no        | no                  | no               |

</details>

[jupyterlite-xeus]: https://github.com/jupyterlite/xeus
[emscripten-forge]: https://github.com/emscripten-forge
[pyodide-build]: https://github.com/pyodide/pyodide/tree/main/pyodide-build
[micropip]: https://github.com/pyodide/micropip

## Documentation Contents

```{toctree}
:maxdepth: 2

demo
form/index
configuration/index
lockers/index
changelog
api/index
contributing
```
