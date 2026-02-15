"""
Google News RSS 统一拉取模块
支持全球中文/英文/按话题预设，关键词过滤，每次请求间隔 1 秒，可独立线程运行。
"""
import threading
import time
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from urllib.parse import quote_plus

from utils.rss_fetcher import fetch_rss
from utils.source_from_entry import get_entry_source
from utils.time import is_today, format_date_for_display, parse_date
from utils.logger import logger

# 预设名称
PRESET_ZH = "zh"
PRESET_EN = "en"
PRESET_TOPIC = "topic"


def build_google_news_rss_url(
    query_keywords: Optional[List[str]] = None,
    hl: str = "en-US",
    gl: str = "US",
    ceid: str = "US:en",
    when: str = "24h",
) -> str:
    """
    生成 Google News RSS 单条 URL。

    Args:
        query_keywords: 查询关键词列表，None 或空则仅 when:24h
        hl, gl, ceid: 语言/地区
        when: 时间范围，默认 24h

    Returns:
        RSS 搜索 URL
    """
    if query_keywords:
        parts = [quote_plus(k.strip()) for k in query_keywords if k and str(k).strip()]
        q = "+".join(parts) + "+" + when
    else:
        q = when
    return f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"


def _entry_matches_filter(entry: Any, keywords_filter: Optional[List[str]]) -> bool:
    """条目标题/摘要是否匹配任一关键词（忽略大小写）。无关键词列表则不过滤，全部保留。"""
    if not keywords_filter:
        return True
    title = (entry.get("title") or "").lower()
    summary = (entry.get("summary") or "").lower()
    text = title + " " + summary
    return any(kw.lower() in text for kw in keywords_filter if kw and str(kw).strip())


def fetch_google_news_rss(
    preset: str = PRESET_EN,
    topic_keywords: Optional[List[str]] = None,
    keywords_filter: Optional[List[str]] = None,
    category: str = "世界新闻",
    max_items: int = 20,
    request_delay: float = 1.0,
) -> List[Dict[str, Any]]:
    """
    根据预设拉取 Google News RSS，按关键词过滤条目。

    Args:
        preset: "zh" 全球中文 24h，"en" 全球英文 24h，"topic" 按话题（需 topic_keywords）
        topic_keywords: 话题关键词（仅 preset=="topic" 时用于拼 q=）
        keywords_filter: 拉取后条目过滤：标题/摘要包含任一关键词则保留
        category: 条目 category 字段
        max_items: 每源最多条目数
        request_delay: 本次请求前等待秒数（由调用方保证多次请求间间隔）

    Returns:
        标准条目列表
    """
    from config import settings

    presets = getattr(settings, "GOOGLE_NEWS_PRESETS", None) or {}
    cfg = presets.get(preset)
    if not cfg and preset == PRESET_TOPIC and topic_keywords:
        cfg = {"hl": "en-US", "gl": "US", "ceid": "US:en"}
    if not cfg:
        cfg = presets.get(PRESET_EN) or {"hl": "en-US", "gl": "US", "ceid": "US:en"}

    hl = cfg.get("hl", "en-US")
    gl = cfg.get("gl", "US")
    ceid = cfg.get("ceid", "US:en")

    if preset == PRESET_TOPIC and topic_keywords:
        url = build_google_news_rss_url(
            query_keywords=topic_keywords, hl=hl, gl=gl, ceid=ceid, when="24h"
        )
    else:
        url = build_google_news_rss_url(
            query_keywords=None, hl=hl, gl=gl, ceid=ceid, when="24h"
        )

    time.sleep(request_delay)
    feed = fetch_rss(url, delay=0)
    if not feed or not feed.entries:
        return []

    items: List[Dict[str, Any]] = []
    default_source = "Google News"
    for entry in feed.entries[: max_items * 2]:
        if len(items) >= max_items:
            break
        if not _entry_matches_filter(entry, keywords_filter):
            continue
        published = entry.get("published", "")
        if not is_today(published):
            continue
        title = (entry.get("title") or "").strip()
        link = entry.get("link", "")
        summary = (entry.get("summary") or "").strip()
        content = summary if summary else title
        source_name = get_entry_source(entry, url, default_source)
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
    return items


def _worker(
    result_list: List[Dict],
    tasks: List[Dict],
    request_interval: float,
) -> None:
    """独立线程中按顺序执行多个 Google RSS 任务，每次请求前间隔 request_interval 秒。"""
    for i, task in enumerate(tasks):
        preset = task.get("preset", "en")
        topic_keywords = task.get("topic_keywords")
        keywords_filter = task.get("keywords_filter")
        category = task.get("category", "世界新闻")
        max_items = task.get("max_items", 20)
        try:
            items = fetch_google_news_rss(
                preset=preset,
                topic_keywords=topic_keywords,
                keywords_filter=keywords_filter,
                category=category,
                max_items=max_items,
                request_delay=request_interval,
            )
            if items:
                result_list.extend(items)
                logger.info(f"Google RSS [{preset}] {category} 采集到 {len(items)} 条")
        except Exception as e:
            logger.warning(f"Google RSS 任务失败 [{preset}] {category}: {e}")


def start_google_rss_collection_thread(
    tasks: Optional[List[Dict]] = None,
    request_interval: float = 1.0,
) -> tuple:
    """
    启动 Google RSS 采集的独立线程，不阻塞主线程。

    Args:
        tasks: 任务列表，每项含 preset, topic_keywords(可选), keywords_filter(可选), category, max_items(可选)
        request_interval: 每次请求间隔秒数

    Returns:
        (thread, result_list)：线程对象与结果列表（线程会往 result_list 里追加）
    """
    from config import settings

    if not tasks:
        tasks = getattr(settings, "GOOGLE_NEWS_TASKS", None) or []
    if not tasks:
        th = threading.Thread(target=lambda: None, daemon=True)
        th.start()
        return th, []

    result_list: List[Dict] = []
    interval = float(getattr(settings, "GOOGLE_NEWS_REQUEST_INTERVAL", 1) or 1)
    th = threading.Thread(
        target=_worker,
        args=(result_list, tasks, max(interval, request_interval)),
        daemon=False,
    )
    th.start()
    return th, result_list
