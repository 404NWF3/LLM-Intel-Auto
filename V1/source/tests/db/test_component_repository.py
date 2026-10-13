from __future__ import annotations

from backend.db.repositories.component_repository import normalize_component_alias


def test_normalize_component_alias_removes_common_separators() -> None:
    assert normalize_component_alias("Lang-Chain_Framework") == "langchainframework"


def test_normalize_component_alias_strips_vendor_prefix() -> None:
    assert (
        normalize_component_alias("OpenAI-GPT4o", vendor_name="OpenAI")
        == "gpt4o"
    )

