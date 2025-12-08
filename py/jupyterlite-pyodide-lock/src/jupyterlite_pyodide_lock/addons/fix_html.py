"""An addon for patching paths in HTML files."""
# Copyright (c) jupyterlite-pyodide-lock contributors.
# Distributed under the terms of the BSD-3-Clause License.

from __future__ import annotations

import json
import os
import re
from typing import TYPE_CHECKING, Any, ClassVar

from jupyterlite_core.addons.base import BaseAddon
from jupyterlite_core.constants import UTF8
from jupyterlite_core.trait_types import TypedTuple
from traitlets import Bool, Dict, Unicode

if TYPE_CHECKING:
    from pathlib import Path

    from jupyterlite_core.manager import LiteManager

    from ._base import TTaskGenerator

RE_HTML_CONFIG = re.compile(
    r"""(?P<tag><script[^>]+id="jupyter-config-data"[^>]*>)\s*"""
    r"""(?P<page_config>\{.*?\})"""
    r"""\s*(?P<endtag></script>)""",
    flags=re.MULTILINE | re.DOTALL,
)

RE_REL_ATTR = re.compile(
    r'''\b(?P<attr>href|src)\s*=\s*"\./(?P<path>.*?)"''',
    flags=re.MULTILINE | re.DOTALL,
)


class FixHtmlAddon(BaseAddon):
    """Patch relative paths in HTML, including ``jupyter-config-data`` scripts."""

    __all__: ClassVar[list[str]] = ["post_build"]

    enabled: bool = Bool(
        default_value=False,
        help="enable fixing paths of ``jupyter-config-data`` in HTML",
    ).tag(config=True)

    task_dep: tuple[str] = TypedTuple(
        Unicode(),
        help=(
            "task names to wait for; may use any manager traits "
            " e.g. ``['post_build:voici:voici:update_index:{output_dir}']``"
        ),
    ).tag(config=True)

    file_dep: tuple[str] = TypedTuple(
        Unicode(),
        help=(
            "output HTML globs that should be updated,  e.g. ``['voici/**/*.html']``"
        ),
    ).tag(config=True)

    ignore_attributes: tuple[str] = TypedTuple(
        Unicode(),
        default_value=("licensesUrl", "themesUrl", "federated_extensions"),
        help=("``jupyter-config-data`` attributes to ignore"),
    ).tag(config=True)

    rewrite_missing: dict[str, str] = Dict(
        help=(
            "redirect patterns for missing ``href`` and ``src`` paths, e.g."
            """ ``"^(.*)$": "/files/\\1\" target=\"_blank"`` """
        )
    ).tag(config=True)

    extra_ignore_attributes: tuple[str] = TypedTuple(
        Unicode(), help=("extra ``jupyter-config-data`` attributes to ignore")
    )

    def post_build(self, manager: LiteManager) -> TTaskGenerator:
        """Fix embedded ``jupyter-config-data`` in HTML paths."""
        if not (self.enabled and self.task_dep and self.file_dep):
            return
        context = {**self.manager._trait_values}  # noqa: SLF001
        task_dep = [td.format(**context) for td in self.task_dep]
        yield self.task(
            name="fix-paths",
            actions=[self._fix_all_html_config],
            task_dep=task_dep,
        )

    def _fix_all_html_config(self) -> bool:
        """Discover and fix relative paths in all HTML ``jupyter-config-data``."""
        html_paths = [h for p in self.file_dep for h in self.manager.output_dir.glob(p)]
        if not html_paths:
            self.log.error("Found no paths to fix from %s", self.file_dep)
            return False
        self.log.warning("Fixing paths in HTML files: %s", len(html_paths))
        fixed = [self._fix_one_html(h) for h in html_paths]
        fix_count = sum(map(int, fixed))
        self.log.warning("Fixed paths in HTML files: %s", fix_count)
        if fix_count:
            return True
        self.log.error(
            "No HTML paths were fixed; adjust ``FixHtmlAddon.task_dep``"
            " and/or ``FixHtmlAddon.file_dep``"
        )
        return False

    def _fix_one_html(self, html_path: Path) -> bool:
        """Fix relative paths in and HTML file, including ``jupyter-config-data``."""
        path_prefix = os.path.relpath(self.manager.output_dir, html_path.parent)
        html = html_path.read_text(**UTF8)

        def _config_replacer(match: re.Match[str]) -> str:
            groups = match.groupdict()
            page_config = json.loads(groups["page_config"])
            self._fix_relative_config_urls(page_config, f"{path_prefix}/")
            new_config_json = json.dumps(page_config, indent=2, sort_keys=True)
            self.log.warning("Fixed paths in %s", html_path)
            return "\n".join([groups["tag"], new_config_json, groups["endtag"]])

        new_html = RE_HTML_CONFIG.sub(_config_replacer, html)

        if self.rewrite_missing:

            def _missing_link_replacer(match: re.Match[str]) -> str:
                groups = match.groupdict()
                attr, path = groups["attr"], groups["path"]
                dest = html_path.parent / path
                new_path = f"./{path}"
                if not dest.exists():
                    for pattern, replacement in self.rewrite_missing.items():
                        if re.match(pattern, path) is None:
                            continue
                        new_path = re.sub(pattern, replacement, path)
                        new_path = f"{path_prefix}{new_path}"
                        self.log.warning(
                            "[html] [%s] rewrote missing %s to %s",
                            html_path,
                            path,
                            new_path,
                        )
                        break
                return f"""{attr}="{new_path}" """

        new_html = RE_REL_ATTR.sub(_missing_link_replacer, new_html)

        html_path.write_text(new_html, **UTF8)
        return True

    def _fix_relative_config_urls(
        self, config_dict: dict[str, Any], path_prefix: str
    ) -> None:
        """Update one ``jupyter-config-data`` object in place with relative URLs.

        See: https://github.com/jupyterlite/jupyterlite/blame/v0.7.0/app/config-utils.js
        """
        ignore_attributes = {self.ignore_attributes, self.extra_ignore_attributes}
        for key, value in config_dict.items():
            if key in ignore_attributes:
                continue
            if isinstance(value, dict):
                # nested config objects may also contain relative paths
                self._fix_relative_config_urls(value, path_prefix)
            elif (
                key.endswith("Url")
                and isinstance(value, str)
                and value.startswith("./")
            ):
                config_dict[key] = f"{path_prefix}{value[2:]}"
            elif key.endswith("Urls") and isinstance(value, list):
                config_dict[key] = [
                    f"{path_prefix}{v[2:]}" if v.startswith("./") else v for v in value
                ]
