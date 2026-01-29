"""
网页消息来源采集模块
非 RSS 的网页时间线（如 xcancel），使用仿真请求头，在独立线程中按间隔请求。
"""
import threading
import time
from typing import List, Dict, Optional
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from config import settings
from utils.logger import logger
from utils.time import format_date_for_display

# 每个来源最多取几条
MAX_ITEMS_PER_PAGE = 10


def _get_headers() -> Dict[str, str]:
    """使用配置的仿真请求头。"""
    return dict(getattr(settings, "WEB_REQUEST_HEADERS", {}) or {})


def fetch_page(url: str, timeout: int = 20) -> Optional[str]:
    """
    用仿真请求头抓取网页 HTML。
    """
    headers = _get_headers()
    if not headers:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logger.warning(f"网页抓取失败 {url}: {e}")
        return None


def _category_and_source(key: str) -> tuple:
    """根据 WEB_SOURCES 的 key 返回 (category, source_name)。"""
    key_lower = key.lower()
    if "elon" in key_lower or "musk" in key_lower:
        return "马斯克", "X / Elon Musk"
    if "trump" in key_lower or "donald" in key_lower:
        return "特朗普", "X / Donald Trump"
    return "网页", key


def _extract_tweet_like_items(html: str, base_url: str, category: str, source_name: str) -> List[Dict]:
    """
    从 xcancel/Nitter 风格或通用时间线页面解析「推文/帖子」条目。
    优先尝试 Nitter 风格（article、.timeline-item、.tweet-content、/status/ 链接）。
    """
    soup = BeautifulSoup(html, "lxml")
    if not soup:
        soup = BeautifulSoup(html, "html.parser")
    items: List[Dict] = []
    base_netloc = urlparse(base_url).netloc or ""

    # 1) Nitter/xcancel 常见：article 或 .timeline-item 包裹每条
    candidates = soup.select("article.timeline-item, .timeline-item, article")
    if not candidates:
        candidates = soup.select("[data-testid='tweet'], .tweet, .post")
    for node in candidates[:MAX_ITEMS_PER_PAGE * 2]:
        text_node = node.select_one(".tweet-content, .tweet-body, [data-testid='tweetText'], .content")
        if not text_node:
            text_node = node
        text = (text_node.get_text(separator=" ", strip=True) or "").strip()
        if not text or len(text) < 3:
            continue
        # 找本条链接（/status/ 或 第一条 a[href]）
        link = ""
        for a in node.select('a[href*="/status/"], a[href*="/statuses/"]'):
            href = a.get("href") or ""
            if href.startswith("http"):
                link = href
                break
            link = urljoin(base_url, href)
            break
        if not link:
            for a in node.select("a[href]"):
                href = (a.get("href") or "").strip()
                if "/status/" in href or "/statuses/" in href:
                    link = urljoin(base_url, href) if not href.startswith("http") else href
                    break
        if not link:
            link = base_url
        items.append({
            "category": category,
            "title": text[:200] if len(text) > 200 else text,
            "content": text[:500] if len(text) > 500 else text,
            "source": source_name,
            "url": link,
            "published_at": format_date_for_display(datetime.now(timezone.utc)),
        })
        if len(items) >= MAX_ITEMS_PER_PAGE:
            break

    # 2) 若没有 article/timeline，则按「带 /status/ 的链接 + 附近文本」拼条目
    if not items:
        for a in soup.select('a[href*="/status/"], a[href*="/statuses/"]')[:MAX_ITEMS_PER_PAGE]:
            href = a.get("href") or ""
            link = urljoin(base_url, href) if not href.startswith("http") else href
            text = (a.get_text(separator=" ", strip=True) or "").strip()
            parent = a.parent
            for _ in range(5):
                if not parent:
                    break
                t = (parent.get_text(separator=" ", strip=True) or "").strip()
                if len(t) > len(text) and len(t) < 2000:
                    text = t
                    break
                parent = parent.parent
            if not text:
                text = a.get_text(separator=" ", strip=True) or "无正文"
            items.append({
                "category": category,
                "title": text[:200] if len(text) > 200 else text,
                "content": text[:500] if len(text) > 500 else text,
                "source": source_name,
                "url": link,
                "published_at": format_date_for_display(datetime.now(timezone.utc)),
            })
        items = items[:MAX_ITEMS_PER_PAGE]

    return items


def _worker(result_list: List[Dict], interval: float) -> None:
    """
    在独立线程中按间隔请求 WEB_SOURCES，解析后写入 result_list。
    """
    web_sources = getattr(settings, "WEB_SOURCES", None) or {}
    for key, urls in web_sources.items():
        if not urls:
            continue
        category, source_name = _category_and_source(key)
        for url in urls:
            try:
                html = fetch_page(url)
                if html:
                    parsed = _extract_tweet_like_items(html, url, category, source_name)
                    result_list.extend(parsed)
                    logger.info(f"网页来源 [{key}] {url} 解析到 {len(parsed)} 条")
            except Exception as e:
                logger.warning(f"网页来源解析失败 [{key}] {url}: {e}")
            time.sleep(interval)


def collect_all() -> List[Dict]:
    """
    在独立线程中采集所有 WEB_SOURCES，请求间隔 30 秒，返回合并后的列表。
    """
    web_sources = getattr(settings, "WEB_SOURCES", None) or {}
    if not web_sources:
        return []
    result_list: List[Dict] = []
    interval = float(getattr(settings, "WEB_REQUEST_INTERVAL", 30) or 30)
    th = threading.Thread(target=_worker, args=(result_list, interval), daemon=False)
    th.start()
    th.join()
    logger.info(f"网页来源采集完成，共 {len(result_list)} 条")
    return result_list
