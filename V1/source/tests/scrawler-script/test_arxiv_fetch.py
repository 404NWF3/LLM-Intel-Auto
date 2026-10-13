"""
=== SAADS WP1-1 验证脚本: arXiv 论文搜索 ===

功能: 验证从 arXiv 搜索 AI 安全相关论文是否正常

前置配置:
  1. 无需任何配置! arXiv API 完全公开，无需 API key。
  2. 仅需网络连接。

运行方式:
  python tests/scripts/test_arxiv_fetch.py

预期输出:
  - 搜索 "prompt injection attack LLM" 相关的论文列表
  - 每条包含: 标题、作者、分类、发布日期、摘要

注意:
  - arXiv 要求请求间隔 >= 3 秒，本脚本已内置延迟。
  - 连续快速测试会触发 429 限速；_search_arxiv_impl 内部有重试机制。
"""

import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import json
from saads.tools.api_tools import _search_arxiv_impl


def _print_papers(data: list, label: str) -> None:
    print(f"找到 {len(data)} 篇论文\n")
    for i, paper in enumerate(data, 1):
        print(f"  [{i}] {paper.get('title', 'N/A')}")
        authors = paper.get("authors", [])
        if authors:
            author_str = ", ".join(authors[:3])
            if len(authors) > 3:
                author_str += f" et al. ({len(authors)} authors)"
            print(f"      作者: {author_str}")
        cats = paper.get("categories", [])
        if cats:
            print(f"      分类: {', '.join(cats)}")
        print(f"      发布: {paper.get('published', 'N/A')[:10]}")
        print(f"      链接: {paper.get('url', 'N/A')}")
        summary = paper.get("summary", "")
        if summary:
            print(f"      摘要: {summary[:150]}...")
        print()


def run_test(label: str, query: str, max_results: int) -> bool:
    """Run a single arXiv search test. Returns True on success."""
    print(f"--- {label} ---")
    print(f"    查询: {query!r}")
    result = _search_arxiv_impl(query, max_results=max_results)

    if result.startswith("Error"):
        print(f"[FAIL] {result}\n")
        return False

    try:
        data = json.loads(result)
    except json.JSONDecodeError as exc:
        print(f"[FAIL] JSON decode error: {exc}")
        print(f"       Raw response (first 500 chars): {result[:500]}\n")
        return False

    if not isinstance(data, list):
        print(f"[FAIL] Unexpected result type: {type(data)}")
        print(f"       Raw: {result[:500]}\n")
        return False

    _print_papers(data, label)
    print(f"[OK] {label} passed\n")
    return True


def main():
    print("=" * 60)
    print("SAADS — arXiv 论文搜索验证")
    print("=" * 60)
    print("\n[INFO] arXiv API 无需配置，直接使用")
    print("[INFO] 请求间隔 3 秒（arXiv 礼貌性要求）\n")

    tests = [
        # (label, query, max_results)
        (
            "测试 1: 搜索 'prompt injection attack LLM' (plain keywords)",
            "prompt injection attack LLM",
            5,
        ),
        (
            "测试 2: 搜索 jailbreak (arXiv operator syntax)",
            'all:jailbreak AND all:"language model"',
            3,
        ),
        (
            "测试 3: 搜索 adversarial multimodal (arXiv operator syntax)",
            'all:adversarial AND all:multimodal AND all:"language model"',
            3,
        ),
    ]

    passed = 0
    for idx, (label, query, max_results) in enumerate(tests):
        if idx > 0:
            print("[INFO] Sleeping 3 s between requests (arXiv rate limit)...\n")
            time.sleep(3)
        if run_test(label, query, max_results):
            passed += 1

    print("=" * 60)
    print(f"arXiv API 验证完成: {passed}/{len(tests)} 测试通过")
    print("=" * 60)


if __name__ == "__main__":
    main()
