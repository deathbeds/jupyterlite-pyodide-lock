import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tornado.httpclient import AsyncHTTPClient

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

    def initialize(
        self, remote: str, rewrites: TRewriteMap | None = None, **kwargs: Any
    ):
        super().initialize(**kwargs)
        self.remote = remote
        self.client = AsyncHTTPClient()
        self.rewrites = rewrites or {}

    async def get(self, path: str, include_body: bool = True) -> None:
        """Actually fetch a file"""
        cache_path = self.root / path
        if cache_path.exists():  # pragma: no cover
            cache_path.touch()
        else:
            await self.cache_file(path, cache_path)
        return await super().get(path, include_body)

    async def cache_file(self, path: str, cache_path: Path):
        """Get the file, and rewrite it."""
        if not cache_path.parent.exists():  # pragma: no cover
            cache_path.parent.mkdir(parents=True)

        url = f"{self.remote}/{path}"
        self.log.debug("[cacher] fetching:    %s", url)
        res = await self.client.fetch(url)

        body = res.body

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
                    raise NotImplementedError(
                        f"Don't know what to do with {type(replacement)}"
                    )

        cache_path.write_bytes(body)
