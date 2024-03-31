# Contributing

## Environment

- start with [mambaforge](https://github.com/conda-forge/miniforge)
- set up the dev environment

```bash
mamba env update --file environment.yml --prefix .venv
```

- activate the environment

```bash
source activate .venv
# or on windows
activate .venv
```


## doit

See the available `doit` tasks:

```bash
doit list
```
