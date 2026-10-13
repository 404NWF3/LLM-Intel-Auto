"""
=== SAADS WP1-1 验证脚本: Reddit RSS 数据采集 ===

功能: 验证通过 Reddit RSS feed 搜索安全相关帖子是否正常

前置配置:
  1. 无需任何 API key（使用公开 RSS 端点）
  2. 无需 OPENAI_API_KEY（本脚本不使用 LLM）
  3. Reddit RSS 端点限速约 100 次/10 分钟

技术说明:
  - Reddit 自 2023 年起封禁了未认证的 .json 端点 (返回 403)
  - 本工具使用 /search.rss 端点 + Atom XML 解析
  - RSS 每次最多返回约 25 条结果
  - 需要自定义 User-Agent 头（否则返回 429）

运行方式:
  uv run python tests/scripts/test_reddit_fetch.py

预期输出:
  - 从 r/netsec、r/MachineLearning 等搜索安全相关帖子
  - 每条包含: title, url, published, author, subreddit
  - 如果某个 subreddit 暂时无结果，列表可能为空（正常）
"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import json
import time
from saads.tools.api_tools import _search_reddit_impl


def test_subreddit(subreddit: str, query: str, limit: int = 5):
    """测试单个 subreddit 搜索。"""
    print(f"\n--- 搜索 r/{subreddit}: '{query}' (limit={limit}) ---")
    result = _search_reddit_impl(subreddit, query, limit=limit)

    if result.startswith("Error"):
        print(f"  [ERROR] {result}")
        return 0

    try:
        data = json.loads(result)
        if isinstance(data, list):
            print(f"  找到 {len(data)} 条帖子\n")
            for i, post in enumerate(data, 1):
                print(f"  [{i}] {post.get('title', 'N/A')[:80]}")
                print(f"      URL: {post.get('url', 'N/A')[:80]}")
                print(f"      作者: {post.get('author', 'N/A')}")
                print(f"      时间: {post.get('published', 'N/A')[:20]}")
                desc = post.get("description", "")
                if desc:
                    print(f"      摘要: {desc[:120]}...")
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
    print("SAADS — Reddit RSS 数据采集验证")
    print("=" * 60)
    print("\n[INFO] 使用公开 RSS 端点（无需 API key）")
    print("[INFO] 自定义 User-Agent: SAADS/1.0")

    total = 0

    # --- 测试 1: r/netsec — 网络安全社区 ---
    count = test_subreddit("netsec", "LLM prompt injection", limit=5)
    total += count
    time.sleep(2)  # 礼貌性等待

    # --- 测试 2: r/MachineLearning — ML 社区 ---
    count = test_subreddit("MachineLearning", "adversarial attack", limit=5)
    total += count
    time.sleep(2)

    # --- 测试 3: r/cybersecurity — 安全社区 ---
    count = test_subreddit("cybersecurity", "AI security vulnerability", limit=5)
    total += count

    print("=" * 60)
    print(f"Reddit RSS 验证完成! 共获取 {total} 条帖子")
    if total > 0:
        print("[OK] Reddit RSS 数据采集正常工作")
    else:
        print("[WARN] 未获取到帖子 -- 可能是关键词太窄或 Reddit 限速")
        print("       这不一定是错误，可以尝试更宽泛的关键词")
    print("=" * 60)


if __name__ == "__main__":
    main()
