import re
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any as _Any

from tornado.httpclient import AsyncHTTPClient

from .mime import ExtraMimeFiles

if TYPE_CHECKING:  # pragma: no cover

    pass


class CachingRemoteFiles(ExtraMimeFiles):
    """a handler which serves files from a cache, downloading them as needed."""

    #: remote URL root
    remote: str
    #: HTTP client
    client: AsyncHTTPClient
    #: URL patterns that should have text replaced
    rewrites: dict[str, _Any]

    def initialize(self, remote, rewrites=None, **kwargs):
        super().initialize(**kwargs)
        self.remote = remote
        self.client = AsyncHTTPClient()
        self.rewrites = rewrites or {}

    async def get(self, path: str, include_body: bool = True) -> None:
        """actually fetch a file"""
        cache_path = self.root / path
        if cache_path.exists():  # pragma: no cover
            pass
        else:
            await self.cache_file(path, cache_path)
        return await super().get(path, include_body)

    async def cache_file(self, path: str, cache_path: Path):
        """get the file, and rewrite it."""
        url = f"{self.remote}/{path}"
        self.log.debug("fetching:    %s", url)
        res = await self.client.fetch(url)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        body = res.body

        for url_pattern, replacements in self.rewrites.items():
            if re.search(url_pattern, path) is None:  # pragma: no cover
                self.log.debug("%s is not %s", url, url_pattern)
                continue
            for marker, replacement in replacements:
                if marker not in body:  # pragma: no cover
                    self.log.debug("%s does not contain %s", url, marker)
                else:
                    self.log.debug("found:     %s contains %s", url, marker)
                    body = body.replace(marker, replacement)

        cache_path.write_bytes(body)
