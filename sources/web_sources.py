"""
网页消息来源采集模块
非 RSS 的网页时间线（如 xcancel），使用仿真请求头，在独立线程中按间隔请求。
智能网关（如 farside）会 302 或 meta refresh 跳转，需跟随跳转到底再解析。
"""
import re
import threading
import time
from typing import List, Dict, Optional
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from config import settings
from utils.logger import logger
from utils.time import format_date_for_display, parse_date

# 每个来源最多取几条
MAX_ITEMS_PER_PAGE = 10
# 智能网关 meta refresh 最多跟随次数
MAX_REDIRECT_HOPS = 8


def _get_headers() -> Dict[str, str]:
    """使用配置的仿真请求头。"""
    return dict(getattr(settings, "WEB_REQUEST_HEADERS", {}) or {})


def _extract_meta_refresh_url(html: str, current_url: str) -> Optional[str]:
    """
    从 HTML 中解析 meta http-equiv="refresh" 的目标 URL。
    智能网关常用 meta refresh 做二次跳转，requests 不会自动跟随。
    """
    if not html or not current_url:
        return None
    # content 形如 "0; url=https://..." 或 "0;URL=https://..."
    m = re.search(
        r'<meta\s+http-equiv=["\']?refresh["\']?\s+content=["\']?\d+\s*;\s*url=([^"\'>\s]+)',
        html,
        re.I,
    )
    if m:
        target = m.group(1).strip()
        if target.startswith("http://") or target.startswith("https://"):
            return target
        return urljoin(current_url, target)
    return None


def fetch_page(url: str, timeout: int = 25) -> Optional[str]:
    """
    用仿真请求头抓取网页 HTML；
    1) 使用 Session 跟随 HTTP 302 跳转到底；
    2) 若响应是 HTML 且含 meta refresh，继续请求目标 URL 直至无跳转或达到 MAX_REDIRECT_HOPS；
    3) 失败时按配置重试（默认 5 次）。
    """
    headers = _get_headers()
    if not headers:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
    retries = int(getattr(settings, "WEB_REQUEST_RETRIES", 5) or 5)
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            with requests.Session() as session:
                session.headers.update(headers)
                session.max_redirects = 15
                current = url
                html = None
                for hop in range(MAX_REDIRECT_HOPS + 1):
                    resp = session.get(current, timeout=timeout, allow_redirects=True)
                    resp.raise_for_status()
                    html = resp.text
                    if not html or len(html) < 100:
                        break
                    # Session 已跟完 302，resp.url 为当前页；再检查是否还有 meta refresh 需跟随
                    next_url = _extract_meta_refresh_url(html, resp.url)
                    if not next_url:
                        break
                    try:
                        next_full = urljoin(resp.url, next_url) if next_url.startswith("/") else next_url
                    except Exception:
                        next_full = next_url
                    if next_full == resp.url:
                        break
                    current = next_full
                    if hop < MAX_REDIRECT_HOPS:
                        time.sleep(1)
                return html
        except Exception as e:
            last_error = e
            if attempt < retries:
                wait = min(3 * attempt, 15)
                logger.warning(f"网页抓取失败 {url} (第 {attempt}/{retries} 次): {e}，{wait}s 后重试")
                time.sleep(wait)
            else:
                logger.warning(f"网页抓取失败 {url} (已重试 {retries} 次): {e}")
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


def _fetch_json_truth_archive(
    url: str, category: str, source_name: str
) -> List[Dict]:
    """
    请求 Truth Social 归档 JSON，转换为与网页解析一致的条目格式。
    期望 JSON 为数组，每项含 id, created_at, content, url 等。
    """
    headers = _get_headers()
    try:
        resp = requests.get(url, headers=headers, timeout=25)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"JSON 来源请求失败 {url}: {e}")
        return []
    if not isinstance(data, list):
        return []
    items: List[Dict] = []
    for obj in data[:MAX_ITEMS_PER_PAGE]:
        if not isinstance(obj, dict):
            continue
        content_raw = (obj.get("content") or "").strip()
        link = (obj.get("url") or "").strip()
        created = obj.get("created_at") or ""
        if not content_raw and not link:
            continue
        title = content_raw[:200] if content_raw else (link[:200] if link else "Truth Social")
        content = (content_raw[:500] if content_raw else title) or title
        dt = parse_date(created) if created else None
        published_at = format_date_for_display(dt or datetime.now(timezone.utc))
        items.append({
            "category": category,
            "title": title,
            "content": content,
            "source": source_name,
            "url": link or url,
            "published_at": published_at,
        })
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
                if url.rstrip("/").endswith(".json"):
                    parsed = _fetch_json_truth_archive(url, category, source_name)
                    if parsed:
                        result_list.extend(parsed)
                        logger.info(f"网页来源 [{key}] {url} 解析到 {len(parsed)} 条")
                else:
                    html = fetch_page(url)
                    if html:
                        parsed = _extract_tweet_like_items(html, url, category, source_name)
                        result_list.extend(parsed)
                        logger.info(f"网页来源 [{key}] {url} 解析到 {len(parsed)} 条")
            except Exception as e:
                logger.warning(f"网页来源解析失败 [{key}] {url}: {e}")
            time.sleep(interval)


def start_collection_thread() -> tuple:
    """
    启动网页采集的独立线程，不阻塞主线程。
    主流程可继续采集其他源，最后 join 本线程再合并结果。

    Returns:
        (thread, result_list): 线程对象与结果列表（线程会往 result_list 里追加）
    """
    web_sources_config = getattr(settings, "WEB_SOURCES", None) or {}
    result_list: List[Dict] = []
    if not web_sources_config:
        th = threading.Thread(target=lambda: None, daemon=True)
        th.start()
        return th, result_list
    interval = float(getattr(settings, "WEB_REQUEST_INTERVAL", 30) or 30)
    th = threading.Thread(target=_worker, args=(result_list, interval), daemon=False)
    th.start()
    return th, result_list


def collect_all() -> List[Dict]:
    """
    在独立线程中采集所有 WEB_SOURCES，请求间隔 30 秒，返回合并后的列表。
    会阻塞直到采集完成；若希望不阻塞，请用 start_collection_thread()。
    """
    th, result_list = start_collection_thread()
    th.join()
    logger.info(f"网页来源采集完成，共 {len(result_list)} 条")
    return result_list
