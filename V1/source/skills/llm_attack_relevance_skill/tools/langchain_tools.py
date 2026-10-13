"""LangChain adapter for the skill bundle."""

from __future__ import annotations

from langchain_core.tools import StructuredTool

from ..executor import run_llm_attack_relevance_skill


def build_langchain_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=run_llm_attack_relevance_skill,
        name="llm_attack_relevance_tool",
        description="Judge whether raw candidate content is substantially about attacks on LLM systems.",
    )
