"""
能源/电力数据采集模块
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
        
        # 确定该 feed 的默认数据源名称
        feed_source = "Reuters"
        if "eia.gov" in rss_url:
            feed_source = "EIA"
        elif "reuters" in rss_url:
            feed_source = "Reuters"
        
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

