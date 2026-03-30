#!/usr/bin/env python
"""
数据源可用性测试脚本
运行：在项目根目录执行  python scripts/test_sources.py
"""
import sys
import os

# 保证项目根在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_coal_sources():
    """测试煤炭模式四个数据源。"""
    print("=" * 50)
    print("煤炭数据源 (REPORT_MODE=coal)")
    print("=" * 50)
    from sources.coal_port import collect_all as coal_port
    from sources.coal_pit import collect_all as coal_pit
    from sources.coal_powerplant import collect_all as coal_powerplant
    from sources.coal_policy import collect_all as coal_policy

    for name, fn in [
        ("coal_port (港口煤价)", coal_port),
        ("coal_pit (产地坑口)", coal_pit),
        ("coal_powerplant (电厂库存)", coal_powerplant),
        ("coal_policy (政策/资讯 RSS)", coal_policy),
    ]:
        try:
            items = fn()
            status = "OK" if items is not None else "FAIL"
            print(f"  {name}: {len(items)} 条 [{status}]")
            if items and len(items) > 0:
                first = items[0]
                title = (first.get("title") or "")[:48]
                print(f"    首条: {title}...")
        except Exception as e:
            print(f"  {name}: 异常 - {e}")
    print()


def test_stock_sources():
    """测试股票模式数据源（需网络，可能较慢）。"""
    print("=" * 50)
    print("股票模式数据源 (REPORT_MODE=stock)")
    print("=" * 50)
    try:
        from sources.stocks import collect_all as stocks
        items = stocks()
        print(f"  stocks (指数+个股): {len(items)} 条 [OK]")
        if items:
            for i, item in enumerate(items[:3]):
                print(f"    [{i+1}] {item.get('category')} {item.get('title', '')[:40]}")
    except Exception as e:
        print(f"  stocks: 异常 - {e}")
    try:
        from sources.rss_extra import collect_all as rss_extra
        items = rss_extra()
        print(f"  rss_extra (美股快讯/SEC): {len(items)} 条 [OK]")
    except Exception as e:
        print(f"  rss_extra: 异常 - {e}")
    try:
        from sources.fed import collect_all as fed
        items = fed()
        print(f"  fed (美联储): {len(items)} 条 [OK]")
    except Exception as e:
        print(f"  fed: 异常 - {e}")
    print()


def main():
    print("\n数据源可用性测试\n")
    test_coal_sources()
    test_stock_sources()
    print("测试结束。")


if __name__ == "__main__":
    main()
