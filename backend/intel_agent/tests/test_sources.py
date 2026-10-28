from __future__ import annotations

from intel_agent import sources


def test_parse_nvd_items_classifies_ai_native_attack():
    data = {
        "vulnerabilities": [
            {
                "cve": {
                    "id": "CVE-2026-0001",
                    "descriptions": [
                        {"lang": "en", "value": "Prompt injection in a large language model app."}
                    ],
                    "published": "2026-06-01T00:00:00.000",
                    "weaknesses": [
                        {"description": [{"value": "CWE-94"}]}
                    ],
                    "references": [{"url": "https://vendor/advisory"}],
                }
            }
        ]
    }
    items = sources.parse_nvd_items(data)
    assert len(items) == 1
    item = items[0]
    assert item.item_id == "nvd:cve-2026-0001"
    assert item.metadata["ai_intel_category"] == "ai_native_attack"
    assert item.relevance_score >= 0.68
    assert "CWE-94" in item.metadata["cwe_ids"]


def test_parse_arxiv_items_skips_error_entry():
    xml = """<?xml version='1.0'?>
    <feed xmlns='http://www.w3.org/2005/Atom'>
      <entry>
        <id>http://arxiv.org/abs/2606.00001v1</id>
        <title>Jailbreaking Aligned LLMs</title>
        <summary>We study jailbreak attacks on aligned models.</summary>
        <published>2026-06-01T00:00:00Z</published>
        <author><name>Jane Doe</name></author>
      </entry>
    </feed>"""
    items = sources.parse_arxiv_items(xml)
    assert len(items) == 1
    assert items[0].item_id == "arxiv:2606.00001v1"
    assert items[0].metadata["authors"] == ["Jane Doe"]


def test_parse_cisa_kev_filters_by_keyword():
    data = {
        "vulnerabilities": [
            {
                "cveID": "CVE-2026-1111",
                "vulnerabilityName": "LLM plugin RCE",
                "shortDescription": "prompt injection leads to tool abuse",
                "vendorProject": "Acme",
                "product": "Chatbot",
                "dateAdded": "2026-06-02",
            },
            {
                "cveID": "CVE-2000-9999",
                "vulnerabilityName": "Old printer bug",
                "shortDescription": "buffer overflow in printer firmware",
                "dateAdded": "2000-01-01",
            },
        ]
    }
    items = sources.parse_cisa_kev_items(data, "prompt injection", [], None, 10)
    ids = {item.item_id for item in items}
    assert "cisa-kev:cve-2026-1111" in ids
    assert "cisa-kev:cve-2000-9999" not in ids


def test_build_nvd_query_params_prefers_cve_id():
    params = sources._build_nvd_query_params(
        "look at CVE-2026-0002 please", 10, None, None, None, False, None, False, None, None, True
    )
    assert params["cveId"] == "CVE-2026-0002"
    assert "keywordSearch" not in params
    assert "noRejected" in params


def test_nvd_query_params_support_page_offset():
    params = sources._build_nvd_query_params(
        "agent tool abuse", 20, None, None, None, False, None, False, None, None, True,
        start_index=40,
    )
    assert params["startIndex"] == "40"


def test_build_arxiv_search_query_uses_categories():
    query = sources.build_arxiv_search_query("jailbreak", ["jailbreak"])
    assert "cat:cs.CR" in query
    assert 'all:"jailbreak"' in query


def test_arxiv_preserves_full_multiline_summary_without_character_limit():
    from xml.sax.saxutils import escape
    summary = "Paragraph & formula <x>.\n\n" + "full abstract " * 3000 + "END"
    xml = f'''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
    <id>https://arxiv.org/abs/2601.12345v1</id><title>Paper</title>
    <summary>{escape(summary)}</summary></entry></feed>'''
    item = sources.parse_arxiv_items(xml)[0]
    assert item.raw_text == summary
    assert item.summary == summary
