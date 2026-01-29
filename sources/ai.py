"""
AI 应用数据采集模块
关注产品化和商业化，排除纯论文
"""
import feedparser
import requests
from typing import List, Dict, Optional
from datetime import datetime, timezone

from config import settings
from utils.logger import logger
from utils.time import is_today, format_date_for_display, parse_date

try:
    from sources.rss_extra import _source_name_from_url
except Exception:
    def _source_name_from_url(url: str) -> str:
        return "RSS"

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

def fetch_hn_api() -> List[Dict]:
    """
    通过 Hacker News API 获取热门 AI 相关文章
    
    Returns:
        文章列表
    """
    items: List[Dict] = []
    
    try:
        # 获取热门文章 ID
        response = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            timeout=10
        )
        response.raise_for_status()
        story_ids = response.json()[:30]  # 取前30个
        
        # 获取每篇文章详情
        for story_id in story_ids:
            try:
                story_response = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                    timeout=5
                )
                story_response.raise_for_status()
                story = story_response.json()
                
                if not story or story.get("type") != "story":
                    continue
                
                title = story.get("title", "").lower()
                url = story.get("url", "")
                
                # 过滤 AI 相关关键词
                ai_keywords = ["ai", "artificial intelligence", "llm", "gpt", 
                             "openai", "anthropic", "claude", "chatgpt",
                             "machine learning", "deep learning", "neural"]
                
                if not any(keyword in title for keyword in ai_keywords):
                    continue
                
                # 排除论文相关
                if any(word in title for word in ["paper", "arxiv", "research paper", "论文"]):
                    continue
                
                # 检查时间（HN 使用 Unix 时间戳）
                time_stamp = story.get("time", 0)
                if time_stamp:
                    story_date = datetime.fromtimestamp(time_stamp, tz=timezone.utc)
                    if not is_today(story_date.strftime("%Y-%m-%d")):
                        continue
                
                items.append({
                    "category": "AI 应用",
                    "title": story.get("title", "")[:200],
                    "content": story.get("title", ""),
                    "source": "Hacker News",
                    "url": url or f"https://news.ycombinator.com/item?id={story_id}",
                    "published_at": format_date_for_display(story_date) if time_stamp else datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                })
            except Exception as e:
                logger.debug(f"获取 HN 文章 {story_id} 失败: {e}")
                continue
    except Exception as e:
        logger.warning(f"获取 Hacker News 数据失败: {e}")
    
    return items

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
        
        # 排除论文相关
        title_lower = title.lower()
        if any(word in title_lower for word in ["paper", "arxiv", "research paper", "论文", "preprint"]):
            return None
        
        # 过滤 AI 相关关键词
        ai_keywords = ["ai", "artificial intelligence", "llm", "gpt", 
                      "openai", "anthropic", "claude", "chatgpt",
                      "machine learning", "deep learning", "neural",
                      "product", "launch", "release", "announce"]
        
        title_lower = title.lower()
        summary_lower = summary.lower() if summary else ""
        
        if not any(keyword in title_lower or keyword in summary_lower for keyword in ai_keywords):
            return None
        
        # 提取内容
        content = summary if summary else title
        
        # 解析发布日期
        published_at = format_date_for_display(
            parse_date(published) or datetime.now(timezone.utc)
        )
        
        return {
            "category": "AI 应用",
            "title": title[:200] if len(title) > 200 else title,
            "content": content[:500] if len(content) > 500 else content,
            "source": source_name,
            "url": link,
            "published_at": published_at,
        }
    except Exception as e:
        logger.warning(f"解析条目失败: {e}")
        return None

def collect_ai_news() -> List[Dict]:
    """
    采集 AI 应用相关新闻
    
    Returns:
        新闻列表
    """
    all_items: List[Dict] = []
    
    # 从 RSS 源采集
    rss_sources = settings.RSS_SOURCES.get("ai", [])
    
    for rss_url in rss_sources:
        if "hnrss" in rss_url:
            # Hacker News 使用 API
            continue
        
        feed = fetch_rss(rss_url)
        if not feed or not feed.entries:
            continue
        
        source_name = _source_name_from_url(rss_url)
        for entry in feed.entries[:settings.MAX_ITEMS_PER_SOURCE]:
            item = parse_entry(entry, source_name)
            if item:
                all_items.append(item)
    
    # 从 Hacker News API 采集
    try:
        hn_items = fetch_hn_api()
        all_items.extend(hn_items)
    except Exception as e:
        logger.warning(f"采集 Hacker News 数据失败: {e}")
    
    logger.info(f"成功采集 {len(all_items)} 条 AI 应用新闻")
    return all_items

def collect_all() -> List[Dict]:
    """
    采集所有 AI 应用数据
    
    Returns:
        所有新闻列表
    """
    return collect_ai_news()

