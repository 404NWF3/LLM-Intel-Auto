"""Text cleaning helpers for the skill bundle."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup


class CleaningService:
    """Perform minimal HTML and whitespace cleanup before sentence splitting."""

    _MARKDOWN_DECORATION_RE = re.compile(r"[`#>*_\-\[\]\(\)]")
    _WHITESPACE_RE = re.compile(r"\s+")

    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        stripped_html = BeautifulSoup(text, "html.parser").get_text(" ")
        de_marked = self._MARKDOWN_DECORATION_RE.sub(" ", stripped_html)
        collapsed = self._WHITESPACE_RE.sub(" ", de_marked)
        return collapsed.strip()

