"""
硬件上游原材料数据采集
RSS 资讯 + 正文价提取 + yfinance 期货参考 + 价格快照涨跌
"""
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import feedparser
import requests
from bs4 import BeautifulSoup

from config import settings
from utils.logger import logger
from utils.rss_fetcher import fetch_rss
from utils.time import get_today_date

_PRICE_PATTERNS = [
    (r"(\d{1,6}(?:\.\d+)?)\s*万元\s*/?\s*吨", "万元/吨", 1.0),
    (r"(\d{2,6}(?:\.\d+)?)\s*元\s*/?\s*吨", "元/吨", 1.0),
    (r"(\d{1,5}(?:\.\d+)?)\s*元\s*/?\s*(?:kg|公斤|千克)", "元/kg", 1.0),
    (r"(\d{1,5}(?:\.\d+)?)\s*元\s*/?\s*千只", "元/千只", 1.0),
    (r"(\d{1,5}(?:\.\d+)?)\s*元\s*/?\s*芯公里", "元/芯公里", 1.0),
    (r"(\d{1,5}(?:\.\d+)?)\s*元\s*/?\s*片", "元/片", 1.0),
    (r"(\d{1,5}(?:\.\d+)?)\s*元\s*/?\s*升", "元/升", 1.0),
    (r"报价\s*(\d{1,6}(?:\.\d+)?)", "报价", 1.0),
    (r"价格\s*(\d{1,6}(?:\.\d+)?)", "报价", 1.0),
]


def _snapshot_path() -> Path:
    return Path("data") / "upstream_price_snapshot.json"


def _load_snapshot() -> Dict[str, float]:
    path = _snapshot_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        prices = data.get("prices", {})
        if isinstance(prices, dict):
            return {str(k): float(v) for k, v in prices.items()}
    except Exception:
        return {}
    return {}


def _save_snapshot(prices: Dict[str, float]) -> None:
    path = _snapshot_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"prices": prices}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning("写入上游价格快照失败: %s", e)


def _materials_config() -> List[Dict]:
    return getattr(settings, "UPSTREAM_MATERIALS", None) or []


def _matches_material(text: str, keywords: List[str]) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(kw.lower() in lower or kw in text for kw in keywords if kw)


def _extract_price_from_text(text: str) -> Optional[Tuple[float, str]]:
    if not text:
        return None
    for pattern, unit, _ in _PRICE_PATTERNS:
        m = re.search(pattern, text, flags=re.I)
        if not m:
            continue
        try:
            val = float(m.group(1))
        except (ValueError, TypeError):
            continue
        if val <= 0 or val > 1_000_000:
            continue
        return val, unit
    return None


def _extract_price_near_keyword(text: str, keywords: List[str]) -> Optional[Tuple[float, str]]:
    if not text:
        return None
    for kw in keywords:
        if not kw:
            continue
        m = re.search(
            rf"{re.escape(kw)}[\s\S]{{0,40}}?(\d{{1,6}}(?:\.\d+)?)\s*(?:万元\s*/?\s*吨|元\s*/?\s*吨|元\s*/?\s*kg|元\s*/?\s*千只|元\s*/?\s*片|元\s*/?\s*升)",
            text,
            flags=re.I,
        )
        if m:
            snippet = m.group(0)
            parsed = _extract_price_from_text(snippet)
            if parsed:
                return parsed
    return _extract_price_from_text(text)


def _fetch_article_text(url: str) -> str:
    if not url or not str(url).startswith("http"):
        return ""
    try:
        resp = requests.get(
            url,
            timeout=12,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
            },
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text or "", "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(" ", strip=True)
        return re.sub(r"\s+", " ", text).strip()[:12000]
    except Exception:
        return ""


def _parse_rss_entry(entry: feedparser.FeedParserDict, source_name: str) -> Optional[Dict]:
    try:
        title = (entry.get("title") or "").strip()
        link = entry.get("link", "")
        summary = (entry.get("summary") or "").strip()
        if not title:
            return None
        content = summary or title
        matched = None
        for mat in _materials_config():
            if _matches_material(title + " " + content, mat.get("keywords", [])):
                matched = mat["name"]
                break
        if not matched:
            return None
        return {
            "category": "上游原材料",
            "title": title[:200],
            "content": (content[:500] + "…") if len(content) > 500 else content,
            "source": source_name,
            "url": link,
            "published_at": get_today_date(),
            "material": matched,
        }
    except Exception as e:
        logger.debug("解析上游 RSS 条目失败: %s", e)
        return None


