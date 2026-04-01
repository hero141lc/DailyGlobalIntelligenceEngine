"""
煤炭·港口煤价数据采集
从 config.settings.COAL_PORT_SOURCES 配置的 RSS 抓取港口煤价相关资讯（秦皇岛、环渤海等）。
"""
from typing import List, Dict, Optional

import feedparser
import re
import requests
from bs4 import BeautifulSoup

from config import settings
from utils.logger import logger
from utils.rss_fetcher import fetch_rss
from utils.time import get_today_date, parse_date, format_date_for_display


# 关键词过滤：仅保留与港口煤价相关（新浪等综合 RSS 会混入大量无关内容）
_COAL_PORT_KEYWORDS = ("煤", "煤炭", "动力煤", "秦皇岛", "环渤海", "港口", "焦煤", "焦炭")

_PORT_MARKERS = ("秦皇岛", "曹妃甸", "京唐", "黄骅", "环渤海")
_PRICE_RE = r"\d{2,4}(?:\.\d+)?\s*元\s*/?\s*吨"

def _parse_entry(entry: feedparser.FeedParserDict, source_name: str) -> Optional[Dict]:
    """将 RSS 条目解析为标准数据项。"""
    try:
        title = (entry.get("title") or "").strip()
        link = entry.get("link", "")
        published = entry.get("published", "")
        summary = (entry.get("summary", "") or "").strip()
        content = summary or title
        # 通用 RSS（如新浪）需过滤：仅保留含煤炭关键词的
        combined = (title + " " + content).lower()
        if not any(kw in combined for kw in _COAL_PORT_KEYWORDS):
            return None
        published_at = get_today_date()
        if published:
            parsed = parse_date(published)
            if parsed:
                published_at = format_date_for_display(parsed)
        return {
            "category": "港口煤价",
            "title": title[:200] if len(title) > 200 else title,
            "content": (content[:500] + "…") if len(content) > 500 else content,
            "source": source_name,
            "url": link,
            "published_at": published_at,
        }
    except Exception as e:
        logger.debug("解析港口煤价条目失败: %s", e)
        return None


def collect_all() -> List[Dict]:
    """采集港口煤价相关资讯（RSS）。"""
    all_items: List[Dict] = []
    urls = getattr(settings, "COAL_PORT_SOURCES", None) or []
    urls = [u.strip() for u in urls if u and str(u).strip()]
    max_items = getattr(settings, "MAX_ITEMS_PER_SOURCE", 20)

    for rss_url in urls:
        feed = fetch_rss(rss_url)
        if not feed or not getattr(feed, "entries", None):
            continue
        source_name = "Google News" if "google.com" in rss_url else ("新浪财经" if "sina.com" in rss_url else "RSS")
        for entry in feed.entries[:max_items]:
            item = _parse_entry(entry, source_name)
            if item and item.get("title"):
                all_items.append(item)
    # 网页补充源：从商务预报/煤炭经济网/东方财富等页面抓取价格句
    all_items.extend(_collect_port_from_web())
    logger.info("港口煤价：采集到 %d 条", len(all_items))
    return all_items


def _collect_port_from_web() -> List[Dict]:
    items: List[Dict] = []
    urls = getattr(settings, "COAL_WEB_SOURCES", None) or []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }
    for page_url in urls:
        url = str(page_url or "").strip()
        if not url.startswith("http"):
            continue
        try:
            resp = requests.get(url, timeout=12, headers=headers)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text or "", "lxml")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            text = soup.get_text("\n", strip=True)
            lines = [ln.strip() for ln in text.splitlines() if ln and ln.strip()]
            for ln in lines:
                if not any(m in ln for m in _PORT_MARKERS):
                    continue
                if "煤" not in ln:
                    continue
                if not re.search(_PRICE_RE, ln):
                    continue
                items.append(
                    {
                        "category": "港口煤价",
                        "title": ln[:200],
                        "content": ln[:500],
                        "source": _web_source_name(url),
                        "url": url,
                        "published_at": get_today_date(),
                    }
                )
                if len(items) >= 20:
                    break
        except Exception as e:
            logger.debug("港口煤价网页采集失败 %s: %s", url, e)
    return items


def _web_source_name(url: str) -> str:
    if "mofcom.gov.cn" in url:
        return "商务预报"
    if "ccera.com.cn" in url:
        return "中国煤炭经济网"
    if "eastmoney.com" in url:
        return "东方财富"
    return "网页源"
