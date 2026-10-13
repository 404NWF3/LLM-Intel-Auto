"""
=== SAADS WP1-1 验证脚本: NVD API 数据采集 ===

功能: 验证从 NVD (National Vulnerability Database) 搜索 CVE 是否正常

前置配置:
  1. 复制 .env.example 为 .env (如果还没有)
  2. (可选) 填入 NVD_API_KEY=your_key  — 提升访问速率 (5次/30秒 → 50次/30秒)
     申请地址: https://nvd.nist.gov/developers/request-an-api-key
  3. 无需 OPENAI_API_KEY (本脚本不使用 LLM)

运行方式:
  python tests/scripts/test_nvd_fetch.py

预期输出:
  - 搜索 "LLM prompt injection" 相关的 CVE 列表
  - 每条包含: cve_id, description, severity, cvss_score, published
  - 如果 NVD 中无相关结果，列表可能为空（这是正常的）
"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import json
from saads.tools.api_tools import _search_nvd_impl


def main():
    print("=" * 60)
    print("SAADS — NVD API 数据采集验证")
    print("=" * 60)

    # 检查 API key 状态
    from saads.config import NVD_API_KEY

    if NVD_API_KEY:
        print(f"\n[OK] NVD_API_KEY 已配置 (速率: 50次/30秒)")
    else:
        print(f"\n[INFO] NVD_API_KEY 未配置 (速率: 5次/30秒, 建议配置以提升速率)")

    # --- 测试 1: 搜索 LLM 相关 CVE ---
    print("\n--- 测试 1: 搜索 'LLM prompt injection' ---")
    result = _search_nvd_impl("LLM prompt injection", max_results=5)

    try:
        data = json.loads(result)
        if isinstance(data, list):
            print(f"找到 {len(data)} 条 CVE\n")
            for i, cve in enumerate(data, 1):
                print(f"  [{i}] {cve.get('cve_id', 'N/A')}")
                print(
                    f"      严重性: {cve.get('severity', 'N/A')} | CVSS: {cve.get('cvss_score', 'N/A')}"
                )
                print(f"      发布: {cve.get('published', 'N/A')[:10]}")
                print(f"      描述: {cve.get('description', 'N/A')[:120]}...")
                print()
        else:
            print(f"返回结果: {result[:500]}")
    except json.JSONDecodeError:
        print(f"返回非 JSON 结果: {result[:500]}")

    # --- 测试 2: 搜索 AI 框架相关 CVE ---
    print("--- 测试 2: 搜索 'langchain' ---")
    result2 = _search_nvd_impl("langchain", max_results=5)

    try:
        data2 = json.loads(result2)
        if isinstance(data2, list):
            print(f"找到 {len(data2)} 条 CVE\n")
            for i, cve in enumerate(data2, 1):
                print(f"  [{i}] {cve.get('cve_id', 'N/A')}")
                print(
                    f"      严重性: {cve.get('severity', 'N/A')} | CVSS: {cve.get('cvss_score', 'N/A')}"
                )
                print(f"      描述: {cve.get('description', 'N/A')[:120]}...")
                print()
        else:
            print(f"返回结果: {result2[:500]}")
    except json.JSONDecodeError:
        print(f"返回非 JSON 结果: {result2[:500]}")

    print("=" * 60)
    print("NVD API 验证完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
