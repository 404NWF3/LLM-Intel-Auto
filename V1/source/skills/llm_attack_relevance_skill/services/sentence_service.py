"""Sentence splitting utilities."""

from __future__ import annotations

import re

from ..schemas.models import SentenceSpan


class SentenceService:
    """Provide lightweight multilingual sentence segmentation."""

    _SENTENCE_BOUNDARY_RE = re.compile(r".+?(?:[。！？!?\.]+(?:\s+|$)|$)", re.DOTALL)

    def split_sentences(self, text: str) -> list[SentenceSpan]:
        if not text.strip():
            return []

        spans: list[SentenceSpan] = []
        for match in self._SENTENCE_BOUNDARY_RE.finditer(text):
            sentence_text = match.group(0).strip()
            if not sentence_text:
                continue
            spans.append(
                SentenceSpan(
                    sentence_index=len(spans),
                    text=sentence_text,
                    char_start=match.start(),
                    char_end=match.end(),
                )
            )
        return spans

