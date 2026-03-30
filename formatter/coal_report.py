"""
煤炭模式报告生成器（预留）
输入煤炭各数据源聚合结果，输出《中国煤炭市场日报》风格 Markdown。
待实现：coal_port、coal_pit、coal_powerplant、coal_policy 等爬虫与数据格式约定。
"""
from typing import List, Dict, Any

from utils.time import get_today_date


def build_coal_report(items: List[Dict], **kwargs: Any) -> str:
    """
    预留：根据煤炭相关数据生成 Markdown 报告。
    当前无煤炭爬虫，返回占位文案。

    Args:
        items: 煤炭相关数据项（港口价、坑口价、电厂库存、政策等）
        **kwargs: 预留扩展字段

    Returns:
        Markdown 字符串
    """
    today = get_today_date()
    if not items:
        return (
            f"# 中国煤炭市场日报（{today}）\n\n"
            "> 港口煤价、产地坑口、电厂库存当前为占位数据源（返回 0 条）。"
            "政策与资讯已接入 RSS，若仍无数据可检查 COAL_POLICY_SOURCES。\n"
        )
    # 按 category 分组，顺序：港口煤价、产地坑口、电厂库存、煤炭政策
    order = ("港口煤价", "产地坑口", "电厂库存", "煤炭政策")
    grouped: Dict[str, List[Dict]] = {}
    for item in items:
        cat = item.get("category", "其他")
        grouped.setdefault(cat, []).append(item)
    lines = [f"# 中国煤炭市场日报（{today}）", ""]
    for cat in order:
        if cat not in grouped:
            continue
        lines.append(f"## {cat}")
        lines.append("")
        for item in grouped[cat]:
            title = item.get("title", "")
            content = item.get("content", "")
            url = item.get("url", "")
            if title:
                if url:
                    lines.append(f"- **[{title}]({url})**")
                else:
                    lines.append(f"- **{title}**")
            if content:
                lines.append(f"  {content}")
            lines.append("")
        lines.append("")
    for cat, group in grouped.items():
        if cat in order:
            continue
        lines.append(f"## {cat}")
        lines.append("")
        for item in group:
            title = item.get("title", "")
            if title:
                lines.append(f"- {title}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"
