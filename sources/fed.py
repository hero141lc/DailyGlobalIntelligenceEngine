"""
美联储数据采集模块
优先官方，其次路透，最后媒体解读
"""
import feedparser
import requests
from typing import List, Dict, Optional
from datetime import datetime, timezone

from config import settings
from utils.logger import logger
from utils.time import is_today, format_date_for_display, parse_date
from utils.source_from_entry import get_entry_source

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
        # 添加延迟，避免限流
        import time
        time.sleep(1)
        
        response = requests.get(url, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        
        # 429 错误不重试
        if response.status_code == 429:
            logger.warning(f"RSS 源限流 {url}，跳过")
            return None
        
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        return feed
    except Exception as e:
        logger.warning(f"获取 RSS 失败 {url}: {e}")
        return None

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
        
        # 确定该 feed 的默认数据源名称
        feed_source = "Reuters"
        if "federalreserve.gov" in rss_url:
            feed_source = "Federal Reserve"
        elif "reuters" in rss_url:
            feed_source = "Reuters"
        
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

