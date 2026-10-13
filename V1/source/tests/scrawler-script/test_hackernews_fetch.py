"""
=== SAADS WP1-1 验证脚本: HackerNews 数据采集 ===

功能: 验证通过 Algolia HN Search API 搜索安全相关讨论是否正常

前置配置:
  1. 无需任何 API key（Algolia HN Search API 完全公开）
  2. 无需 OPENAI_API_KEY（本脚本不使用 LLM）
  3. 速率限制: ~10,000 次/小时（非常宽松）

API 说明:
  - 端点: https://hn.algolia.com/api/v1/search
  - 参数: query, tags=story, hitsPerPage
  - 返回: title, url, points, author, created_at, num_comments

运行方式:
  uv run python tests/scripts/test_hackernews_fetch.py

预期输出:
  - LLM 安全相关的 HackerNews 故事列表
  - 每条包含: title, url, points, num_comments, author
"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import json
from saads.tools.api_tools import _search_hackernews_impl


def test_query(query: str, max_results: int = 5):
    """测试单个查询。"""
    print(f"\n--- 搜索 HackerNews: '{query}' (max={max_results}) ---")
    result = _search_hackernews_impl(query, max_results=max_results)

    if result.startswith("Error"):
        print(f"  [ERROR] {result}")
        return 0

    try:
        data = json.loads(result)
        if isinstance(data, list):
            print(f"  找到 {len(data)} 条故事\n")
            for i, story in enumerate(data, 1):
                title = story.get("title", "N/A")
                points = story.get("points", 0)
                comments = story.get("num_comments", 0)
                author = story.get("author", "N/A")
                created = story.get("created_at", "N/A")[:10]
                url = story.get("url", "N/A")

                print(f"  [{i}] {title[:80]}")
                print(f"      分数: {points} | 评论: {comments} | 作者: {author}")
                print(f"      时间: {created}")
                if url and url != "N/A":
                    print(f"      URL: {url[:80]}")
                print()
            return len(data)
        else:
            print(f"  返回非列表结果: {result[:300]}")
            return 0
    except json.JSONDecodeError:
        print(f"  返回非 JSON 结果: {result[:300]}")
        return 0


def main():
    print("=" * 60)
    print("SAADS — HackerNews (Algolia API) 数据采集验证")
    print("=" * 60)
    print("\n[INFO] 使用 Algolia HN Search API（无需 API key）")
    print("[INFO] 速率限制: ~10,000 次/小时")

    total = 0

    # --- 测试 1: LLM prompt injection ---
    total += test_query("LLM prompt injection", max_results=5)

    # --- 测试 2: AI security vulnerability ---
    total += test_query("AI security vulnerability", max_results=5)

    # --- 测试 3: jailbreak language model ---
    total += test_query("jailbreak language model", max_results=5)

    print("=" * 60)
    print(f"HackerNews 验证完成! 共获取 {total} 条故事")
    if total > 0:
        print("[OK] HackerNews Algolia API 数据采集正常工作")
    else:
        print("[WARN] 未获取到故事 -- 可能是网络问题")
    print("=" * 60)


if __name__ == "__main__":
    main()
