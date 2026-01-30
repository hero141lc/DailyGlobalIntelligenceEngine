"""
能源/电力数据采集模块
"""
from typing import List, Dict, Optional
from datetime import datetime, timezone

import feedparser

from config import settings
from utils.logger import logger
from utils.time import is_today, format_date_for_display, parse_date
from utils.source_from_entry import get_entry_source
from utils.rss_fetcher import fetch_rss

try:
    from sources.rss_extra import _source_name_from_url
except Exception:
    def _source_name_from_url(url: str) -> str:
        return "RSS"

def parse_entry(entry: feedparser.FeedParserDict, source_name: str) -> Optional[Dict]:
    """
    解析 RSS 条目
    
    Args:
        entry: feedparser 条目
        source_name: 数据源名称
    
    Returns:
        标准格式的数据字典，解析失败返回 None
    """
    try:
        title = entry.get("title", "").strip()
        link = entry.get("link", "")
        published = entry.get("published", "")
        summary = entry.get("summary", "").strip()
        
        # 检查是否为今天的新闻
        if not is_today(published):
            return None
        
        # 提取内容
        content = summary if summary else title
        
        # 过滤关键词：电价、能源、电力、供应、政策
        keywords = ["energy", "power", "electricity", "price", "supply", 
                   "能源", "电力", "电价", "供应", "政策", "energy price",
                   "power price", "electricity price"]
        
        title_lower = title.lower()
        content_lower = content.lower()
        
        if not any(keyword in title_lower or keyword in content_lower for keyword in keywords):
            return None
        
        # 解析发布日期
        published_at = format_date_for_display(
            parse_date(published) or datetime.now(timezone.utc)
        )
        
        return {
            "category": "能源/电力",
            "title": title[:200] if len(title) > 200 else title,
            "content": content[:500] if len(content) > 500 else content,
            "source": source_name,
            "url": link,
            "published_at": published_at,
        }
    except Exception as e:
        logger.warning(f"解析条目失败: {e}")
        return None

def collect_energy_news() -> List[Dict]:
    """
    采集能源/电力相关新闻
    
    Returns:
        新闻列表
    """
    all_items: List[Dict] = []
    
    rss_sources = settings.RSS_SOURCES.get("energy", [])
    
    for rss_url in rss_sources:
        feed = fetch_rss(rss_url)
        if not feed or not feed.entries:
            continue
        
        feed_source = _source_name_from_url(rss_url)
        for entry in feed.entries[:settings.MAX_ITEMS_PER_SOURCE]:
            source_name = get_entry_source(entry, rss_url, feed_source)
            item = parse_entry(entry, source_name)
            if item:
                all_items.append(item)
    
    logger.info(f"成功采集 {len(all_items)} 条能源/电力新闻")
    return all_items

def collect_all() -> List[Dict]:
    """
    采集所有能源/电力数据
    
    Returns:
        所有新闻列表
    """
    return collect_energy_news()

