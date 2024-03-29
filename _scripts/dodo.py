import shutil
import typing as T
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from doit.tools import CmdAction


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
    yield dict(
        name="env",
        file_dep=[P.ENV_DEV],
        targets=[B.ENV_DEV_HISTORY],
        actions=[
            ["mamba", "env", "update", "--file", P.ENV_DEV, "--prefix", B.ENV_DEV]
        ],
    )

    for ppt in P.PY_SRC:
        pkg = ppt.parent
        yield dict(
            name=pkg.name,
            actions=[
                U.do(
                    [*C.PIP, "install", "-e", ".", "--no-deps", "--ignore-installed"],
                    cwd=pkg,
                )
            ],
            file_dep=[ppt],
        )


def task_fix():
    yield dict(
        name="ruff",
        actions=[
            [*C.RUFF, "format", *P.PY_ALL],
            [*C.RUFF, "check", "--fix-only", *P.PY_ALL],
        ],
        file_dep=[*P.PPT_ALL, *P.PY_ALL, B.ENV_DEV_HISTORY],
    )


def task_lint():
    yield dict(
        name="ruff",
        actions=[
            [*C.RUFF, "format", "--check"],
            [*C.RUFF, "check"],
        ],
        file_dep=[*P.PPT_ALL, *P.PY_ALL, B.ENV_DEV_HISTORY],
    )


def task_test():
    for ppt, src in P.PY_SRC.items():
        pkg = ppt.parent
        mod = pkg.name.replace("-", "_")

        yield dict(
            name=f"pytest:{pkg.name}",
            actions=[
                U.do([*C.COV_RUN, "--source", mod, "-m", "pytest"], cwd=pkg),
            ],
            file_dep=[ppt, *src, *P.PY_TEST[ppt], B.ENV_DEV_HISTORY],
            task_dep=[f"dev:{pkg.name}"],
            targets=[
                pkg / "build/reports/pytest.html",
                pkg / "build/reports/htmlcov/status.json",
            ],
        )


class C:
    PY_NAME = "jupyterlite_pyodide_lock"
    PY = ["python"]
    PYM = [*PY, "-m"]
    PIP = [*PYM, "pip"]
    COV = ["coverage"]
    RUFF = ["ruff"]
    COV_RUN = [*COV, "run", "--branch"]
    COV_REPORT = [*COV, "report"]
    COV_HTML = [*COV, "html"]
    COV_COMBINE = [*COV, "combine"]
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
    ENV_DEV = ROOT / "environment.yml"

    # per-package
    PY = ROOT / "py"
    PY_SRC = {
        ppt: [*(ppt.parent / "src").rglob("*.py")]
        for ppt in PY.glob("*/pyproject.toml")
    }
    PY_TEST = {ppt: [*(ppt.parent / "tests").rglob("*.py")] for ppt in PY_SRC}
    PY_SRC_ALL = sum(PY_SRC.values(), [])
    PY_TEST_ALL = sum(PY_TEST.values(), [])

    DOCS = ROOT / "docs"
    PY_DOCS = [*DOCS.rglob("*.py")]

    PY_ALL = [*PY_DOCS, *PY_SCRIPTS, *PY_SRC_ALL, *PY_TEST_ALL]
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
    ENV_DEV = P.ROOT / ".venv"
    ENV_DEV_HISTORY = ENV_DEV / "conda-meta/history"


class U:
    @staticmethod
    def copy(src: Path, dest: Path) -> T.Optional[bool]:
        if dest.is_dir():
            shutil.rmtree(dest)
        elif dest.exists():
            dest.unlink()
        dest.parent.mkdir(exist_ok=True, parents=True)
        shutil.copytree(src, dest) if src.is_dir() else shutil.copy2(src, dest)

    @staticmethod
    def do(cmd: T.List[str], cwd=None):
        return CmdAction(cmd, shell=False, cwd=str(cwd) if cwd else None)
