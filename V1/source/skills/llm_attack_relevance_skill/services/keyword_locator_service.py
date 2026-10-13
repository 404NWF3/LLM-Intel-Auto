"""Keyword matching logic for sentence windows."""

from __future__ import annotations

from ..schemas.models import KeywordConfig, MatchedKeyword, SentenceSpan


class KeywordLocatorService:
    """Locate configured keywords across sentence spans."""

    def locate(
        self,
        *,
        sentences: list[SentenceSpan],
        keyword_config: KeywordConfig,
        title: str | None = None,
        summary: str | None = None,
    ) -> list[MatchedKeyword]:
        hits: list[MatchedKeyword] = []
        for sentence in sentences:
            lowered = sentence.text.casefold()
            hits.extend(self._find_hits_in_text(lowered, sentence, keyword_config.llm_terms, "llm_term"))
            hits.extend(self._find_hits_in_text(lowered, sentence, keyword_config.attack_terms, "attack_term"))
            hits.extend(
                self._find_hits_in_text(lowered, sentence, keyword_config.exclusion_terms, "exclusion_term")
            )

        title_summary = " ".join(part for part in [title or "", summary or ""] if part).strip()
        if title_summary:
            lowered = title_summary.casefold()
            hits.extend(self._find_hits_in_virtual_text(lowered, -1, keyword_config.llm_terms, "llm_term"))
            hits.extend(self._find_hits_in_virtual_text(lowered, -1, keyword_config.attack_terms, "attack_term"))
            hits.extend(
                self._find_hits_in_virtual_text(lowered, -1, keyword_config.exclusion_terms, "exclusion_term")
            )

        return sorted(
            hits,
            key=lambda item: (
                item.sentence_index,
                item.char_start if item.char_start is not None else -1,
                item.term,
            ),
        )

    @staticmethod
    def _find_hits_in_text(
        lowered_text: str,
        sentence: SentenceSpan,
        terms: list[str],
        term_type: str,
    ) -> list[MatchedKeyword]:
        matches: list[MatchedKeyword] = []
        for term in terms:
            term_lower = term.casefold()
            start = lowered_text.find(term_lower)
            while start != -1:
                matches.append(
                    MatchedKeyword(
                        sentence_index=sentence.sentence_index,
                        term=term,
                        term_type=term_type,
                        char_start=start,
                        char_end=start + len(term_lower),
                    )
                )
                start = lowered_text.find(term_lower, start + len(term_lower))
        return matches

    @staticmethod
    def _find_hits_in_virtual_text(
        lowered_text: str,
        sentence_index: int,
        terms: list[str],
        term_type: str,
    ) -> list[MatchedKeyword]:
        matches: list[MatchedKeyword] = []
        for term in terms:
            term_lower = term.casefold()
            start = lowered_text.find(term_lower)
            while start != -1:
                matches.append(
                    MatchedKeyword(
                        sentence_index=sentence_index,
                        term=term,
                        term_type=term_type,
                        char_start=start,
                        char_end=start + len(term_lower),
                    )
                )
                start = lowered_text.find(term_lower, start + len(term_lower))
        return matches

