"""Browser details for ``jupyterlite-pyodide-lock-webdriver``."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

from typing import TypedDict

from selenium.webdriver import (
    Chrome,
    ChromeOptions,
    ChromeService,
    Firefox,
    FirefoxOptions,
    FirefoxService,
)
from selenium.webdriver.common.options import ArgOptions
from selenium.webdriver.common.service import Service
from selenium.webdriver.remote.webdriver import WebDriver

from jupyterlite_pyodide_lock.constants import (
    BROWSER_BIN,
    CHROME,
    CHROMIUM,
    FIREFOX,
)

__all__ = ["ArgOptions", "Browser", "Service", "WebDriver"]


class Browser(TypedDict, total=False):
    """Common values for selenium configuration."""

    webdriver_class: type[WebDriver]
    options_class: type[ArgOptions]
    service_class: type[Service]
    log_output: str
    webdriver_path: str
    browser_binary: str
    service_args: list[str]


#: known testable open source browsers
BROWSERS: dict[str, Browser] = {
    FIREFOX: Browser(
        webdriver_class=Firefox,
        options_class=FirefoxOptions,
        service_class=FirefoxService,
        browser_binary=BROWSER_BIN[FIREFOX],
        webdriver_path="geckodriver",
        log_output="geckodriver.log",
    ),
    CHROMIUM: Browser(
        browser_binary=BROWSER_BIN[CHROMIUM],
        webdriver_class=Chrome,
        options_class=ChromeOptions,
        service_class=ChromeService,
        log_output="chromedriver.log",
        webdriver_path="chromedriver",
    ),
}

#: known testable white-label derivatives
BROWSERS[CHROME] = Browser(**BROWSERS[CHROMIUM])
BROWSERS[CHROME]["browser_binary"] = BROWSER_BIN[CHROME]
