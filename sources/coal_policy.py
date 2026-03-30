"""
煤炭·政策与资讯数据采集
从 config.settings.COAL_POLICY_SOURCES 配置的 RSS/URL 抓取煤炭相关政策与资讯。
默认使用 Google News RSS（中国+煤炭+政策），可改为其他 RSS 或网页。
"""
from typing import List, Dict, Optional

import feedparser

from config import settings
from utils.logger import logger
from utils.rss_fetcher import fetch_rss
from utils.time import get_today_date, parse_date, format_date_for_display

try:
    from utils.source_from_entry import get_entry_source
except Exception:
    def get_entry_source(entry, url: str, fallback: str) -> str:
        return fallback

_POLICY_KEYWORDS = ("煤", "煤炭", "能源", "发改委", "政策", "安检", "产能", "动力煤", "焦煤")

def _parse_entry(entry: feedparser.FeedParserDict, source_name: str) -> Optional[Dict]:
    """将 RSS 条目解析为标准数据项。"""
    try:
        title = (entry.get("title") or "").strip()
        link = entry.get("link", "")
        published = entry.get("published", "")
        summary = (entry.get("summary", "") or "").strip()
        content = summary or title
        # 通用 RSS 需过滤
        combined = (title + " " + content).lower()
        if not any(kw in combined for kw in _POLICY_KEYWORDS):
            return None
        published_at = get_today_date()
        if published:
            parsed = parse_date(published)
            if parsed:
                published_at = format_date_for_display(parsed)
        return {
            "category": "煤炭政策",
            "title": title[:200] if len(title) > 200 else title,
            "content": (content[:500] + "…") if len(content) > 500 else content,
            "source": source_name,
            "url": link,
            "published_at": published_at,
        }
    except Exception as e:
        logger.debug("解析煤炭政策条目失败: %s", e)
        return None


def collect_all() -> List[Dict]:
    """
    采集煤炭政策与资讯（RSS）。
    从 settings.COAL_POLICY_SOURCES 读取 URL，支持 RSS；非 RSS 需在扩展中实现。
    """
    all_items: List[Dict] = []
    urls = getattr(settings, "COAL_POLICY_SOURCES", None) or []
    urls = [u.strip() for u in urls if u and str(u).strip()]
    max_items = getattr(settings, "MAX_ITEMS_PER_SOURCE", 20)

    for rss_url in urls:
        feed = fetch_rss(rss_url)
        if not feed or not getattr(feed, "entries", None):
            continue
        source_name = "Google News" if "google.com" in rss_url else ("新浪财经" if "sina.com" in rss_url else "RSS")
        for entry in feed.entries[:max_items]:
            item = _parse_entry(entry, source_name)
            if item and item.get("title"):
                all_items.append(item)
    logger.info("煤炭政策/资讯：采集到 %d 条", len(all_items))
    return all_items
