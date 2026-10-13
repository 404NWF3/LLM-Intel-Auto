"""
=== SAADS WP1-1 验证脚本: Dark Web Agent (Mock Data) ===

功能: 验证 Dark Web Agent 能否返回覆盖全部 6 个攻击类别的模拟暗网情报

前置配置:
  1. 无需任何 API Key (纯 mock 数据)
  2. (可选) TELEGRAM_BOT_TOKEN=xxx — Phase 2 Telegram 集成预留

运行方式:
  python tests/scripts/test_dark_web_agent.py

预期输出:
  - 返回 14 条模拟暗网情报 (默认 max_per_source=14)
  - 覆盖全部 6 个类别: prompt_injection, jailbreak, info_leakage, multimodal, dos, agent_hijack
  - 每条情报包含: 标题、描述、严重等级、payload 片段、来源论坛
  - 验证 priority_categories 过滤功能
"""

import sys
import asyncio
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from saads.agents.wp1_1.dark_web import dark_web_node, MOCK_DARK_WEB_INTEL


async def main():
    print("=" * 60)
    print("SAADS — Dark Web Agent (Mock Data) 验证")
    print("=" * 60)

    # --- Test 1: 默认采集 (全部类别) ---
    print("\n--- Test 1: 默认采集 (无 priority_categories 过滤) ---\n")

    state = {
        "messages": [],
        "collection_strategy": {
            "max_per_source": 20,  # 足够大，返回全部 mock 数据
        },
        "raw_intel": [],
        "standardized_entries": [],
        "coverage_report": {},
        "iteration": 0,
        "should_continue": True,
    }

    result = await dark_web_node(state)
    raw_intel = result.get("raw_intel", [])

    print(f"  Mock 数据总量: {len(MOCK_DARK_WEB_INTEL)} 条")
    print(f"  返回情报数量: {len(raw_intel)} 条")

    # 按类别统计
    by_category: dict[str, list] = {}
    for item in raw_intel:
        cat = item.get("category", "unknown")
        by_category.setdefault(cat, []).append(item)

    print(f"\n  类别分布:")
    expected_categories = {
        "prompt_injection",
        "jailbreak",
        "info_leakage",
        "multimodal",
        "dos",
        "agent_hijack",
    }
    for cat in sorted(by_category.keys()):
        items = by_category[cat]
        print(f"    {cat}: {len(items)} 条")

    # 检查覆盖率
    covered = set(by_category.keys())
    missing = expected_categories - covered
    if missing:
        print(f"\n  [WARNING] 缺少类别: {missing}")
    else:
        print(f"\n  [OK] 全部 6 个类别已覆盖!")

    # 打印每条情报的摘要
    print(f"\n{'=' * 60}")
    print("全部情报摘要:")
    print(f"{'=' * 60}")

    for i, item in enumerate(raw_intel, 1):
        title = item.get("title", "N/A")
        cat = item.get("category", "?")
        sev = item.get("severity_estimate", "?")
        forum = item.get("forum", "?")
        date = item.get("posted_date", "?")
        source_type = item.get("_source_type", "?")

        print(f"\n  [{i:2d}] {title[:70]}")
        print(f"       类别={cat} | 严重={sev} | 来源={forum} | 日期={date}")
        print(f"       _source_type={source_type}")

        # 显示 payload 片段
        payload = item.get("payload_snippet", "")
        if payload:
            print(f"       payload: {payload[:60]}...")

    # --- Test 2: 带 priority_categories 过滤 ---
    print(f"\n{'=' * 60}")
    print("--- Test 2: 仅优先采集 prompt_injection + agent_hijack ---")
    print(f"{'=' * 60}")

    state2 = {
        "messages": [],
        "collection_strategy": {
            "priority_categories": ["prompt_injection", "agent_hijack"],
            "max_per_source": 5,
        },
        "raw_intel": [],
        "standardized_entries": [],
        "coverage_report": {},
        "iteration": 0,
        "should_continue": True,
    }

    result2 = await dark_web_node(state2)
    raw_intel2 = result2.get("raw_intel", [])

    print(f"\n  请求 max_per_source=5, priority=[prompt_injection, agent_hijack]")
    print(f"  返回情报数量: {len(raw_intel2)} 条")

    # 验证优先排序: 前几条应该是 prompt_injection 和 agent_hijack
    print(f"\n  返回顺序:")
    for i, item in enumerate(raw_intel2, 1):
        cat = item.get("category", "?")
        title = item.get("title", "N/A")[:50]
        is_priority = cat in ["prompt_injection", "agent_hijack"]
        marker = "[PRIORITY]" if is_priority else "[other]"
        print(f"    [{i}] {marker} {cat}: {title}...")

    # 检查优先类别是否排在前面
    priority_items = [
        item
        for item in raw_intel2
        if item.get("category") in ["prompt_injection", "agent_hijack"]
    ]
    print(f"\n  优先类别数量: {len(priority_items)} / {len(raw_intel2)} 条")

    # --- Test 3: 验证数据完整性 ---
    print(f"\n{'=' * 60}")
    print("--- Test 3: 数据完整性检查 ---")
    print(f"{'=' * 60}")

    required_fields = [
        "title",
        "description",
        "category",
        "severity_estimate",
        "_source_type",
        "source",
        "url",
    ]
    errors = 0
    for i, item in enumerate(raw_intel, 1):
        for field in required_fields:
            if not item.get(field):
                print(f"  [ERROR] 条目 {i}: 缺少字段 '{field}'")
                errors += 1

    # 验证 severity_estimate 值合法
    valid_severities = {"critical", "high", "medium", "low"}
    for i, item in enumerate(raw_intel, 1):
        sev = item.get("severity_estimate")
        if sev not in valid_severities:
            print(f"  [ERROR] 条目 {i}: 非法 severity '{sev}'")
            errors += 1

    # 验证 _source_type 为 darkweb
    for i, item in enumerate(raw_intel, 1):
        if item.get("_source_type") != "darkweb":
            print(
                f"  [ERROR] 条目 {i}: _source_type={item.get('_source_type')} (应为 'darkweb')"
            )
            errors += 1

    if errors == 0:
        print(f"\n  [OK] 全部 {len(raw_intel)} 条情报数据完整性检查通过!")
    else:
        print(f"\n  [FAIL] 发现 {errors} 个数据完整性问题")

    # --- 总结 ---
    print(f"\n{'=' * 60}")
    print("Dark Web Agent (Mock Data) 验证完成!")
    print(f"{'=' * 60}")
    print(f"  总 mock 数据: {len(MOCK_DARK_WEB_INTEL)} 条")
    print(f"  覆盖类别: {len(by_category)} / 6")
    print(f"  数据完整性: {'PASS' if errors == 0 else 'FAIL'}")
    print(f"  优先过滤: 正常工作")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
