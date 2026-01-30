"""
黄金、石油、军事数据采集模块
通过 RSS（如 Google News）采集
"""
from typing import List, Dict, Optional
from datetime import datetime, timezone

import feedparser

from config import settings
from utils.logger import logger
from utils.time import is_today, is_today_or_yesterday, format_date_for_display, parse_date
from utils.source_from_entry import get_entry_source
from utils.rss_fetcher import fetch_rss

try:
    from sources.rss_extra import _source_name_from_url
except Exception:
    def _source_name_from_url(url: str) -> str:
        return "RSS"

# 各板块关键词与类别
_CATEGORY_CONFIG = {
    "gold": {
        "category": "黄金",
        "keywords": ["gold", "precious metal", "bullion", "黄金", "金价", "贵金属", "mining", "copper"],
    },
    "oil": {
        "category": "石油",
        "keywords": ["oil", "crude", "wti", "brent", "石油", "油价", "原油"],
    },
    "military": {
        "category": "军事",
        "keywords": ["military", "defense", "pentagon", "ukraine", "nato", "army", "军事", "国防", "北约", "乌克兰"],
    },
}


def _parse_entry(
    entry: feedparser.FeedParserDict,
    source_name: str,
    category: str,
    keywords: List[str],
) -> Optional[Dict]:
    try:
        title = entry.get("title", "").strip()
        link = entry.get("link", "")
        published = entry.get("published", "")
        summary = entry.get("summary", "").strip()
        # 黄金用「今天」；石油/军事用「今天或昨天」以减少时区导致的 0 条
        if category == "黄金":
            if not is_today(published):
                return None
        else:
            if not is_today_or_yesterday(published):
                return None
        title_lower = title.lower()
        content_lower = (summary if summary else title).lower()
        if not any(kw in title_lower or kw in content_lower for kw in keywords):
            return None
        content = summary if summary else title
        published_at = format_date_for_display(
            parse_date(published) or datetime.now(timezone.utc)
        )
        return {
            "category": category,
            "title": title[:200] if len(title) > 200 else title,
            "content": content[:500] if len(content) > 500 else content,
            "source": source_name,
            "url": link,
            "published_at": published_at,
        }
    except Exception as e:
        logger.warning(f"解析条目失败: {e}")
        return None


def _collect_key(key: str) -> List[Dict]:
    items: List[Dict] = []
    config = _CATEGORY_CONFIG.get(key)
    if not config:
        return items
    urls = settings.RSS_SOURCES.get(key, [])
    category = config["category"]
    keywords = config["keywords"]
    for rss_url in urls:
        feed = fetch_rss(rss_url)
        if not feed or not feed.entries:
            continue
        feed_source = _source_name_from_url(rss_url)
        for entry in feed.entries[:settings.MAX_ITEMS_PER_SOURCE]:
            source_name = get_entry_source(entry, rss_url, feed_source)
            item = _parse_entry(entry, source_name, category, keywords)
            if item:
                items.append(item)
    return items


def collect_all() -> List[Dict]:
    all_items: List[Dict] = []
    for key in ("gold", "oil", "military"):
        try:
            items = _collect_key(key)
            all_items.extend(items)
            logger.info(f"成功采集 {len(items)} 条 {_CATEGORY_CONFIG[key]['category']} 相关")
        except Exception as e:
            logger.error(f"采集 {key} 失败: {e}")
    return all_items
