"""Project automation for jupyterlite-pyodide-lock."""

import json
import os
import platform
import pprint
import re
import shutil
import subprocess
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
            install = [*C.PIP_INSTALL, wheel]
            file_dep = [wheel]
        else:
            install = [*C.PIP_INSTALL, "-e", "."]
            file_dep = [ppt, B.ENV_DEV_HISTORY]
        pip_tasks += [f"dev:{pkg.name}"]
        yield dict(name=pkg.name, actions=[U.do(install, cwd=pkg)], file_dep=file_dep)

    yield dict(name="check:pip", actions=[[*C.PIP, "check"]], task_dep=pip_tasks)

    yield dict(
        name="check:browsers",
        actions=[["jupyter", "pyodide-lock", "browsers"]],
        task_dep=["dev:check:pip"],
    )


def task_fix() -> TTaskGenerator:
    """Fix code style."""
    core_name = D.PPT[P.PPT]["project"]["name"]
    core_version = D.PPT[P.PPT]["project"]["version"]
    for ppt in P.PPT_CONTRIB:
        yield dict(
            name=f"""version:{D.PPT[ppt]["project"]["name"]}""",
            file_dep=[P.PPT, ppt],
            actions=[
                (
                    U.replace_in_toml,
                    [
                        ppt,
                        ["project", "dependencies"],
                        core_name,
                        f"""{core_name} =={core_version}""",
                    ],
                )
            ],
        )

    for dest, [srcs, src_names] in D.COPY_PASTA.items():
        yield dict(
            name=f"""copy-pasta:{dest.relative_to(P.ROOT)}""",
            file_dep=srcs,
            targets=[dest],
            actions=[(U.replace_between, [dest, srcs, src_names])],
        )

    for ppt, ppt_data in D.PPT.items():
        yield dict(
            name=f"""taplo:{ppt_data["project"]["name"]}""",
            file_dep=[ppt, B.ENV_DEV_HISTORY],
            actions=[(U.normalize_toml, [ppt]), [*C.TAPLO_FORMAT, ppt]],
        )

    for env, stack in P.ENV_STACKS.items():
        yield dict(
            name=f"""env:{env.stem}""",
            file_dep=stack,
            targets=[env],
            actions=[(U.replace_between, [env, stack])],
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
        env = None

        if E.CI:
            env = (
                C.CI_ENV.get(tuple(pkg.name, *E.PY_PLATFORM))
                or C.CI_ENV.get(E.PY_PLATFORM)
                or C.CI_ENV.get(E.PY)
            )
        else:
            file_dep += [B.ENV_DEV_HISTORY]

        yield dict(
            name=f"pytest:{pkg.name}",
            actions=[
                *([(pprint.pprint, [env])] if env else []),
                U.do([*C.COV_RUN, "--source", mod, "-m", "pytest"], cwd=pkg, env=env),
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

    def lite() -> bool:
        args = [
            "jupyter-lite",
            "doit",
            "--debug",
            "--",
            "pre_archive:report:SHA256SUMS",
        ]
        rc = subprocess.call(args, cwd=str(P.EXAMPLES))
        return rc == 0

    yield dict(
        name="app",
        actions=[lite],
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
    PY = ".".join(map(str, sys.version_info[:2]))
    PLATFORM = platform.system().lower()
    PY_PLATFORM = (PY, PLATFORM)


class C:
    """Constants."""

    CORE_NAME = "jupyterlite-pyodide-lock"
    PPT = "pyproject.toml"
    CONFTEST_PY = "tests/conftest.py"
    PY = [sys.executable]
    PYM = [*PY, "-m"]
    PIP = [*PYM, "pip"]
    PIP_INSTALL = [
        *PIP,
        "install",
        "-vv",
        "--no-deps",
        "--ignore-installed",
        "--no-build-isolation",
        "--disable-pip-version-check",
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
    TAPLO = ["taplo"]
    TAPLO_OPTS = [
        "--option=array_auto_collapse=false",
        "--option=array_auto_expand=true",
        "--option=compact_inline_tables=true",
        "--option=column_width=88",
    ]
    TAPLO_FORMAT = [*TAPLO, "fmt", *TAPLO_OPTS]
    CI_ENV = {
        "3.10": dict(JLPL_BROWSER="chrome"),
        # apparently chromedriver doesn't work with chromium on CI
        (CORE_NAME, "3.10", "linux"): dict(JLPL_BROWSER="chromium"),
    }


class P:
    """Paths."""

    DODO = Path(__file__)
    SCRIPTS = DODO.parent
    PY_SCRIPTS = [*SCRIPTS.glob("*.py")]

    # top-level
    ROOT = SCRIPTS.parent
    PPT = ROOT / C.PPT
    CONTRIB = ROOT / "contrib"
    LICENSE = ROOT / "LICENSE"
    README = ROOT / "README.md"
    ENV_DEV = ROOT / "environment.yml"

    # ci
    CI = ROOT / ".github"
    ENV_TEST = CI / "environment-test.yml"
    ENV_TEST_WD = CI / "environment-test-webdriver.yml"
    ENV_TEST_BROWSER = CI / "environment-test-browser.yml"

    # per-package
    PPT_CONTRIB = [*CONTRIB.glob(f"*/{C.PPT}")]
    PY = ROOT / "py"
    PY_SRC = {ppt: [*(ppt.parent / "src").rglob("*.py")] for ppt in [PPT, *PPT_CONTRIB]}
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

    # envs
    ENV_STACKS = {
        ENV_DEV: [ENV_DOCS, ENV_TEST, ENV_TEST_WD, ENV_TEST_BROWSER],
        ENV_DOCS: [ENV_TEST, ENV_TEST_WD],
        ENV_TEST_WD: [ENV_TEST],
    }


class D:
    """Data."""

    PPT = {ppt: tomllib.loads(ppt.read_text(**C.UTF8)) for ppt in P.PY_SRC}
    VERSION = {ppt: pptd["project"]["version"] for ppt, pptd in PPT.items()}
    COPY_PASTA = {
        ppt.parent / C.CONFTEST_PY: [[P.ROOT / C.CONFTEST_PY], ["shared fixtures"]]
        for ppt in P.PPT_CONTRIB
    }


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
    DOCS_APP_SHA256SUMS = DOCS_APP / "SHA256SUMS"


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
        env = None
        _env = kwargs.pop("env", None)
        if _env:
            env = dict(os.environ)
            env.update(_env)
        return CmdAction(
            cmd, shell=False, cwd=str(cwd) if cwd else None, env=env, **kwargs
        )

    @staticmethod
    def replace_between(
        dest: Path, srcs: Path, src_names: list[str] | None = None
    ) -> bool:
        """Replace text between matching markers in files."""
        src_names = src_names or [src.name for src in srcs]
        for src, src_name in zip(srcs, src_names, strict=False):
            marker = f"### {src_name} ###"
            src_text = src.read_text(**C.UTF8)
            dest_text = dest.read_text(**C.UTF8)
            if marker not in dest_text:
                print(f"'{marker}' not in {dest}")
                return False
            if marker not in src_text:
                print(f"'{marker}' not in {src}")
                return False
            src_chunks = src_text.split(marker)
            dest_chunks = dest_text.split(marker)
            dest_text = "".join(
                [dest_chunks[0], marker, src_chunks[1], marker, dest_chunks[2]]
            )
            dest.write_text(dest_text, encoding="utf-8")
        return True

    @staticmethod
    def replace_in_toml(
        toml_path: Path, attr_path: list[str], pattern: str, new_value: str
    ) -> bool:
        """Replace a TOML list item by pattern."""
        import tomli_w

        prefix = f"""{"/".join(attr_path)}[{new_value}]"""
        rel = toml_path.relative_to(P.ROOT)

        root = tomllib.loads(toml_path.read_text(**C.UTF8))
        current = root
        for attr in attr_path:
            current = current[attr]

        for i, old_value in enumerate(current):
            if re.findall(pattern, old_value):
                if old_value != new_value:
                    print(f"   ... {prefix} changed (was '{old_value}') {rel}")
                    current[i] = new_value
                    toml_path.write_text(tomli_w.dumps(root))
                    return True

                print(f"""   ... {prefix} already in {rel}""")
                return True

        print(f"   !!!'{pattern}' not in {rel}")
        return False

    @staticmethod
    def normalize_toml(toml_path: Path) -> bool:
        """Round trip a TOML file."""
        import tomli_w

        rel = toml_path.relative_to(P.ROOT)
        old_text = toml_path.read_text(**C.UTF8).strip()
        new_text = tomli_w.dumps(tomllib.loads(old_text)).strip()
        if old_text == new_text:
            print(f"   ... ok TOML {rel}")
            return True

        print(f"   ... writing TOML {rel}")
        toml_path.write_text(new_text + "\n")
        return True
