from pathlib import Path
import shutil
import typing as T

try:
    import tomllib
except ImportError:
    import tomli as tomllib


def task_build():
    for ppt, src in P.PY_SRC.items():
        pkg = ppt.parent
        license = pkg / P.LICENSE.name

        yield dict(
            name=f"license:{pkg.name}",
            actions=[(U.copy, [P.LICENSE, license])],
            file_dep=[P.LICENSE],
            targets=[license],
        )

        yield dict(
            name=f"flit:{pkg.name}",
            actions=[["pyproject-build", pkg, "--no-isolation"]],
            file_dep=[ppt, license, *src],
            targets=B.DIST[ppt],
        )


def task_dev():
    for ppt in P.PY_SRC:
        pkg = ppt.parent
        yield dict(
            name=pkg.name,
            actions=[[*C.PIP, "install", "-e", pkg, "--no-deps", "--ignore-installed"]],
            file_dep=[ppt],
        )


def task_fix():
    yield dict(
        name="ruff",
        actions=[
            [*C.RUFF, "format", *P.PY_ALL],
            [*C.RUFF, "check", "--fix-only", *P.PY_ALL],
        ],
        file_dep=[*P.PPT_ALL, *P.PY_ALL],
    )


def task_lint():
    yield dict(
        name="ruff",
        actions=[
            [*C.RUFF, "format", "--check"],
            [*C.RUFF, "check"],
        ],
        file_dep=[*P.PPT_ALL, *P.PY_ALL],
    )


class C:
    PY_NAME = "jupyterlite_pyodide_lock"
    PY = ["python"]
    PYM = [*PY, "-m"]
    PIP = [*PYM, "pip"]
    COV = ["coverage"]
    RUFF = ["ruff"]
    COV_RUN_M = [COV, "run"]
    DIST_EXT = [".tar.gz", "-py3-none-any.whl"]


class P:
    DODO = Path(__file__)
    SCRIPTS = DODO.parent
    PY_SCRIPTS = [*SCRIPTS.glob("*.py")]

    # top-level
    ROOT = SCRIPTS.parent
    PPT = ROOT / "pyproject.toml"
    LICENSE = ROOT / "LICENSE"
    README = ROOT / "README.md"

    # per-package
    PY = ROOT / "py"
    PY_SRC = {
        ppt: [*ppt.parent.glob("src/*/**/*.py")] for ppt in PY.glob("*/pyproject.toml")
    }
    PY_SRC_ALL = sum(PY_SRC.values(), [])

    DOCS = ROOT / "docs"
    PY_DOCS = [*DOCS.rglob("*.py")]

    PY_ALL = [*PY_DOCS, *PY_SCRIPTS, *PY_SRC_ALL]
    PPT_ALL = [PPT, *PY_SRC]


class D:
    PPT = {ppt: tomllib.load(ppt.open("rb")) for ppt in P.PY_SRC}
    VERSION = {ppt: pptd["project"]["version"] for ppt, pptd in PPT.items()}


class B:
    BUILD = P.ROOT / "build"
    DIST = {
        ppt: [
            ppt.parent
            / f"dist/{ppt.parent.name.replace("-", "_")}-{D.VERSION[ppt]}{ext}"
            for ext in C.DIST_EXT
        ]
        for ppt in P.PY_SRC
    }


class U:
    @staticmethod
    def copy(src: Path, dest: Path) -> T.Optional[bool]:
        if dest.is_dir():
            shutil.rmtree(dest)
        elif dest.exists():
            dest.unlink()

        dest.parent.mkdir(exist_ok=True, parents=True)

        if src.is_dir():
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)
