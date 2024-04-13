"""Solve ``pyodide-lock`` with the browser manged as a naive subprocess."""

import asyncio
import shutil
import subprocess
from pathlib import Path

from jupyterlite_core.trait_types import TypedTuple
from traitlets import Bool, Instance, Unicode, default

from .tornado import TornadoLocker

#: browser CLI args, keyed by configurable
BROWSERS = {
    "firefox": {
        "launch": ["firefox"],
        "headless": ["--headless"],
        "private_mode": ["--private-window"],
        "profile": ["--new-instance", "--profile", "{PROFILE_DIR}"],
    },
    "chromium": {
        "launch": ["chromium-browser", "--new-window"],
        # doesn't appear to work
        # "headless": ["--headless"],
        "private_mode": ["--incognito"],
        "profile": ["--user-data-dir={PROFILE_DIR}"],
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

    browser = Unicode("firefox", help="an alias for a pre-configured browser").tag(
        config=True,
    )
    headless = Bool(True, help="run the browser in headless mode").tag(config=True)
    private_mode = Bool(True, help="run the browser in private mode").tag(config=True)
    profile = Unicode(
        None,
        help="run the browser with a copy of the given profile directory",
        allow_none=True,
    ).tag(config=True)
    temp_profile: bool = Bool(
        False,
        help="run the browser with a temporary profile: incompatible with ``profile``",
    ).tag(config=True)

    # runtime
    _temp_profile_path: Path = Instance(Path, allow_none=True)
    _browser_process: subprocess.Popen = Instance(subprocess.Popen, allow_none=True)

    def cleanup(self) -> None:
        proc, path = self._browser_process, self._temp_profile_path
        self.log.debug("[browser] cleanup process: %s", proc)
        self.log.debug("[browser] cleanup path: %s", path)

        if proc and proc.returncode is None:
            self.log.info("[browser] stopping browser")
            proc.kill()
        self._browser_process = None

        if path and path.exists():  # pragma: no cover
            self.log.info("[browser] clearing temporary profile path")
            shutil.rmtree(path, ignore_errors=True)
        self._temp_profile_path = None

        self.log.debug("[browser] cleanup process: %s", proc)
        self.log.debug("[browser] cleanup path: %s", path)

        super().cleanup()

    async def fetch(self):
        args = [*self.browser_argv, self.lock_html_url]
        self.log.debug("[browser] browser args: %s", args)
        self._browser_process = subprocess.Popen(args)

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
    @default("browser_argv")
    def _default_browser_argv(self):
        argv = self.browser_cli_arg(self.browser, "launch")
        argv[0] = self.find_browser_binary(argv[0])

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
