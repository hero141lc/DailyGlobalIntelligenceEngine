"""
股票模式报告生成器
输出 Markdown，适用于企业微信/飞书等（指数 + 涨跌 + 简析）
"""
from typing import List, Dict, Optional

from utils.time import get_today_date


def build_stock_report(
    items: List[Dict],
    stock_analysis: Optional[str] = None,
) -> str:
    """
    根据采集的股票相关条目生成 Markdown 报告。

    Args:
        items: 处理后的数据项（含美股市场、大涨个股、今日涨跌、美股快讯等）
        stock_analysis: 可选，LLM 生成的股票简析

    Returns:
        Markdown 字符串
    """
    today = get_today_date()
    lines = [
        f"# 美股市场日报（{today}）",
        "",
    ]
    indices = [i for i in items if i.get("category") == "美股市场"]
    surge = [i for i in items if i.get("category") == "大涨个股"]
    movers = [i for i in items if i.get("category") == "今日涨跌"]
    news = [i for i in items if i.get("category") in ("美股快讯", "SEC监管")]

    if indices:
        lines.append("## 主要指数")
        lines.append("")
        for item in indices:
            title = item.get("title", "")
            lines.append(f"- {title}")
        lines.append("")
    if surge:
        lines.append("## 大涨个股")
        lines.append("")
        for item in surge[:15]:
            title = item.get("title", "")
            url = item.get("url", "")
            if url:
                lines.append(f"- [{title}]({url})")
            else:
                lines.append(f"- {title}")
        if len(surge) > 15:
            lines.append(f"- _…共 {len(surge)} 条_")
        lines.append("")
    if movers:
        lines.append("## 今日涨跌一览")
        lines.append("")
        for item in movers[:12]:
            title = item.get("title", "")
            url = item.get("url", "")
            if url:
                lines.append(f"- [{title}]({url})")
            else:
                lines.append(f"- {title}")
        if len(movers) > 12:
            lines.append(f"- _…共 {len(movers)} 条_")
        lines.append("")
    if stock_analysis and stock_analysis.strip():
        lines.append("## AI 简析")
        lines.append("")
        lines.append(stock_analysis.strip())
        lines.append("")
    if news:
        lines.append("## 快讯与监管")
        lines.append("")
        for item in news[:10]:
            title = item.get("title", "")
            url = item.get("url", "")
            summary = (item.get("summary") or item.get("content", ""))[:80]
            if url:
                lines.append(f"- **{title}** [链接]({url})")
            else:
                lines.append(f"- **{title}**")
            if summary:
                lines.append(f"  {summary}…")
        if len(news) > 10:
            lines.append(f"- _…共 {len(news)} 条_")
    return "\n".join(lines).strip() + "\n"
