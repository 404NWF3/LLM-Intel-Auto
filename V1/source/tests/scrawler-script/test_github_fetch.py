"""
=== SAADS WP1-1 验证脚本: GitHub Security Advisories 数据采集 ===

功能: 验证通过 GitHub GraphQL API 搜索安全公告是否正常

前置配置:
  1. 复制 .env.example 为 .env (如果还没有)
  2. 【必须】填入 GITHUB_TOKEN=ghp_xxx
     创建地址: https://github.com/settings/tokens
     权限: 无需特殊权限，默认的 public_repo 即可访问 GraphQL Security Advisories
  3. 无需 OPENAI_API_KEY (本脚本不使用 LLM)

运行方式:
  python tests/scripts/test_github_fetch.py

预期输出:
  - 搜索 "langchain" 相关的安全公告列表
  - 每条包含: ghsa_id, cve_id, summary, severity, cvss_score
  - 如果 GITHUB_TOKEN 未配置，会提示错误信息
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import json
from saads.tools.api_tools import _search_github_advisories_impl


def main():
    print("=" * 60)
    print("SAADS — GitHub Security Advisories 数据采集验证")
    print("=" * 60)

    # 检查 Token 状态
    from saads.config import GITHUB_TOKEN

    if GITHUB_TOKEN:
        print(f"\n[OK] GITHUB_TOKEN 已配置 (速率: 5000次/小时)")
    else:
        print(f"\n[ERROR] GITHUB_TOKEN 未配置! GitHub GraphQL API 需要 Token。")
        print(f"  请在 .env 中设置: GITHUB_TOKEN=ghp_your_token")
        print(f"  创建地址: https://github.com/settings/tokens\n")

    # --- 测试 1: 搜索 langchain 相关安全公告 ---
    print("--- 测试 1: 搜索 'langchain' ---")
    result = _search_github_advisories_impl("langchain", max_results=5)

    try:
        data = json.loads(result)
        if isinstance(data, dict) and "error" in data:
            print(f"  [ERROR] {data['error']}\n")
        elif isinstance(data, list):
            print(f"找到 {len(data)} 条安全公告\n")
            for i, adv in enumerate(data, 1):
                print(
                    f"  [{i}] {adv.get('ghsa_id', 'N/A')} | CVE: {adv.get('cve_id', 'N/A')}"
                )
                print(
                    f"      严重性: {adv.get('severity', 'N/A')} | CVSS: {adv.get('cvss_score', 'N/A')}"
                )
                print(f"      摘要: {adv.get('summary', 'N/A')[:100]}...")
                if adv.get("affected_packages"):
                    print(f"      受影响包: {', '.join(adv['affected_packages'][:3])}")
                print()
        else:
            print(f"返回结果: {result[:500]}")
    except json.JSONDecodeError:
        print(f"返回非 JSON 结果: {result[:500]}")

    # --- 测试 2: 搜索 LLM 相关安全公告 ---
    print("--- 测试 2: 搜索 'LLM' ---")
    result2 = _search_github_advisories_impl("LLM", max_results=5)

    try:
        data2 = json.loads(result2)
        if isinstance(data2, dict) and "error" in data2:
            print(f"  [ERROR] {data2['error']}\n")
        elif isinstance(data2, list):
            print(f"找到 {len(data2)} 条安全公告\n")
            for i, adv in enumerate(data2, 1):
                print(
                    f"  [{i}] {adv.get('ghsa_id', 'N/A')}: {adv.get('summary', 'N/A')[:80]}..."
                )
                print()
        else:
            print(f"返回结果: {result2[:500]}")
    except json.JSONDecodeError:
        print(f"返回非 JSON 结果: {result2[:500]}")

    print("=" * 60)
    print("GitHub Advisories 验证完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
