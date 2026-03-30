"""
煤炭·电厂库存与日耗数据采集
从 config.settings.COAL_POWERPLANT_SOURCES 配置的 RSS 抓取电厂库存、日耗相关资讯。
"""
from typing import List, Dict, Optional

import feedparser

from config import settings
from utils.logger import logger
from utils.rss_fetcher import fetch_rss
from utils.time import get_today_date, parse_date, format_date_for_display


_POWERPLANT_KEYWORDS = ("煤", "煤炭", "电厂", "库存", "日耗", "沿海", "动力煤", "焦煤", "焦炭")

def _parse_entry(entry: feedparser.FeedParserDict, source_name: str) -> Optional[Dict]:
    """将 RSS 条目解析为标准数据项。"""
    try:
        title = (entry.get("title") or "").strip()
        link = entry.get("link", "")
        published = entry.get("published", "")
        summary = (entry.get("summary", "") or "").strip()
        content = summary or title
        combined = (title + " " + content).lower()
        if not any(kw in combined for kw in _POWERPLANT_KEYWORDS):
            return None
        published_at = get_today_date()
        if published:
            parsed = parse_date(published)
            if parsed:
                published_at = format_date_for_display(parsed)
        return {
            "category": "电厂库存",
            "title": title[:200] if len(title) > 200 else title,
            "content": (content[:500] + "…") if len(content) > 500 else content,
            "source": source_name,
            "url": link,
            "published_at": published_at,
        }
    except Exception as e:
        logger.debug("解析电厂库存条目失败: %s", e)
        return None


def collect_all() -> List[Dict]:
    """采集电厂库存/日耗相关资讯（RSS）。"""
    all_items: List[Dict] = []
    urls = getattr(settings, "COAL_POWERPLANT_SOURCES", None) or []
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
    logger.info("电厂库存：采集到 %d 条", len(all_items))
    return all_items
