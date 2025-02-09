"""A ``tornado`` handler for proxying remote CDN files with a cache."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tornado.httpclient import AsyncHTTPClient, HTTPError
from tornado.simple_httpclient import HTTPTimeoutError

from .mime import ExtraMimeFiles

TReplacer = bytes | Callable[[bytes], bytes]
TRouteRewrite = tuple[str, TReplacer]
TRewriteMap = dict[str, list[TRouteRewrite]]


class CachingRemoteFiles(ExtraMimeFiles):
    """a handler which serves files from a cache, downloading them as needed."""

    #: remote URL root
    remote: str
    #: HTTP client
    client: AsyncHTTPClient
    #: URL patterns that should have text replaced
    rewrites: TRewriteMap

    def initialize(self, *args: Any, **kwargs: Any) -> None:
        """Extend the base initialize with instance members."""
        remote: str = kwargs.pop("remote")
        rewrites: TRewriteMap | None = kwargs.pop("rewrites", None)
        super().initialize(*args, **kwargs)
        self.remote = remote
        self.client = AsyncHTTPClient()
        self.rewrites = rewrites or {}

    async def get(self, path: str, include_body: bool = True) -> None:  # noqa: FBT002, FBT001
        """Actually fetch a file."""
        cache_path = Path(self.root) / path
        if cache_path.exists():  # pragma: no cover
            cache_path.touch()
        else:
            await self.cache_file(path, cache_path)
        return await super().get(path, include_body=include_body)

    async def cache_file(self, path: str, cache_path: Path) -> None:
        """Get the file, and rewrite it."""
        if not cache_path.parent.exists():  # pragma: no cover
            cache_path.parent.mkdir(parents=True)

        url = f"{self.remote}/{path}"
        body = await self.fetch_body_with_retries(url)

        for url_pattern, replacements in self.rewrites.items():
            if re.search(url_pattern, path) is None:  # pragma: no cover
                self.log.debug("[cacher] %s is not %s", url, url_pattern)
                continue
            for marker, replacement in replacements:
                if marker not in body:  # pragma: no cover
                    self.log.debug("[cacher] %s does not contain %s", url, marker)
                    continue
                self.log.debug("[cacher] %s contains %s", url, marker)
                if isinstance(replacement, bytes):
                    body = body.replace(marker, replacement)
                elif callable(replacement):
                    body = replacement(body)
                else:  # pragma: no cover
                    msg = f"Don't know what to do with {type(replacement)}"
                    raise NotImplementedError(msg)

        cache_path.write_bytes(body)

    async def fetch_body_with_retries(self, url: str, retries: int = 5) -> bytes:
        """Fetch the raw bytes of URL with retries.

        In the event of a timeout, wait for an increasing number of seconds
        """
        self.log.debug("[cacher] fetching:    %s", url)
        last_error: HTTPError | None = None
        for attempt in range(retries):
            await asyncio.sleep(2**attempt)
            try:
                res = await self.client.fetch(url)
            except HTTPTimeoutError as err:  # pragma: no cover
                last_error = err
                continue
            else:
                return res.body

        if TYPE_CHECKING:
            assert last_error

        raise last_error  # pragma: no cover
