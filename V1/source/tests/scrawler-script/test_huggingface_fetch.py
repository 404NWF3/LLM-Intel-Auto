"""
=== SAADS WP1-1 验证脚本: HuggingFace 数据采集 ===

功能: 验证通过 HuggingFace API 搜索安全相关模型和论文是否正常

前置配置:
  1. 无需 API key（公开端点即可使用）
  2. (可选) 设置 HF_TOKEN 环境变量以提升速率限制
     创建地址: https://huggingface.co/settings/tokens
  3. 无需 OPENAI_API_KEY（本脚本不使用 LLM）

API 说明:
  - /api/models?search= — 搜索模型，按 lastModified 排序，无需认证
  - /api/daily_papers — 获取每日论文（无搜索参数，需客户端过滤）
  - 注意: 不存在全局 /api/discussions 搜索端点

运行方式:
  uv run python tests/scripts/test_huggingface_fetch.py

预期输出:
  - 安全相关模型列表（如 prompt-injection 检测模型）
  - 匹配的每日论文（如果当日有安全相关论文）
  - 每条包含: title, url, downloads/likes (模型) 或 upvotes (论文)
"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import json
import os
from saads.tools.api_tools import _search_huggingface_impl


def main():
    print("=" * 60)
    print("SAADS — HuggingFace 数据采集验证")
    print("=" * 60)

    # 检查 HF_TOKEN
    hf_token = os.getenv("HF_TOKEN", "")
    if hf_token:
        print(f"\n[OK] HF_TOKEN 已配置（速率限制提升）")
    else:
        print(f"\n[INFO] HF_TOKEN 未配置（使用公开端点，速率有限但可用）")

    total_results = 0

    # --- 测试 1: 搜索 prompt injection 相关模型 ---
    print("\n--- 测试 1: 搜索 'prompt injection' ---")
    result = _search_huggingface_impl("prompt injection", max_results=10)

    if result.startswith("Error"):
        print(f"  [ERROR] {result}")
    else:
        try:
            data = json.loads(result)
            if isinstance(data, list):
                models = [d for d in data if d.get("item_type") == "model"]
                papers = [d for d in data if d.get("item_type") == "paper"]

                print(f"  找到 {len(models)} 个模型 + {len(papers)} 篇论文\n")

                if models:
                    print("  === 模型 ===")
                    for i, m in enumerate(models, 1):
                        print(f"  [{i}] {m.get('title', 'N/A')}")
                        print(
                            f"      下载: {m.get('downloads', 0):,} | "
                            f"点赞: {m.get('likes', 0)}"
                        )
                        print(f"      URL: {m.get('url', 'N/A')}")
                        tags = m.get("tags", [])
                        if tags:
                            print(f"      标签: {', '.join(tags[:5])}")
                        print()

                if papers:
                    print("  === 论文 ===")
                    for i, p in enumerate(papers, 1):
                        print(f"  [{i}] {p.get('title', 'N/A')[:80]}")
                        print(f"      URL: {p.get('url', 'N/A')}")
                        print(f"      时间: {p.get('published', 'N/A')[:10]}")
                        print()

                total_results += len(data)
            else:
                print(f"  返回结果: {result[:500]}")
        except json.JSONDecodeError:
            print(f"  返回非 JSON 结果: {result[:300]}")

    # --- 测试 2: 搜索 security 相关模型 ---
    print("\n--- 测试 2: 搜索 'security vulnerability' ---")
    result2 = _search_huggingface_impl("security vulnerability", max_results=5)

    if result2.startswith("Error"):
        print(f"  [ERROR] {result2}")
    else:
        try:
            data2 = json.loads(result2)
            if isinstance(data2, list):
                models2 = [d for d in data2 if d.get("item_type") == "model"]
                papers2 = [d for d in data2 if d.get("item_type") == "paper"]
                print(f"  找到 {len(models2)} 个模型 + {len(papers2)} 篇论文\n")

                for i, item in enumerate(data2, 1):
                    kind = item.get("item_type", "?")
                    print(f"  [{i}] ({kind}) {item.get('title', 'N/A')[:70]}")
                    print(f"      URL: {item.get('url', 'N/A')}")
                    print()

                total_results += len(data2)
            else:
                print(f"  返回结果: {result2[:500]}")
        except json.JSONDecodeError:
            print(f"  返回非 JSON 结果: {result2[:300]}")

    # --- 测试 3: 搜索 jailbreak 相关内容 ---
    print("\n--- 测试 3: 搜索 'jailbreak LLM' ---")
    result3 = _search_huggingface_impl("jailbreak LLM", max_results=5)

    if result3.startswith("Error"):
        print(f"  [ERROR] {result3}")
    else:
        try:
            data3 = json.loads(result3)
            if isinstance(data3, list):
                print(f"  找到 {len(data3)} 条结果\n")
                for i, item in enumerate(data3, 1):
                    kind = item.get("item_type", "?")
                    print(f"  [{i}] ({kind}) {item.get('title', 'N/A')[:70]}")
                    print(f"      URL: {item.get('url', 'N/A')}")
                    print()
                total_results += len(data3)
            else:
                print(f"  返回结果: {result3[:500]}")
        except json.JSONDecodeError:
            print(f"  返回非 JSON 结果: {result3[:300]}")

    print("=" * 60)
    print(f"HuggingFace 验证完成! 共获取 {total_results} 条结果")
    if total_results > 0:
        print("[OK] HuggingFace API 数据采集正常工作")
    else:
        print("[WARN] 未获取到结果 -- 可能是网络问题或 API 限速")
    print("=" * 60)


if __name__ == "__main__":
    main()
