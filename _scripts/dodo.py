"""Project automation for jupyterlite-pyodide-lock."""

import json
import os
import shutil
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from doit.tools import CmdAction

TTaskGenerator = Generator[None, None, dict[str, Any]]


def task_build() -> TTaskGenerator:
    """Build distributions."""
    for ppt, src in P.PY_SRC.items():
        pkg = ppt.parent
        license = pkg / P.LICENSE.name

        if ppt != P.PPT:
            yield dict(
                name=f"license:{pkg.name}",
                actions=[(U.copy, [P.LICENSE, license])],
                file_dep=[P.LICENSE],
                targets=[license],
            )

        if not (E.CI and all(d.exists() for d in B.DIST[ppt])):
            yield dict(
                name=f"flit:{pkg.name}",
                actions=[["pyproject-build", pkg, "--no-isolation"]],
                file_dep=[ppt, license, *src],
                targets=B.DIST[ppt],
            )


def task_dev() -> TTaskGenerator:
    """Prepare for development."""
    if not E.CI:
        yield dict(
            name="env",
            file_dep=[P.ENV_DEV],
            targets=[B.ENV_DEV_HISTORY],
            actions=[
                ["mamba", "env", "update", "--file", P.ENV_DEV, "--prefix", B.ENV_DEV],
            ],
        )

    pip_tasks = []

    for ppt in P.PY_SRC:
        pkg = ppt.parent

        if E.CI:
            wheel = [dist for dist in B.DIST[ppt] if dist.name.endswith(".whl")][0]
            install = [*C.PIP, "install", "--no-deps", wheel]
            file_dep = [wheel]
        else:
            install = [*C.PIP_E, "."]
            file_dep = [ppt, B.ENV_DEV_HISTORY]
        pip_tasks += [f"dev:{pkg.name}"]
        yield dict(name=pkg.name, actions=[U.do(install, cwd=pkg)], file_dep=file_dep)

    yield dict(name="check", actions=[[*C.PIP, "check"]], task_dep=pip_tasks)


def task_fix() -> TTaskGenerator:
    """Fix code style."""
    yield dict(
        name="env:dev",
        file_dep=[P.ENV_TEST, P.ENV_DOCS],
        targets=[P.ENV_DEV],
        actions=[(U.replace_between, [P.ENV_DEV, [P.ENV_TEST, P.ENV_DOCS]])],
    )

    yield dict(
        name="env:docs",
        file_dep=[P.ENV_TEST],
        targets=[P.ENV_DOCS],
        actions=[(U.replace_between, [P.ENV_DOCS, [P.ENV_TEST]])],
    )

    yield dict(
        name="ruff",
        actions=[
            [*C.RUFF, "check", "--fix-only", *P.PY_ALL],
            [*C.RUFF, "format", *P.PY_ALL],
        ],
        file_dep=[*P.PPT_ALL, *P.PY_ALL, B.ENV_DEV_HISTORY],
    )


def task_lint() -> TTaskGenerator:
    """Run style checks."""
    file_dep = [*P.PPT_ALL, *P.PY_ALL]

    if not E.CI:
        file_dep += [B.ENV_DEV_HISTORY]

    yield dict(
        name="ruff",
        actions=[[*C.RUFF, "check"], [*C.RUFF, "format", "--check"]],
        file_dep=file_dep,
    )


def task_test() -> TTaskGenerator:
    """Run unit tests."""
    for ppt, src in P.PY_SRC.items():
        pkg = ppt.parent
        mod = pkg.name.replace("-", "_")
        file_dep = [ppt, *src, *P.PY_TEST[ppt]]

        if not E.CI:
            file_dep += [B.ENV_DEV_HISTORY]

        yield dict(
            name=f"pytest:{pkg.name}",
            actions=[
                U.do([*C.COV_RUN, "--source", mod, "-m", "pytest"], cwd=pkg),
            ],
            file_dep=file_dep,
            task_dep=[f"dev:{pkg.name}"],
            targets=[
                pkg / "build/reports/pytest.html",
                pkg / "build/reports/htmlcov/status.json",
            ],
        )


def task_docs() -> TTaskGenerator:
    """Build documentation."""
    dev_env = [] if E.CI else [B.ENV_DEV_HISTORY]
    yield dict(
        name="app",
        actions=[
            U.do([*C.PYM, "jupyter", "lite", "archive", "--debug"], cwd=P.EXAMPLES),
        ],
        file_dep=[*P.EXAMPLES_ALL, *dev_env],
        targets=[B.DOCS_APP_SHA256SUMS],
    )
    yield dict(
        name="html",
        actions=[[*C.SPHINX, "-b", "html", P.DOCS, B.DOCS]],
        file_dep=[*P.DOCS_ALL, B.DOCS_APP_SHA256SUMS, *dev_env],
        targets=[B.DOCS_BUILDINFO],
    )


class E:
    """Environment."""

    CI = bool(json.loads(os.environ.get("CI", "0").lower()))


