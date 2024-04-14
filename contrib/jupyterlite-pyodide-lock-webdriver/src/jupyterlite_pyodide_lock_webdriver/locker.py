"""The locker implementation."""

import asyncio
import os
import shutil
from typing import TYPE_CHECKING

from jupyterlite_pyodide_lock.constants import (
    CHROME,
    CHROME_BINARY,
    CHROMIUM,
    CHROMIUM_BINARY,
    ENV_VAR_BROWSER,
    FIREFOX,
    FIREFOX_BINARY,
)
from jupyterlite_pyodide_lock.lockers.tornado import TornadoLocker
from selenium.webdriver import (
    Chrome,
    ChromeOptions,
    ChromeService,
    Firefox,
    FirefoxOptions,
    FirefoxService,
)
from traitlets import Bool, Dict, Instance, List, Unicode, default

if TYPE_CHECKING:  # pragma: no cover
    TAnyService = FirefoxService | ChromeService
    TAnyOptions = FirefoxOptions | ChromeOptions
    TAnyWebDriver = Firefox | Chrome

BROWSER_CHROMIUM_BASE = {
    "webdriver_class": Chrome,
    "options_class": ChromeOptions,
    "service_class": ChromeService,
    "log_output": "chromedriver.log",
    "webdriver_path": "chromedriver",
}

BROWSERS = {
    FIREFOX: {
        "webdriver_class": Firefox,
        "options_class": FirefoxOptions,
        "service_class": FirefoxService,
        "browser_binary": FIREFOX_BINARY,
        "webdriver_path": "geckodriver",
        "log_output": "geckodriver.log",
    },
    CHROMIUM: {"browser_binary": CHROMIUM_BINARY, **BROWSER_CHROMIUM_BASE},
    CHROME: {"browser_binary": CHROME_BINARY, **BROWSER_CHROMIUM_BASE},
}


class WebDriverLocker(TornadoLocker):
    browser = Unicode(help="an alias for a pre-configured browser").tag(
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
    webdriver_log_output = Unicode(help="a path to the webdriver log").tag(config=True)
    webdriver_env = Dict(Unicode(), help="custom enviroment variable overrides").tag(
        config=True
    )

    # runtime
    _webdriver_options: "TAnyOptions" = Instance(
        "selenium.webdriver.common.options.ArgOptions", allow_none=True
    )
    _webdriver_service: "TAnyService" = Instance(
        "selenium.webdriver.common.service.Service", allow_none=True
    )
    _webdriver: "TAnyWebDriver" = Instance(
        "selenium.webdriver.remote.webdriver.WebDriver", allow_none=True
    )
    _webdriver_task = Instance(
        asyncio.Task,
        help="a handle for the webdriver task to avoid gc",
        allow_none=True,
    )

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
            self.cleanup()

    def cleanup(self) -> None:
        if self._webdriver:  # pragma: no cover
            for method in [self._webdriver.close, self._webdriver.quit]:
                try:
                    method()
                except Exception as err:
                    self.log.debug("[webdriver] cleanup error: %s", err)
            self._webdriver = None
        return super().cleanup()

    async def _webdriver_get_async(self):
        await asyncio.get_event_loop().run_in_executor(None, self._webdriver_get)

    def _webdriver_get(self):
        try:
            self._webdriver.get(self.lock_html_url)
        except Exception as err:  # pragma: no cover
            self.log.warning("[webdriver] halting due to error: %s", err)
            self._solve_halted = True

    # defaults
    @default("browser")
    def _default_browser(self):
        return os.environ.get(ENV_VAR_BROWSER, FIREFOX)

    @default("_webdriver")
    def _default_webdriver(self) -> "TAnyWebDriver":  # pragma: no cover
        WebDriverClass = BROWSERS[self.browser]["webdriver_class"]
        options = self._webdriver_options
        service = self._webdriver_service

        return WebDriverClass(options=options, service=service)

    @default("browser_path")
    def _default_browser_path(self):  # pragma: no cover
        return self.find_browser_binary(BROWSERS[self.browser]["browser_binary"])

    @default("webdriver_path")
    def _default_webdriver_path(self):  # pragma: no cover
        bin = BROWSERS[self.browser]["webdriver_path"]
        if bin:
            return shutil.which(bin) or shutil.which(f"{bin}.exe")
        return None

    @default("webdriver_log_output")
    def _default_webdriver_log_output(self):  # pragma: no cover
        return BROWSERS[self.browser]["log_output"]

    @default("webdriver_env")
    def _default_webdriver_env(self):  # pragma: no cover
        if self.browser == FIREFOX and self.headless:
            return {"MOZ_HEADLESS": "1"}
        return {}

    @default("_webdriver_options")
    def _default_webdriver_options(self) -> "TAnyOptions":
        browser = self.browser
        OptionsClass: "type[TAnyOptions]" = BROWSERS[browser]["options_class"]
        options = OptionsClass()

        if self.browser_path:  # pragma: no cover
            self.log.debug("[webdriver] %s path %s", browser, self.browser_path)
            options.binary_location = self.browser_path

        return options

    @default("_webdriver_service")
    def _default_webdriver_service(self) -> "TAnyService":
        browser = self.browser
        ServiceClass: "type[TAnyService]" = BROWSERS[browser]["service_class"]
        service_kwargs = dict(
            executable_path=self.webdriver_path,
            service_args=self.webdriver_service_args,
            env=self.webdriver_env,
        )

        if self.webdriver_log_output:  # pragma: no cover
            path = self.parent.manager.lite_dir / self.webdriver_log_output
            path.parent.mkdir(parents=True, exist_ok=True)
            service_kwargs.update(log_output=str(path.resolve()))

        self.log.debug("[webdriver] %s service options: %s", browser, service_kwargs)

        _env = dict(os.environ)
        _env.update(service_kwargs["env"])
        service_kwargs["env"] = _env

        return ServiceClass(**service_kwargs)
