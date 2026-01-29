"""
从 RSS 条目中解析真实来源名称
解决 Google News 等聚合源把所有条目错误标成「Reuters」的问题
"""
from typing import Optional

try:
    import feedparser
    FeedParserDict = feedparser.FeedParserDict
except Exception:
    FeedParserDict = dict  # type: ignore


def get_entry_source(entry: "FeedParserDict", rss_url: str, fallback: str) -> str:
    """
    从条目中解析真实来源名称。
    Google News RSS 的标题格式多为：「标题 - 来源名」，例如
    "Live coverage: SpaceX to launch... - Spaceflight Now"

    Args:
        entry: feedparser 解析的条目
        rss_url: 当前 RSS 的 URL，用于判断是否为聚合源
        fallback: 无法解析时使用的默认来源名

    Returns:
        来源名称字符串
    """
    # 仅对 Google News 聚合源做解析，其它 RSS 用原有逻辑
    if "news.google.com" not in (rss_url or ""):
        return fallback

    title = (entry.get("title") or "").strip()
    # 标题末尾常见格式："... - Source Name" 或 "... – Source Name"（en dash）
    if not title:
        return fallback

    # 尝试 Atom/RSS 的 source 元素（若有）
    source_elem = entry.get("source")
    if source_elem:
        if isinstance(source_elem, dict) and source_elem.get("title"):
            return (source_elem.get("title") or "").strip() or fallback
        if isinstance(source_elem, str) and source_elem.strip():
            return source_elem.strip()

    # 用 " - " 或 " – " 从标题末尾截取来源
    for sep in [" - ", " – ", " — "]:
        if sep in title:
            parts = title.split(sep)
            if len(parts) >= 2:
                candidate = parts[-1].strip()
                # 避免把过长的或带 URL 的当作来源
                if candidate and len(candidate) < 80 and "http" not in candidate:
                    return candidate

    return fallback
