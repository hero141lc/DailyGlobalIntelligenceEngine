"""
美联储数据采集模块
优先官方，其次路透，最后媒体解读
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

def parse_entry(entry: feedparser.FeedParserDict, source_name: str, is_official: bool = False) -> Optional[Dict]:
    """
    解析 RSS 条目
    
    Args:
        entry: feedparser 条目
        source_name: 数据源名称
        is_official: 是否为官方来源
    
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
        
        # 过滤关键词：美联储、FOMC、利率、政策
        keywords = ["fed", "federal reserve", "fomc", "interest rate", 
                   "monetary policy", "jerome powell", "powell",
                   "美联储", "利率", "政策", "FOMC"]
        
        title_lower = title.lower()
        content_lower = (summary if summary else title).lower()
        
        if not any(keyword in title_lower or keyword in content_lower for keyword in keywords):
            return None
        
        # 提取内容
        content = summary if summary else title
        
        # 解析发布日期
        published_at = format_date_for_display(
            parse_date(published) or datetime.now(timezone.utc)
        )
        
        # 如果是官方来源，标记优先级
        if is_official:
            source_name = f"Federal Reserve (官方)"
        
        return {
            "category": "美联储",
            "title": title[:200] if len(title) > 200 else title,
            "content": content[:500] if len(content) > 500 else content,
            "source": source_name,
            "url": link,
            "published_at": published_at,
        }
    except Exception as e:
        logger.warning(f"解析条目失败: {e}")
        return None

def collect_fed_news() -> List[Dict]:
    """
    采集美联储相关新闻
    优先级：官方 > 路透 > 其他媒体
    
    Returns:
        新闻列表（已按优先级排序）
    """
    all_items: List[Dict] = []
    official_items: List[Dict] = []
    other_items: List[Dict] = []
    
    rss_sources = settings.RSS_SOURCES.get("fed", [])
    
    for rss_url in rss_sources:
        feed = fetch_rss(rss_url)
        if not feed or not feed.entries:
            continue
        
        # 判断是否为官方来源
        is_official = "federalreserve.gov" in rss_url
        
        feed_source = _source_name_from_url(rss_url)
        for entry in feed.entries[:settings.MAX_ITEMS_PER_SOURCE]:
            source_name = get_entry_source(entry, rss_url, feed_source)
            item = parse_entry(entry, source_name, is_official)
            if item:
                if is_official:
                    official_items.append(item)
                else:
                    other_items.append(item)
    
    # 优先官方，其次其他
    all_items = official_items + other_items
    
    logger.info(f"成功采集 {len(all_items)} 条美联储新闻（官方: {len(official_items)}, 其他: {len(other_items)}）")
    return all_items

def collect_all() -> List[Dict]:
    """
    采集所有美联储数据
    
    Returns:
        所有新闻列表
    """
    return collect_fed_news()

