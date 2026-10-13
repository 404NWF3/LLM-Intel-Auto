#!/usr/bin/env python3
"""
测试 VirusTotal API 查询功能。

验证 VirusTotal API 集成。需要 VIRUSTOTAL_API_KEY 环境变量。
"""

import json
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from saads.tools.api_tools import _query_virustotal_impl
from saads.config import VIRUSTOTAL_API_KEY


def test_virustotal_query():
    """测试 VirusTotal 查询功能。"""
    print("=" * 80)
    print("测试 VirusTotal API 查询")
    print("=" * 80)

    # 检查 API Key
    if not VIRUSTOTAL_API_KEY:
        print("\n⚠️  警告: 未设置 VIRUSTOTAL_API_KEY 环境变量")
        print("   请在 .env 文件中添加:")
        print("   VIRUSTOTAL_API_KEY=your-api-key-here")
        print("\n   获取免费 API Key: https://www.virustotal.com/gui/join-us")
        return

    # 测试 URL 查询（使用已知的恶意 URL 示例）
    test_cases = [
        ("http://www.eicar.org/download/eicar.com.txt", "url"),
        ("http://malware.testing.google.test/testing/malware/", "url"),
    ]

    for resource, resource_type in test_cases:
        print(f"\n{'=' * 80}")
        print(f"查询 {resource_type.upper()}: {resource}")
        print("=" * 80)

        result = _query_virustotal_impl(resource, resource_type)

        # 检查是否返回错误
        if result.startswith("Error"):
            print(f"❌ 错误: {result}")
            continue

        # 解析 JSON 结果
        try:
            data = json.loads(result)

            if "error" in data:
                print(f"⚠️  API 配置问题: {data.get('error')}")
                print(f"   提示: {data.get('note', '')}")
                continue

            print(f"✅ 查询成功\n")
            print(f"📊 扫描结果:")
            print(f"  资源: {data.get('resource', 'N/A')}")
            print(f"  扫描日期: {data.get('scan_date', 'N/A')}")
            print(f"  检出数/总数: {data.get('positives', 0)}/{data.get('total', 0)}")
            print(f"  报告链接: {data.get('permalink', 'N/A')}")

            positives = data.get("positives", 0)
            if positives > 0:
                print(f"  ⚠️  检测到恶意特征: {positives} 个引擎标记为威胁")
            else:
                print(f"  ✅ 未检测到恶意特征")

        except json.JSONDecodeError as e:
            print(f"❌ JSON 解析失败: {e}")
            print(f"原始响应: {result[:500]}")


def main():
    """主函数。"""
    print("\n🚀 开始测试 VirusTotal API\n")

    test_virustotal_query()

    print("\n" + "=" * 80)
    print("✅ VirusTotal API 测试完成")
    print("=" * 80)


if __name__ == "__main__":
    main()
