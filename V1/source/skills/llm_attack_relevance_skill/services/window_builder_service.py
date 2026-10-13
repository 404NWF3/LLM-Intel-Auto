"""Evidence window construction helpers."""

from __future__ import annotations

from collections import defaultdict

from ..schemas.models import EvidenceWindow, KeywordConfig, MatchedKeyword, SentenceSpan, SkillRuntimeOptions


class WindowBuilderService:
    """Build and merge keyword-centered evidence windows."""

    def build_windows(
        self,
        *,
        sentences: list[SentenceSpan],
        matches: list[MatchedKeyword],
        keyword_config: KeywordConfig,
        runtime_options: SkillRuntimeOptions,
    ) -> tuple[list[EvidenceWindow], list[str]]:
        notes: list[str] = []
        sentence_matches = [item for item in matches if item.sentence_index >= 0]
        if not sentence_matches:
            return [], notes

        grouped: dict[int, list[MatchedKeyword]] = defaultdict(list)
        for match in sentence_matches:
            grouped[match.sentence_index].append(match)

        raw_windows: list[tuple[int, int, list[MatchedKeyword]]] = []
        for sentence_index, grouped_matches in sorted(grouped.items()):
            start = max(0, sentence_index - keyword_config.window_sentences_before)
            end = min(len(sentences) - 1, sentence_index + keyword_config.window_sentences_after)
            max_end = start + runtime_options.max_sentences_per_window - 1
            end = min(end, max_end)
            raw_windows.append((start, end, grouped_matches))

        merged_windows = self._merge_windows(raw_windows, merge=runtime_options.merge_overlapping_windows)
        built_windows = [
            self._materialize_window(index, item, sentences) for index, item in enumerate(merged_windows, start=1)
        ]

        if len(built_windows) > runtime_options.max_windows_per_item:
            built_windows = sorted(
                built_windows,
                key=lambda window: (
                    window.score_hint or 0.0,
                    -(window.end_sentence_index - window.start_sentence_index),
                ),
                reverse=True,
            )[: runtime_options.max_windows_per_item]
            built_windows = sorted(built_windows, key=lambda window: window.start_sentence_index)
            notes.append(
                f"Window count truncated to top {runtime_options.max_windows_per_item} evidence windows."
            )

        total_chars = 0
        for window in built_windows:
            next_total = total_chars + len(window.text)
            if next_total <= runtime_options.max_total_chars_for_llm:
                total_chars = next_total
                continue
            window.included_in_llm_prompt = False

        if any(not window.included_in_llm_prompt for window in built_windows):
            notes.append("Some evidence windows were excluded from the LLM prompt due to character budget.")

        return built_windows, notes

    @staticmethod
    def _merge_windows(
        windows: list[tuple[int, int, list[MatchedKeyword]]],
        *,
        merge: bool,
    ) -> list[tuple[int, int, list[MatchedKeyword]]]:
        if not windows:
            return []
        if not merge:
            return windows

        merged: list[tuple[int, int, list[MatchedKeyword]]] = []
        current_start, current_end, current_matches = windows[0]
        for start, end, matches in windows[1:]:
            if start <= current_end:
                current_end = max(current_end, end)
                current_matches = current_matches + matches
                continue
            merged.append((current_start, current_end, current_matches))
            current_start, current_end, current_matches = start, end, matches
        merged.append((current_start, current_end, current_matches))
        return merged

    @staticmethod
    def _materialize_window(
        index: int,
        window: tuple[int, int, list[MatchedKeyword]],
        sentences: list[SentenceSpan],
    ) -> EvidenceWindow:
        start, end, matches = window
        window_sentences = [sentence.text for sentence in sentences[start : end + 1]]
        llm_term_hits = sum(1 for item in matches if item.term_type == "llm_term")
        attack_term_hits = sum(1 for item in matches if item.term_type == "attack_term")
        exclusion_hits = sum(1 for item in matches if item.term_type == "exclusion_term")
        score_hint = (llm_term_hits * 1.2) + (attack_term_hits * 1.5) - (exclusion_hits * 2.0)
        return EvidenceWindow(
            window_id=f"window-{index}",
            start_sentence_index=start,
            end_sentence_index=end,
            matched_terms=list(matches),
            text=" ".join(window_sentences).strip(),
            score_hint=round(score_hint, 3),
            included_in_llm_prompt=True,
        )
