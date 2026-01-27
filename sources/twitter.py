"""
Twitter 数据采集模块
通过 Nitter RSS 采集马斯克和特朗普的推文
"""
import feedparser
import requests
from typing import List, Dict, Optional
from datetime import datetime, timezone

from config import settings
from utils.logger import logger
from utils.time import is_today, format_date_for_display

def fetch_nitter_rss(url: str, timeout: int = 10) -> Optional[feedparser.FeedParserDict]:
    """
    获取 Nitter RSS 源
    
    Args:
        url: RSS URL
        timeout: 请求超时时间（秒）
    
    Returns:
        feedparser 解析结果，失败返回 None
    """
    try:
        response = requests.get(url, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0 (compatible; DGIE/1.0)"
        })
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        return feed
    except Exception as e:
        logger.warning(f"获取 Nitter RSS 失败 {url}: {e}")
        return None

def parse_tweet_entry(entry: feedparser.FeedParserDict, username: str) -> Optional[Dict]:
    """
    解析单条推文条目
    
    Args:
        entry: feedparser 条目
        username: 用户名（用于分类）
    
    Returns:
        标准格式的数据字典，解析失败返回 None
    """
    try:
        # 提取基本信息
        title = entry.get("title", "").strip()
        link = entry.get("link", "")
        published = entry.get("published", "")
        
        # 检查是否为今天的推文
        if not is_today(published):
            return None
        
        # 提取推文内容（去除标题中的用户名前缀）
        content = title
        if ":" in content:
            content = content.split(":", 1)[1].strip()
        
        # 确定分类
        if "elon" in username.lower() or "musk" in username.lower():
            category = "马斯克"
            source_name = "X / Elon Musk"
        elif "trump" in username.lower() or "donald" in username.lower():
            category = "特朗普"
            source_name = "X / Donald Trump"
        else:
            category = "Twitter"
            source_name = f"X / {username}"
        
        return {
            "category": category,
            "title": content[:200] if len(content) > 200 else content,
            "content": content,
            "source": source_name,
            "url": link,
            "published_at": format_date_for_display(
                datetime.now(timezone.utc)
            ) if published else datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }
    except Exception as e:
        logger.warning(f"解析推文条目失败: {e}")
        return None

def fetch_tweets(username: str, max_items: int = 5) -> List[Dict]:
    """
    获取指定用户的最新推文
    
    Args:
        username: Twitter 用户名
        max_items: 最大获取数量
    
    Returns:
        推文列表（标准格式）
    """
    tweets: List[Dict] = []
    
    # 尝试多个 Nitter 实例
    rss_urls = []
    if "elon" in username.lower() or "musk" in username.lower():
        rss_urls = settings.RSS_SOURCES.get("twitter_elon", [])
    elif "trump" in username.lower() or "donald" in username.lower():
        rss_urls = settings.RSS_SOURCES.get("twitter_trump", [])
    
    if not rss_urls:
        # 默认使用第一个 Nitter 实例
        base_url = settings.NITTER_INSTANCES[0]
        rss_urls = [f"{base_url}/{username}/rss"]
    
    for rss_url in rss_urls:
        if len(tweets) >= max_items:
            break
        
        feed = fetch_nitter_rss(rss_url)
        if not feed or not feed.entries:
            continue
        
        for entry in feed.entries[:max_items]:
            if len(tweets) >= max_items:
                break
            
            tweet = parse_tweet_entry(entry, username)
            if tweet:
                tweets.append(tweet)
        
        # 如果成功获取到数据，不再尝试其他实例
        if tweets:
            break
    
    logger.info(f"成功获取 {username} 的 {len(tweets)} 条推文")
    return tweets[:max_items]

def collect_musk_tweets() -> List[Dict]:
    """
    采集马斯克的推文
    
    Returns:
        推文列表
    """
    return fetch_tweets("elonmusk", settings.MAX_TWEETS_PER_USER)

def collect_trump_tweets() -> List[Dict]:
    """
    采集特朗普的推文
    
    Returns:
        推文列表
    """
    return fetch_tweets("realDonaldTrump", settings.MAX_TWEETS_PER_USER)

def collect_all() -> List[Dict]:
    """
    采集所有 Twitter 数据
    
    Returns:
        所有推文列表
    """
    all_tweets: List[Dict] = []
    
    # 采集马斯克推文
    try:
        all_tweets.extend(collect_musk_tweets())
    except Exception as e:
        logger.error(f"采集马斯克推文失败: {e}")
    
    # 采集特朗普推文
    try:
        all_tweets.extend(collect_trump_tweets())
    except Exception as e:
        logger.error(f"采集特朗普推文失败: {e}")
    
    return all_tweets

