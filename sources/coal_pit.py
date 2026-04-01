"""
煤炭·产地坑口价格数据采集
从 config.settings.COAL_PIT_SOURCES 配置的 RSS 抓取产地坑口价相关资讯（榆林、鄂尔多斯等）。
"""
from typing import List, Dict, Optional

import feedparser
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import random
import time

from config import settings
from utils.logger import logger
from utils.rss_fetcher import fetch_rss
from utils.time import get_today_date, parse_date, format_date_for_display


_PIT_KEYWORDS = ("煤", "煤炭", "产地", "坑口", "榆林", "鄂尔多斯", "山西", "陕西", "蒙西", "焦煤", "焦炭")
_PIT_MARKERS = ("榆林", "鄂尔多斯", "神木", "府谷", "产地", "坑口")
_PRICE_RE = r"(?:报价|价格|坑口价|车板价|现货价)?\s*(\d{2,4}(?:\.\d+)?)\s*元\s*/?\s*吨(?:左右)?"
_DETAIL_HINTS = ("煤炭市场早报", "价格快讯", "价格指数", "动力煤", "坑口", "港口", "煤价", "煤炭")
_UA_POOL = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
)

def _parse_entry(entry: feedparser.FeedParserDict, source_name: str) -> Optional[Dict]:
    """将 RSS 条目解析为标准数据项。"""
    try:
        title = (entry.get("title") or "").strip()
        link = entry.get("link", "")
        published = entry.get("published", "")
        summary = (entry.get("summary", "") or "").strip()
        content = summary or title
        combined = (title + " " + content).lower()
        if not any(kw in combined for kw in _PIT_KEYWORDS):
            return None
        published_at = get_today_date()
        if published:
            parsed = parse_date(published)
            if parsed:
                published_at = format_date_for_display(parsed)
        return {
            "category": "产地坑口",
            "title": title[:200] if len(title) > 200 else title,
            "content": (content[:500] + "…") if len(content) > 500 else content,
            "source": source_name,
            "url": link,
            "published_at": published_at,
        }
    except Exception as e:
        logger.debug("解析产地坑口条目失败: %s", e)
        return None


def collect_all() -> List[Dict]:
    """采集产地坑口价相关资讯（RSS）。"""
    all_items: List[Dict] = []
    urls = getattr(settings, "COAL_PIT_SOURCES", None) or []
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
    all_items.extend(_collect_pit_from_web())
    logger.info("产地坑口：采集到 %d 条", len(all_items))
    return all_items


def _collect_pit_from_web() -> List[Dict]:
    items: List[Dict] = []
    urls = getattr(settings, "COAL_WEB_SOURCES", None) or []
    session = requests.Session()
    for page_url in urls:
        url = str(page_url or "").strip()
        if not url.startswith("http"):
            continue
        try:
            headers = _build_headers(url)
            _human_delay()
            resp = _request_with_retry(session, url, headers)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text or "", "lxml")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            text = soup.get_text("\n", strip=True)
            lines = _extract_candidate_lines(soup, text, url)
            for ln in lines:
                if not any(m in ln for m in _PIT_MARKERS):
                    continue
                if "煤" not in ln:
                    continue
                if not re.search(_PRICE_RE, ln):
                    continue
                items.append(
                    {
                        "category": "产地坑口",
                        "title": ln[:200],
                        "content": ln[:500],
                        "source": _web_source_name(url),
                        "url": url,
                        "published_at": get_today_date(),
                    }
                )
                if len(items) >= 20:
                    break
            # 下钻详情页，提高坑口价格提取命中率
            for detail_url in _collect_detail_links(soup, url):
                detail_lines = _fetch_text_lines(session, detail_url)
                for ln in detail_lines:
                    if not any(m in ln for m in _PIT_MARKERS):
                        continue
                    if "煤" not in ln or not re.search(_PRICE_RE, ln):
                        continue
                    items.append(
                        {
                            "category": "产地坑口",
                            "title": ln[:200],
                            "content": ln[:500],
                            "source": _web_source_name(url),
                            "url": detail_url,
                            "published_at": get_today_date(),
                        }
                    )
                    if len(items) >= 40:
                        break
                if len(items) >= 40:
                    break
        except Exception as e:
            logger.debug("产地坑口网页采集失败 %s: %s", url, e)
    return items


def _web_source_name(url: str) -> str:
    if "mofcom.gov.cn" in url:
        return "商务预报"
    if "ccera.com.cn" in url:
        return "中国煤炭经济网"
    if "eastmoney.com" in url:
        return "东方财富"
    if "10jqka.com.cn" in url:
        return "同花顺财经"
    return "网页源"


def _collect_detail_links(soup: BeautifulSoup, base_url: str) -> List[str]:
    host = urlparse(base_url).netloc
    links: List[str] = []
    seen = set()
    for a in soup.find_all("a"):
        text = (a.get_text(" ", strip=True) or "").strip()
        href = (a.get("href") or "").strip()
        if not href:
            continue
        href_l = href.lower()
        if not any(h in text for h in _DETAIL_HINTS):
            if not any(k in href_l for k in ("coal", "meitan", "price", "hangqing", "market", "index")):
                continue
        if any(x in href_l for x in ("login", "register", "video", "live")):
            continue
        full = urljoin(base_url, href)
        p = urlparse(full)
        if p.scheme not in ("http", "https"):
            continue
        if host and host not in p.netloc:
            continue
        if full in seen:
            continue
        seen.add(full)
        links.append(full)
        if len(links) >= 8:
            break
    return links


def _fetch_text_lines(session: requests.Session, url: str) -> List[str]:
    try:
        headers = _build_headers(url)
        _human_delay()
        resp = _request_with_retry(session, url, headers)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text or "", "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text("\n", strip=True)
        return _extract_candidate_lines(soup, text, url)
    except Exception:
        return []


def _extract_candidate_lines(soup: BeautifulSoup, text: str, url: str) -> List[str]:
    """按站点特征提取更可能含坑口煤价的候选行。"""
    lines: List[str] = []
    host = urlparse(url).netloc
    for ln in text.splitlines():
        s = ln.strip()
        if s:
            lines.append(s)
    for tr in soup.find_all("tr"):
        row = " ".join(td.get_text(" ", strip=True) for td in tr.find_all(["th", "td"]))
        row = re.sub(r"\s+", " ", row).strip()
        if row:
            lines.append(row)
    if "10jqka.com.cn" in host or "eastmoney.com" in host:
        for node in soup.find_all(["p", "li", "div"]):
            s = node.get_text(" ", strip=True)
            s = re.sub(r"\s+", " ", s).strip()
            if len(s) >= 16:
                lines.append(s)
    seen = set()
    uniq: List[str] = []
    for s in lines:
        if s in seen:
            continue
        seen.add(s)
        uniq.append(s)
    return uniq[:1200]


def _human_delay() -> None:
    time.sleep(random.uniform(0.35, 1.05))


def _build_headers(url: str) -> Dict[str, str]:
    host = urlparse(url).netloc
    scheme = urlparse(url).scheme or "https"
    origin = f"{scheme}://{host}" if host else ""
    return {
        "User-Agent": random.choice(_UA_POOL),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Referer": origin + "/" if origin else "",
    }


def _request_with_retry(session: requests.Session, url: str, headers: Dict[str, str], retries: int = 2):
    last_err = None
    for attempt in range(retries + 1):
        try:
            return session.get(url, timeout=12, headers=headers, allow_redirects=True)
        except requests.RequestException as e:
            last_err = e
            if attempt < retries:
                time.sleep(0.8 * (attempt + 1) + random.uniform(0.2, 0.6))
    raise last_err