def _collect_rss_news() -> List[Dict]:
    items: List[Dict] = []
    urls = getattr(settings, "UPSTREAM_RSS_SOURCES", None) or []
    max_items = getattr(settings, "MAX_ITEMS_PER_SOURCE", 20)
    for rss_url in urls:
        feed = fetch_rss(rss_url)
        if not feed or not getattr(feed, "entries", None):
            continue
        source_name = (
            "Google News" if "google.com" in rss_url
            else ("新浪财经" if "sina.com" in rss_url else "RSS")
        )
        for entry in feed.entries[:max_items]:
            item = _parse_rss_entry(entry, source_name)
            if item:
                items.append(item)
    return items


def _get_yfinance_price(symbol: str) -> Optional[Dict[str, Any]]:
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d")
        if hist is None or hist.empty or len(hist) < 2:
            return None
        latest = float(hist.iloc[-1]["Close"])
        prev = float(hist.iloc[-2]["Close"])
        if prev == 0:
            return None
        change_pct = ((latest - prev) / prev) * 100
        return {"price": latest, "change_pct": change_pct, "unit": "美元/磅", "source": "COMEX期货"}
    except Exception as e:
        logger.debug("yfinance 上游参考价失败 %s: %s", symbol, e)
        return None


def _build_price_details(news_items: List[Dict]) -> Dict[str, Dict[str, Any]]:
    """从资讯中提取各材料最优价格行。"""
    detail: Dict[str, Dict[str, Any]] = {}
    materials = _materials_config()

    for mat in materials:
        name = mat["name"]
        keywords = mat.get("keywords", [])
        yf_symbol = mat.get("yf_symbol")
        if yf_symbol:
            yf_data = _get_yfinance_price(yf_symbol)
            if yf_data:
                detail[name] = {
                    "price": yf_data["price"],
                    "unit": yf_data["unit"],
                    "change_pct": yf_data.get("change_pct"),
                    "source": yf_data["source"],
                    "factors": f"期货参考 {yf_symbol}",
                    "estimated": False,
                    "quality": 10,
                }

    fetch_budget = 8
    for item in news_items:
        text = f"{item.get('title', '')} {item.get('content', '')}"
        material = item.get("material")
        if not material:
            for mat in materials:
                if _matches_material(text, mat.get("keywords", [])):
                    material = mat["name"]
                    break
        if not material:
            continue
        mat_cfg = next((m for m in materials if m["name"] == material), None)
        if not mat_cfg:
            continue
        if material in detail and not detail[material].get("estimated", True):
            continue
        parsed = _extract_price_near_keyword(text, mat_cfg.get("keywords", []))
        if not parsed and item.get("url") and fetch_budget > 0:
            article = _fetch_article_text(str(item["url"]))
            fetch_budget -= 1
            if article:
                parsed = _extract_price_near_keyword(article, mat_cfg.get("keywords", []))
        if not parsed:
            continue
        price, unit = parsed
        quality = 5
        if material in str(item.get("title", "")):
            quality += 2
        prev_q = detail.get(material, {}).get("quality", -1)
        if quality > prev_q:
            detail[material] = {
                "price": price,
                "unit": unit or mat_cfg.get("unit", ""),
                "change_pct": None,
                "source": str(item.get("source", "资讯")),
                "factors": str(item.get("title", ""))[:80],
                "estimated": True,
                "quality": quality,
            }

    return detail


def _fmt_change(curr: float, prev: Optional[float]) -> Optional[float]:
    if prev is None or prev == 0:
        return None
    return ((curr - prev) / prev) * 100


def build_price_table_items(news_items: List[Dict]) -> List[Dict]:
    """生成结构化上游价格表条目（category=上游价格表）。"""
    detail = _build_price_details(news_items)
    previous = _load_snapshot()
    current: Dict[str, float] = {}
    rows: List[Dict] = []

    for name, d in detail.items():
        price = float(d["price"])
        current[name] = price
        day_chg = d.get("change_pct")
        if day_chg is None:
            day_chg = _fmt_change(price, previous.get(name))
        est = d.get("estimated", False)
        unit = d.get("unit", "")
        rows.append({
            "category": "上游价格表",
            "material": name,
            "title": f"{name}：{price:g} {unit}",
            "content": d.get("factors", ""),
            "source": d.get("source", ""),
            "url": "",
            "published_at": get_today_date(),
            "price": price,
            "unit": unit,
            "change_pct": day_chg,
            "factors": d.get("factors", ""),
            "estimated": est,
        })

    if current:
        _save_snapshot(current)

    return rows


def collect_all() -> List[Dict]:
    """采集上游原材料资讯并生成价格表行。"""
    all_items: List[Dict] = []
    try:
        news = _collect_rss_news()
        all_items.extend(news)
        logger.info("上游原材料资讯：%d 条", len(news))
    except Exception as e:
        logger.warning("上游原材料 RSS 采集失败: %s", e)
        news = []

    try:
        price_rows = build_price_table_items(news)
        all_items.extend(price_rows)
        logger.info("上游价格表：%d 项", len(price_rows))
    except Exception as e:
        logger.warning("上游价格表生成失败: %s", e)

    return all_items