class C:
    """Constants."""

    PY_NAME = "jupyterlite_pyodide_lock"
    PY = [sys.executable]
    PYM = [*PY, "-m"]
    PIP = [*PYM, "pip"]
    PIP_E = [
        *PIP,
        "install",
        "-vv",
        "--no-deps",
        "--ignore-installed",
        "--no-build-isolation",
        "-e",
    ]
    SPHINX = ["sphinx-build", "-W", "--color"]
    COV = ["coverage"]
    RUFF = ["ruff"]
    COV_RUN = [*COV, "run", "--branch"]
    COV_REPORT = [*COV, "report"]
    COV_HTML = [*COV, "html"]
    COV_COMBINE = [*COV, "combine"]
    DIST_EXT = [".tar.gz", "-py3-none-any.whl"]
    UTF8 = dict(encoding="utf-8")


class P:
    """Paths."""

    DODO = Path(__file__)
    SCRIPTS = DODO.parent
    PY_SCRIPTS = [*SCRIPTS.glob("*.py")]

    # top-level
    ROOT = SCRIPTS.parent
    PPT = ROOT / "pyproject.toml"
    LICENSE = ROOT / "LICENSE"
    README = ROOT / "README.md"
    ENV_DEV = ROOT / "environment.yml"

    # ci
    CI = ROOT / ".github"
    ENV_TEST = CI / "environment-test.yml"

    # per-package
    PY = ROOT / "py"
    PY_SRC = {ppt: [*(ppt.parent / "src").rglob("*.py")] for ppt in [PPT]}
    PY_TEST = {ppt: [*(ppt.parent / "tests").rglob("*.py")] for ppt in PY_SRC}
    PY_SRC_ALL = sum(PY_SRC.values(), [])
    PY_TEST_ALL = sum(PY_TEST.values(), [])

    # examples
    EXAMPLES = ROOT / "examples"
    EXAMPLES_LITE_DOIT = EXAMPLES / ".jupyterlite.doit.db"
    EXAMPLES_ALL = sorted({*EXAMPLES.rglob("*.*")} - {EXAMPLES_LITE_DOIT})

    # docs
    DOCS = ROOT / "docs"
    PY_DOCS = [*DOCS.rglob("*.py")]
    ENV_DOCS = DOCS / "environment-docs.yml"
    MD_DOCS = [*DOCS.rglob("*.md")]
    DOCS_ALL = [*MD_DOCS, *PY_DOCS, *PY_SRC_ALL]

    # linting
    PY_ALL = [*PY_DOCS, *PY_SCRIPTS, *PY_SRC_ALL, *PY_TEST_ALL]
    PPT_ALL = [PPT, *PY_SRC]


class D:
    """Data."""

    PPT = {ppt: tomllib.loads(ppt.read_text(**C.UTF8)) for ppt in P.PY_SRC}
    VERSION = {ppt: pptd["project"]["version"] for ppt, pptd in PPT.items()}


class B:
    """Build."""

    BUILD = P.ROOT / "build"
    DIST = {
        ppt: [
            ppt.parent
            / f"dist/{ppt.parent.name.replace('-', '_')}-{D.VERSION[ppt]}{ext}"
            for ext in C.DIST_EXT
        ]
        for ppt in P.PY_SRC
    }
    ENV_DEV = P.ROOT / ".venv"
    ENV_DEV_HISTORY = ENV_DEV / "conda-meta/history"
    DOCS = BUILD / "docs"
    DOCS_BUILDINFO = DOCS / ".buildinfo"
    DOCS_STATIC = DOCS / "_static"
    DOCS_APP = BUILD / "docs-app"
    DOCS_APP_SHA256SUMS = DOCS_STATIC / "SHA256SUMS"


class U:
    """Utilities."""

    @staticmethod
    def copy(src: Path, dest: Path) -> bool | None:
        """Copy a folder or file."""
        if not src.exists:
            return False
        if dest.is_dir():
            shutil.rmtree(dest)
        elif dest.exists():
            dest.unlink()
        dest.parent.mkdir(exist_ok=True, parents=True)
        shutil.copytree(src, dest) if src.is_dir() else shutil.copy2(src, dest)
        return True

    @staticmethod
    def do(cmd: list[str], cwd: None | Path = None, **kwargs: Any) -> CmdAction:
        """Wrap a command line with extra options."""
        return CmdAction(cmd, shell=False, cwd=str(cwd) if cwd else None, **kwargs)

    @staticmethod
    def replace_between(dest: Path, srcs: Path) -> None:
        """Replace text between matching markers in files."""
        for src in srcs:
            src_text = src.read_text(**C.UTF8)
            dest_text = dest.read_text(**C.UTF8)
            marker = f"### {src.name} ###"
            src_chunks = src_text.split(marker)
            dest_chunks = dest_text.split(marker)
            dest_text = "".join(
                [dest_chunks[0], marker, src_chunks[1], marker, dest_chunks[2]]
            )
            dest.write_text(dest_text, encoding="utf-8")
