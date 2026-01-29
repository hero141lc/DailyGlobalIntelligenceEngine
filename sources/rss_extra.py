"""
美股快讯、SEC 监管等 RSS 采集（CNBC、MarketWatch、Seeking Alpha、SEC）
"""
import time
import feedparser
import requests
from typing import List, Dict, Optional
from datetime import datetime, timezone

from config import settings
from utils.logger import logger
from utils.time import is_today, format_date_for_display, parse_date
from utils.source_from_entry import get_entry_source


def fetch_rss(url: str, timeout: int = 15, max_retries: int = 3) -> Optional[feedparser.FeedParserDict]:
    """获取 RSS；失败时重试 max_retries 次（含 SEC 等偶发失败）。"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            time.sleep(1)
            response = requests.get(url, timeout=timeout, headers=headers)
            if response.status_code == 429:
                logger.warning(f"RSS 源限流 {url}，跳过")
                return None
            response.raise_for_status()
            return feedparser.parse(response.content)
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(2 * attempt)
                logger.warning(f"获取 RSS 失败 {url} (第 {attempt}/{max_retries} 次): {e}，重试中")
            else:
                logger.warning(f"获取 RSS 失败 {url}: {e}")
    return None


def _source_name_from_url(url: str) -> str:
    if not url:
        return "RSS"
    url_lower = url.lower()
    if "cnbc" in url_lower:
        return "CNBC"
    if "marketwatch" in url_lower or "dowjones" in url_lower:
        return "MarketWatch"
    if "seekingalpha" in url_lower:
        return "Seeking Alpha"
    if "sec.gov" in url_lower:
        return "SEC"
    return "RSS"


def _collect_rss_key(key: str, category: str) -> List[Dict]:
    items: List[Dict] = []
    urls = settings.RSS_SOURCES.get(key, [])
    for rss_url in urls:
        feed = fetch_rss(rss_url)
        if not feed or not feed.entries:
            continue
        default_source = _source_name_from_url(rss_url)
        for entry in feed.entries[:settings.MAX_ITEMS_PER_SOURCE]:
            try:
                title = entry.get("title", "").strip()
                link = entry.get("link", "")
                published = entry.get("published", "")
                summary = entry.get("summary", "").strip()
                if not is_today(published):
                    continue
                content = summary if summary else title
                source_name = get_entry_source(entry, rss_url, default_source)
                published_at = format_date_for_display(
                    parse_date(published) or datetime.now(timezone.utc)
                )
                items.append({
                    "category": category,
                    "title": title[:200] if len(title) > 200 else title,
                    "content": content[:500] if len(content) > 500 else content,
                    "source": source_name,
                    "url": link,
                    "published_at": published_at,
                })
            except Exception as e:
                logger.warning(f"解析条目失败: {e}")
    return items


def collect_all() -> List[Dict]:
    all_items: List[Dict] = []
    # 美股快讯（CNBC、MarketWatch、Seeking Alpha）
    try:
        stocks_items = _collect_rss_key("stocks", "美股快讯")
        all_items.extend(stocks_items)
        logger.info(f"成功采集 {len(stocks_items)} 条美股快讯")
    except Exception as e:
        logger.error(f"采集美股快讯失败: {e}")
    # SEC 监管（特斯拉等）
    try:
        sec_items = _collect_rss_key("sec_filings", "SEC监管")
        all_items.extend(sec_items)
        logger.info(f"成功采集 {len(sec_items)} 条 SEC 监管")
    except Exception as e:
        logger.error(f"采集 SEC 监管失败: {e}")
    return all_items
