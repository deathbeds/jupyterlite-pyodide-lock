"""The locker implementation."""

import asyncio
import os
import shutil
from typing import TYPE_CHECKING

from jupyterlite_pyodide_lock.lockers.tornado import TornadoLocker
from traitlets import Bool, Dict, Instance, List, Unicode, default

if TYPE_CHECKING:  # pragma: no cover
    from selenium.webdriver.remote.webdriver import WebDriver


class WebDriverLocker(TornadoLocker):
    browser = Unicode("firefox", help="an alias for a pre-configured browser").tag(
        config=True,
    )
    headless = Bool(True, help="run the browser in headless mode").tag(config=True)
    browser_path = Unicode(
        help="an absolute path to a browser, if not well-known or on PATH",
    ).tag(config=True)
    webdriver_path = Unicode(
        help="an absolute path to a driver, if not well-known or on PATH",
    ).tag(config=True)
    webdriver_service_args = List(
        Unicode(), help="arguments for the webdriver binary"
    ).tag(config=True)
    webdriver_log_path = Unicode(help="a path to the webdriver log").tag(config=True)
    webdriver_env_vars = Dict(Unicode(), help="a path to the webdriver log").tag(
        config=True
    )

    # runtime
    _webdriver: "WebDriver" = Instance(
        "selenium.webdriver.remote.webdriver.WebDriver", allow_none=True
    )
    _webdriver_task = Instance(asyncio.Task)

    async def fetch(self) -> None:
        webdriver = self._webdriver

        self.log.info("[webdriver] %s", webdriver)

        self._webdriver_task = asyncio.create_task(self._webdriver_get_async())

        try:
            while True:
                if self._solve_halted:
                    self.log.info("Lock is finished")
                    break

                await asyncio.sleep(1)
        finally:
            await self.cleanup()

    async def cleanup(self) -> None:
        if self._webdriver:  # pragma: no cover
            for method in [self._webdriver.close, self._webdriver.quit]:
                try:
                    method()
                except Exception as err:
                    self.log.debug("[webdriver] cleanup error: %s", err)
            self._webdriver = None
        return await super().cleanup()

    async def _webdriver_get_async(self):
        await asyncio.get_event_loop().run_in_executor(None, self._webdriver_get)

    def _webdriver_get(self):
        try:
            self._webdriver.get(self.lock_html_url)
        except Exception as err:  # pragma: no cover
            self.log.warning("[webdriver] halting due to error: %s", err)
            self._solve_halted = True

    # defaults
    @default("_webdriver")
    def _default_webdriver(self):  # pragma: no cover
        if self.browser == "firefox":
            return self._make_webdriver_firefox()
        raise NotImplementedError(f"{self.browser} is not yet supported")

    @default("browser_path")
    def _default_browser_path(self):  # pragma: no cover
        if self.browser == "firefox":
            return self.find_browser_binary("firefox")
        raise NotImplementedError(f"{self.browser} is not yet supported")

    @default("webdriver_path")
    def _default_webdriver_path(self):  # pragma: no cover
        if self.browser == "firefox":
            return shutil.which("geckodriver")
        raise NotImplementedError(f"{self.browser} is not yet supported")

    @default("webdriver_log_path")
    def _default_webdriver_log_path(self):  # pragma: no cover
        if self.browser == "firefox":
            return str(self.parent.manager.lite_dir / "geckodriver.log")
        raise NotImplementedError(f"{self.browser} is not yet supported")

    @default("webdriver_env_vars")
    def _default_webdriver_env_vars(self):  # pragma: no cover
        if self.browser == "firefox" and self.headless:
            return {"MOZ_HEADLESS": "1"}
        return {}

    # utilities
    def _make_webdriver_firefox(self):
        """Build a firefox driver"""
        from selenium.webdriver import Firefox, FirefoxOptions, FirefoxService

        options = FirefoxOptions()
        if self.headless:  # pragma: no cover
            options.headless = self.headless

        if self.browser_path:  # pragma: no cover
            self.log.debug("[webdriver] firefox path %s", self.browser_path)

            options.binary_location = self.browser_path

        service_kwargs = dict(
            executable_path=self.webdriver_path,
            service_args=self.webdriver_service_args,
            env=self.webdriver_env_vars,
        )

        if self.webdriver_log_path:  # pragma: no cover
            path = self.parent.manager.lite_dir / self.webdriver_log_path
            path.parent.mkdir(parents=True, exist_ok=True)
            service_kwargs.update(log_output=str(path.resolve()))

        self.log.debug("[webdriver] geckodriver options: %s", service_kwargs)

        _env = dict(os.environ)
        _env.update(service_kwargs["env"])
        service_kwargs["env"] = _env

        service = FirefoxService(**service_kwargs)

        self.log.debug("[webdriver] firefox options %s", options.__dict__)

        return Firefox(options=options, service=service)
