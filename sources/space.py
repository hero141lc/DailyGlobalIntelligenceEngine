"""
商业航天数据采集模块
关注 SpaceX、Starlink、发射、合同等
"""
import feedparser
import requests
from typing import List, Dict, Optional
from datetime import datetime, timezone

from config import settings
from utils.logger import logger
from utils.time import is_today, format_date_for_display, parse_date

def fetch_rss(url: str, timeout: int = 15) -> Optional[feedparser.FeedParserDict]:
    """
    获取 RSS 源
    
    Args:
        url: RSS URL
        timeout: 请求超时时间（秒）
    
    Returns:
        feedparser 解析结果，失败返回 None
    """
    try:
        # 添加延迟和更好的 User-Agent，避免限流
        import time
        time.sleep(2)  # 避免 429 错误
        
        response = requests.get(url, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        
        # 429 错误不重试，直接返回 None
        if response.status_code == 429:
            logger.warning(f"RSS 源限流 {url}，跳过")
            return None
        
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        return feed
    except Exception as e:
        logger.warning(f"获取 RSS 失败 {url}: {e}")
        return None

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
        
        # 过滤关键词：SpaceX、Starlink、发射、合同、商业航天
        keywords = ["spacex", "starlink", "launch", "contract", "aerospace",
                   "commercial space", "satellite", "rocket", "space",
                   "发射", "合同", "商业航天", "卫星", "火箭"]
        
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
        
        return {
            "category": "商业航天/星链",
            "title": title[:200] if len(title) > 200 else title,
            "content": content[:500] if len(content) > 500 else content,
            "source": source_name,
            "url": link,
            "published_at": published_at,
        }
    except Exception as e:
        logger.warning(f"解析条目失败: {e}")
        return None

def collect_space_news() -> List[Dict]:
    """
    采集商业航天相关新闻
    
    Returns:
        新闻列表
    """
    all_items: List[Dict] = []
    
    rss_sources = settings.RSS_SOURCES.get("space", [])
    
    for rss_url in rss_sources:
        feed = fetch_rss(rss_url)
        if not feed or not feed.entries:
            continue
        
        # 确定数据源名称
        source_name = "Reuters"
        if "spacenews" in rss_url:
            source_name = "SpaceNews"
        elif "reuters" in rss_url:
            source_name = "Reuters"
        
        for entry in feed.entries[:settings.MAX_ITEMS_PER_SOURCE]:
            item = parse_entry(entry, source_name)
            if item:
                all_items.append(item)
    
    logger.info(f"成功采集 {len(all_items)} 条商业航天新闻")
    return all_items

def collect_all() -> List[Dict]:
    """
    采集所有商业航天数据
    
    Returns:
        所有新闻列表
    """
    return collect_space_news()

