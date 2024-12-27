"""Solve ``pyodide-lock`` with the browser manged as a naive subprocess."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path

import psutil
from jupyterlite_core.trait_types import TypedTuple
from traitlets import Bool, Instance, Unicode, default

from jupyterlite_pyodide_lock.constants import (
    BROWSER_BIN,
    CHROME,
    CHROMIUM,
    ENV_VAR_BROWSER,
    FIREFOX,
)
from jupyterlite_pyodide_lock.utils import find_browser_binary

from .tornado import TornadoLocker

#: chromium base args
BROWSER_CHROMIUM_BASE = {
    "private_mode": ["--incognito"],
    "profile": ["--user-data-dir={PROFILE_DIR}"],
    "headless": ["--headless=new"],
}


#: browser CLI args, keyed by configurable
BROWSERS = {
    FIREFOX: {
        "launch": [BROWSER_BIN[FIREFOX]],
        "headless": ["--headless"],
        "private_mode": ["--private-window"],
        "profile": ["--new-instance", "--profile", "{PROFILE_DIR}"],
    },
    CHROMIUM: {
        "launch": [BROWSER_BIN[CHROMIUM], "--new-window"],
        **BROWSER_CHROMIUM_BASE,
    },
    CHROME: {
        "launch": [BROWSER_BIN[CHROME], "--new-window"],
        **BROWSER_CHROMIUM_BASE,
    },
}


class BrowserLocker(TornadoLocker):
    """Use a web server and browser subprocess to build a ``pyodide-lock.json``.

    See :class:`..tornado.TornadoLocker` for server details.
    """

    # configurable
    browser_argv = TypedTuple(
        Unicode(),
        help=(
            "the non-URL arguments for the browser process: if configured, ignore "
            "'browser', 'headless', 'private_mode', 'temp_profile', and 'profile'"
        ),
    ).tag(config=True)
    extra_browser_argv = TypedTuple(
        Unicode(), help="additional non-URL arguments for the browser process."
    ).tag(config=True)
    browser = Unicode(help="an alias for a pre-configured browser").tag(
        config=True,
    )
    headless = Bool(default_value=True, help="run the browser in headless mode").tag(
        config=True
    )
    private_mode = Bool(default_value=True, help="run the browser in private mode").tag(
        config=True
    )
    profile = Unicode(
        None,
        help="run the browser with a copy of the given profile directory",
        allow_none=True,
    ).tag(config=True)
    temp_profile: bool = Bool(
        default_value=True,
        help="run the browser with a temporary profile: clobbered by ``profile``",
    ).tag(config=True)

    # runtime
    _temp_profile_path: Path | None = Instance(Path, allow_none=True)
    _browser_process: psutil.Popen | None = Instance(psutil.Popen, allow_none=True)

    def cleanup(self) -> None:
        """Clean up the browser process and profile directory."""
        proc, path = self._browser_process, self._temp_profile_path
        self.log.debug("[browser] cleanup process: %s", proc)
        self.log.debug("[browser] cleanup path: %s", path)

        procs: list[psutil.Process] = (
            [] if proc is None else [*proc.children(recursive=True), proc]
        )
        running = [p for p in procs if p.is_running()]

        for p in running:
            self.log.info("[browser] stopping browser process %s", p)
            try:
                p.kill()
            except psutil.NoSuchProcess:  # pragma: no cover
                self.log.debug("[browser] was already stopped %s", p)

        psutil.wait_procs(r for r in running if r.is_running())

        self._browser_process = None

        if path and path.exists():  # pragma: no cover
            self.log.info("[browser] clearing temporary profile path")
            shutil.rmtree(path, ignore_errors=True)

        self._temp_profile_path = None

        self.log.debug("[browser] cleanup process: %s", proc)
        self.log.debug("[browser] cleanup path: %s", path)

        super().cleanup()

    async def fetch(self) -> None:
        """Open the browser to the lock page, and wait for it to finish."""
        args = [*self.browser_argv, *self.extra_browser_argv, self.lock_html_url]
        self.log.debug("[browser] browser args: %s", args)
        self._browser_process = psutil.Popen(args)

        try:
            while True:
                if self._solve_halted:
                    self.log.info("Lock is finished")
                    break

                if self._browser_process.returncode is not None:  # pragma: no cover
                    self.log.info(
                        "Browser is closed with code: %s",
                        self._browser_process.returncode,
                    )
                    break

                await asyncio.sleep(1)
        finally:
            self.cleanup()

    # trait defaults
    @default("browser")
    def _default_browser(self) -> str:
        return os.environ.get(ENV_VAR_BROWSER, "").strip() or FIREFOX

    @default("browser_argv")
    def _default_browser_argv(self) -> list[str]:
        argv = self.browser_cli_arg(self.browser, "launch")
        argv[0] = find_browser_binary(argv[0], self.log)

        if True:  # pragma: no cover
            if self.headless:
                argv += self.browser_cli_arg(self.browser, "headless")

            if self.profile and self.temp_profile:
                self.log.warning(
                    "[browser] 'profile' and 'temp_profile' both specified: using %s",
                    self.profile,
                )

            if self.profile:
                self.ensure_temp_profile(
                    (self.parent.manager.lite_dir / self.profile).resolve(),
                )
            elif self.temp_profile:
                self.ensure_temp_profile()

            if self._temp_profile_path:
                argv += [
                    arg.replace("{PROFILE_DIR}", str(self._temp_profile_path))
                    for arg in self.browser_cli_arg(self.browser, "profile")
                ]

            if self.private_mode:
                argv += self.browser_cli_arg(self.browser, "private_mode")

        self.log.debug("[browser] non-URL browser argv %s", argv)

        return argv

    # utilities
    def ensure_temp_profile(
        self,
        baseline: Path | None = None,
    ) -> str:  # pragma: no cover
        """Create a temporary browser profile."""
        if self._temp_profile_path is None:
            path = self.cache_dir / ".browser" / self.browser
            if baseline and baseline.is_dir():
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(baseline, path)
            else:
                path.mkdir(parents=True, exist_ok=True)
            self._temp_profile_path = path
        return str(self._temp_profile_path)

    def browser_cli_arg(self, browser: str, trait_name: str) -> list[str]:
        """Find the CLI args for specific browser by trait name."""
        if trait_name not in BROWSERS[browser]:  # pragma: no cover
            self.log.warning(
                "[browser] %s.%s does not work with %s",
                self.__class__.__name__,
                trait_name,
                browser,
            )
            return []
        return BROWSERS[browser][trait_name]
