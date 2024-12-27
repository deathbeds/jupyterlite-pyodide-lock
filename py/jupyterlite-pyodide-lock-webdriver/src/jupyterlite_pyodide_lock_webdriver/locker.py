"""Locker implementation ``jupyterlite-pyodide-lock-webdriver``."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

from __future__ import annotations

import asyncio
import os
import shutil
from typing import Any, cast

from jupyterlite_core.trait_types import TypedTuple
from traitlets import Bool, Dict, Instance, List, Unicode, default

from jupyterlite_pyodide_lock.constants import ENV_VAR_BROWSER, FIREFOX
from jupyterlite_pyodide_lock.lockers.browser import BROWSERS as CORE_BROWSERS
from jupyterlite_pyodide_lock.lockers.tornado import TornadoLocker
from jupyterlite_pyodide_lock.utils import find_browser_binary

from .browsers import BROWSERS, ArgOptions, Service, WebDriver


class WebDriverLocker(TornadoLocker):
    """A locker that uses the WebDriver standard to control a browser."""

    browser: str = Unicode(help="an alias for a pre-configured browser").tag(
        config=True,
    )  # type: ignore[assignment]
    webdriver_option_arguments: list[str] = TypedTuple(
        Unicode(), help="options to add to the webdriver browser"
    ).tag(config=True)
    headless: bool = Bool(
        default_value=True, help="run the browser in headless mode"
    ).tag(config=True)  # type: ignore[assignment]
    browser_path: str = Unicode(
        help="an absolute path to a browser, if not well-known or on PATH",
    ).tag(config=True)  # type: ignore[assignment]
    webdriver_path: str = Unicode(
        help="an absolute path to a driver, if not well-known or on PATH",
    ).tag(config=True)  # type: ignore[assignment]
    webdriver_service_args: list[str] = List(
        Unicode(), help="arguments for the webdriver binary"
    ).tag(config=True)  # type: ignore[assignment]
    webdriver_log_output: str = Unicode(help="a path to the webdriver log").tag(
        config=True
    )  # type: ignore[assignment]
    webdriver_env: dict[str, str] = Dict(
        Unicode(), help="custom environment variable overrides"
    ).tag(config=True)  # type: ignore[assignment]

    # runtime
    _webdriver_options: ArgOptions | None = Instance(
        "selenium.webdriver.common.options.ArgOptions", allow_none=True
    )  # type: ignore[assignment]
    _webdriver_service: Service | None = Instance(
        "selenium.webdriver.common.service.Service", allow_none=True
    )  # type: ignore[assignment]
    _webdriver: WebDriver | None = Instance(
        "selenium.webdriver.remote.webdriver.WebDriver", allow_none=True
    )  # type: ignore[assignment]
    _webdriver_task: asyncio.Task[Any] = Instance(
        asyncio.Task,
        help="a handle for the webdriver task to avoid gc",
        allow_none=True,
    )  # type: ignore[assignment]

    async def fetch(self) -> None:
        """Create the WebDriver, open the lock page, and wait for it to lock."""
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
        """Clean up the WebDriver."""
        if self._webdriver:  # pragma: no cover
            for method in [self._webdriver.close, self._webdriver.quit]:
                try:
                    method()
                except Exception as err:
                    self.log.debug("[webdriver] cleanup error: %s", err)
            self._webdriver = None
        super().cleanup()

    async def _webdriver_get_async(self) -> None:
        """Wrap the blocking webdriver behavior for making a ``Task``."""
        await asyncio.get_event_loop().run_in_executor(None, self._webdriver_get)

    def _webdriver_get(self) -> None:
        """Actually open the page (or fail)."""
        if self._webdriver is None:  # pragma: no cover
            self.log.warning("[webdriver] halting because no webdriver")
            self._solve_halted = True
            return

        try:
            self._webdriver.get(self.lock_html_url)
        except Exception as err:  # pragma: no cover
            self.log.warning("[webdriver] halting due to error: %s", err)
            self._solve_halted = True

    # defaults
    @default("browser")
    def _default_browser(self) -> str:
        return os.environ.get(ENV_VAR_BROWSER, "").strip() or FIREFOX

    @default("_webdriver")
    def _default_webdriver(self) -> WebDriver:  # pragma: no cover
        webdriver_class: type[WebDriver] = BROWSERS[self.browser]["webdriver_class"]
        options = self._webdriver_options
        service = self._webdriver_service
        driver_kwargs: Any = {"options": options, "service": service}
        return webdriver_class(**driver_kwargs)

    @default("browser_path")
    def _default_browser_path(self) -> str:  # pragma: no cover
        return find_browser_binary(BROWSERS[self.browser]["browser_binary"], self.log)

    @default("webdriver_path")
    def _default_webdriver_path(self) -> str | None:  # pragma: no cover
        exe = BROWSERS[self.browser].get("webdriver_path")
        if exe:
            return shutil.which(exe) or shutil.which(f"{exe}.exe")
        return None

    @default("webdriver_log_output")
    def _default_webdriver_log_output(self) -> str:  # pragma: no cover
        return str(BROWSERS[self.browser]["log_output"])

    @default("webdriver_env")
    def _default_webdriver_env(self) -> dict[str, str]:  # pragma: no cover
        if self.browser == FIREFOX and self.headless:
            return dict(MOZ_HEADLESS="1")
        return {}

    @default("_webdriver_options")
    def _default_webdriver_options(self) -> ArgOptions:
        browser = self.browser
        options_klass: type[ArgOptions] = BROWSERS[browser]["options_class"]
        options: ArgOptions = options_klass()

        if self.browser_path:  # pragma: no cover
            self.log.debug("[webdriver] %s path %s", browser, self.browser_path)
            options.binary_location = self.browser_path  # type: ignore[attr-defined]

        opts = [*self.webdriver_option_arguments]

        if self.headless:  # pragma: no cover
            opts += CORE_BROWSERS[browser]["headless"]

        for opt in opts:
            self.log.debug("[webdriver] adding %s option %s", browser, opt)
            options.add_argument(opt)

        self.log.debug("[webdriver] %s webdriver options: %s", browser, options)

        return options

    @default("_webdriver_service")
    def _default_webdriver_service(self) -> Service:
        browser = self.browser
        service_class = BROWSERS[browser]["service_class"]
        service_kwargs = dict(
            executable_path=self.webdriver_path,
            service_args=(
                self.webdriver_service_args or BROWSERS[browser].get("service_args", [])
            ),
            env=self.webdriver_env,
        )

        if self.webdriver_log_output:  # pragma: no cover
            path = self.parent.manager.lite_dir / self.webdriver_log_output
            path.parent.mkdir(parents=True, exist_ok=True)
            service_kwargs.update(log_output=str(path.resolve()))

        self.log.debug("[webdriver] %s service options: %s", browser, service_kwargs)

        env_ = dict(os.environ)
        env_.update(dict(cast("Any", service_kwargs["env"])))
        service_kwargs["env"] = env_

        return service_class(**cast("Any", service_kwargs))
