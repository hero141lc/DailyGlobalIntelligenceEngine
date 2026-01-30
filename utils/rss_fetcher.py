"""
共享 RSS 获取模块
统一请求头、限流与重试逻辑，供各数据源复用。
"""
import time
from typing import Optional, List, Dict, Callable, Any

import feedparser
import requests

from utils.logger import logger

# 类型：feedparser 解析结果
FeedParserDict = feedparser.FeedParserDict

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def fetch_rss(
    url: str,
    timeout: int = 15,
    max_retries: int = 3,
    delay: float = 1.0,
    headers: Optional[Dict[str, str]] = None,
) -> Optional[FeedParserDict]:
    """
    获取 RSS 源（统一实现：限流不重试、失败可重试）。

    Args:
        url: RSS URL
        timeout: 请求超时（秒）
        max_retries: 失败时重试次数
        delay: 每次请求前等待秒数，避免限流
        headers: 请求头，默认使用 DEFAULT_HEADERS

    Returns:
        feedparser 解析结果，失败返回 None
    """
    h = dict(headers or DEFAULT_HEADERS)
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            time.sleep(delay)
            response = requests.get(url, timeout=timeout, headers=h)
            if response.status_code == 429:
                logger.warning(f"RSS 源限流 {url}，跳过")
                return None
            response.raise_for_status()
            return feedparser.parse(response.content)
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                wait = min(2 * attempt, 15)
                logger.warning(f"获取 RSS 失败 {url} (第 {attempt}/{max_retries} 次): {e}，{wait}s 后重试")
                time.sleep(wait)
            else:
                logger.warning(f"获取 RSS 失败 {url}: {e}")
    return None


class RSSCollector:
    """
    基于 RSS URL 列表的通用采集器：拉取 feed、遍历条目、用调用方提供的解析函数生成标准条目。
    各源只需实现 parse_entry(entry, source_name) 并传入，减少重复的 fetch/循环代码。
    """

    def __init__(
        self,
        urls: List[str],
        max_items_per_source: int = 20,
        fetch_delay: float = 1.0,
    ):
        self.urls = urls
        self.max_items_per_source = max_items_per_source
        self.fetch_delay = fetch_delay

    def collect(
        self,
        parse_entry_fn: Callable[..., Optional[Dict[str, Any]]],
        default_source_from_url: Callable[[str], str],
    ) -> List[Dict[str, Any]]:
        """
        对每个 URL 拉取 feed，对每条 entry 用 get_entry_source 解析来源名后调用 parse_entry_fn。

        Args:
            parse_entry_fn: (entry, source_name) -> item or None
            default_source_from_url: (rss_url) -> default_source

        Returns:
            标准格式条目列表
        """
        from utils.source_from_entry import get_entry_source

        items: List[Dict[str, Any]] = []
        for rss_url in self.urls:
            feed = fetch_rss(rss_url, delay=self.fetch_delay)
            if not feed or not feed.entries:
                continue
            default_source = default_source_from_url(rss_url)
            for entry in feed.entries[: self.max_items_per_source]:
                source_name = get_entry_source(entry, rss_url, default_source)
                item = parse_entry_fn(entry, source_name)
                if item:
                    items.append(item)
        return items
