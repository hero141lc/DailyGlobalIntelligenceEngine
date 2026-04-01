"""
Daily Global Intelligence Engine
主程序入口
支持 REPORT_MODE：daily_intel / stock / coal（配置驱动采集、报告与推送）
"""
import sys
import html as html_module
import re
import json
from pathlib import Path
from typing import List, Dict, Optional, Any

import requests
from bs4 import BeautifulSoup

from utils.logger import logger
from utils.dedup import deduplicate_items
from utils import google_rss
from sources import energy, ai, space, fed, stocks
from sources import web_sources, commodities_military, rss_extra, twitter
from sources import coal_port, coal_pit, coal_powerplant, coal_policy
from llm.github_llm import summarize_batch_unified, generate_report_summary_with_reasoning, generate_stock_analysis
from formatter.report_builder import build_html_report
from formatter.stock_report import build_stock_report
from formatter.coal_report import build_coal_report
from mail.mailer import send_report
from mail.feishu import send_report_to_feishu
from mail.wecom import send_wecom

# 同步数据源模块映射（key 与 config.settings.MODE_SOURCES 一致）
# web_sources / google_rss 为线程采集，在 collect_all_data 内单独处理
SOURCE_MODULES: Dict[str, Any] = {
    "energy": energy,
    "commodities_military": commodities_military,
    "ai": ai,
    "space": space,
    "fed": fed,
    "stocks": stocks,
    "rss_extra": rss_extra,
    "twitter": twitter,
    "coal_port": coal_port,
    "coal_pit": coal_pit,
    "coal_powerplant": coal_powerplant,
    "coal_policy": coal_policy,
}


def _collect_data_sources() -> List[Dict]:
    """从配置与 Google RSS 任务收集本次用到的数据来源，用于报告内折叠展示。"""
    from config import settings
    sources: List[Dict] = []
    seen: set = set()
    for category_key, urls in (getattr(settings, "RSS_SOURCES", None) or {}).items():
        if not urls:
            continue
        for url in urls:
            key = ("rss", url)
            if key in seen:
                continue
            seen.add(key)
            sources.append({"name": category_key, "url": url, "category": "RSS"})
    for web_key, urls in (getattr(settings, "WEB_SOURCES", None) or {}).items():
        if not urls:
            continue
        for url in urls:
            uid = ("web", url)
            if uid in seen:
                continue
            seen.add(uid)
            sources.append({"name": web_key, "url": url, "category": "网页"})
    for task in getattr(settings, "GOOGLE_NEWS_TASKS", None) or []:
        preset = task.get("preset", "")
        cat = task.get("category", "世界新闻")
        url = f"https://news.google.com/rss (preset={preset}, category={cat})"
        uid = ("google", preset, cat)
        if uid in seen:
            continue
        seen.add(uid)
        sources.append({"name": f"Google News ({preset})", "url": url, "category": cat})
    return sources


def collect_all_data(mode: Optional[str] = None) -> List[Dict]:
    """
    按指定 mode 只采集 MODE_SOURCES 中启用的数据源。
    mode 为空时使用 settings.REPORT_MODE。
    """
    from config import settings
    all_items: List[Dict] = []
    mode = mode or getattr(settings, "REPORT_MODE", "daily_intel") or "daily_intel"
    mode_sources = getattr(settings, "MODE_SOURCES", None) or {}
    enabled = mode_sources.get(mode, mode_sources.get("daily_intel", []))

    logger.info("=" * 60)
    logger.info("开始数据采集 [REPORT_MODE=%s]", mode)
    logger.info("=" * 60)

    web_thread, web_result_list = None, []
    google_rss_thread, google_rss_result_list = None, []

    if "web_sources" in enabled:
        logger.info("\n采集网页来源（独立线程）...")
        try:
            web_thread, web_result_list = web_sources.start_collection_thread()
        except Exception as e:
            logger.error("✗ 网页来源线程启动失败: %s", e)
    if "google_rss" in enabled:
        logger.info("\n采集 Google News RSS（独立线程）...")
        try:
            google_rss_thread, google_rss_result_list = google_rss.start_google_rss_collection_thread()
        except Exception as e:
            logger.error("✗ Google RSS 线程启动失败: %s", e)

    step = 0
    for key in enabled:
        if key in ("web_sources", "google_rss"):
            continue
        mod = SOURCE_MODULES.get(key)
        if mod is None:
            logger.warning("未知或未实现数据源: %s，已跳过", key)
            continue
        step += 1
        logger.info("\n[%s] 采集 %s...", step, key)
        try:
            items = mod.collect_all()
            all_items.extend(items)
            logger.info("✓ 采集到 %d 条", len(items))
        except Exception as e:
            logger.error("✗ %s 采集失败: %s", key, e)

    if web_thread is not None and web_thread.is_alive():
        logger.info("\n等待网页来源采集线程结束...")
        web_thread.join()
    if google_rss_thread is not None and google_rss_thread.is_alive():
        logger.info("等待 Google News RSS 采集线程结束...")
        google_rss_thread.join()
    if web_result_list:
        logger.info("✓ 网页来源采集到 %d 条（已合并）", len(web_result_list))
    if google_rss_result_list:
        logger.info("✓ Google News RSS 采集到 %d 条（已合并）", len(google_rss_result_list))
    all_items = web_result_list + google_rss_result_list + all_items

    logger.info("\n" + "=" * 60)
    logger.info("数据采集完成，共采集 %d 条数据", len(all_items))
    logger.info("=" * 60)
    return all_items

def process_data(items: List[Dict]) -> List[Dict]:
    """
    处理数据：去重、过滤、摘要生成
    
    Args:
        items: 原始数据项列表
    
    Returns:
        处理后的数据项列表
    """
    logger.info("\n" + "=" * 60)
    logger.info("开始数据处理")
    logger.info("=" * 60)
    
    # 1. 去重
    logger.info("\n[1/3] 数据去重...")
    unique_items = deduplicate_items(items)
    logger.info(f"✓ 去重完成：{len(items)} -> {len(unique_items)} 条")
    
    # 2. 过滤空数据
    logger.info("\n[2/3] 过滤空数据...")
    valid_items = [item for item in unique_items if item.get("title") and item.get("url")]
    logger.info(f"✓ 过滤完成：{len(unique_items)} -> {len(valid_items)} 条")
    
    # 3. 一次性生成所有中文摘要（如果配置了 GitHub Token）
    logger.info("\n[3/3] 一次性生成中文摘要...")
    try:
        from config import settings
        if settings.GITHUB_TOKEN:
            summarized_items = summarize_batch_unified(valid_items)
            logger.info(f"✓ 摘要生成完成：{len(summarized_items)} 条")
            return summarized_items
        else:
            logger.warning("未配置 GITHUB_TOKEN，跳过摘要生成，使用原始内容")
            for item in valid_items:
                if "summary" not in item:
                    original_content = item.get("content", item.get("title", ""))
                    item["summary"] = original_content[:200] + ("..." if len(original_content) > 200 else "")
            return valid_items
    except Exception as e:
        logger.error(f"✗ 摘要生成失败: {e}")
        for item in valid_items:
            if "summary" not in item:
                original_content = item.get("content", item.get("title", ""))
                item["summary"] = original_content[:200] + ("..." if len(original_content) > 200 else "")
        return valid_items

def _markdown_to_html_body(markdown_content: str) -> str:
    """将 Markdown 报告包装为最小 HTML 邮件正文（<pre> 保留换行）。"""
    escaped = html_module.escape(markdown_content)
    from utils.time import get_today_date
    today = get_today_date()
    return (
        f"<!DOCTYPE html><html><head><meta charset=\"UTF-8\"><title>日报 - {today}</title></head>"
        f"<body style=\"font-family: sans-serif; padding: 16px;\">"
        f"<pre style=\"white-space: pre-wrap; word-break: break-all;\">{escaped}</pre>"
        f"</body></html>"
    )


def _html_to_plain_text(html_content: str, max_len: int = 4000) -> str:
    """将 HTML 报告转为纯文本，避免在 IM 渠道里出现标签噪音。"""
    if not html_content:
        return ""
    text = re.sub(r"<[^>]+>", " ", html_content)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        return text[: max_len - 1].rstrip() + "…"
    return text


def _strip_links_and_shrink(text: str, max_len: int = 1000) -> str:
    """去掉 markdown/裸链接并压缩空白，保留可读的纯文本关键信息。"""
    if not text:
        return ""
    cleaned = text
    cleaned = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", cleaned)  # [text](url) -> text
    cleaned = re.sub(r"https?://\S+", "", cleaned)  # 删除裸链接
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > max_len:
        return cleaned[: max_len - 1].rstrip() + "…"
    return cleaned


def _build_wecom_brief(
    mode: str,
    processed: List[Dict],
    report_summary: Optional[str],
    stock_analysis: Optional[str],
    fallback_html_or_md: str,
) -> str:
    """
    构建企业微信精简版正文：文字总结 + 关键信息，不包含链接列表。
    """
    from utils.time import get_today_date

    if mode == "coal":
        return _build_wecom_coal_price_brief(processed)

    lines: List[str] = [f"**{mode} 快报 - {get_today_date()}**"]

    summary = _strip_links_and_shrink(report_summary or "", max_len=1600)
    if summary:
        lines.append(f"\n**今日总结**\n{summary}")

    analysis = _strip_links_and_shrink(stock_analysis or "", max_len=900)
    if analysis:
        lines.append(f"\n**市场观察**\n{analysis}")

    # 关键信息：从处理后的新闻中抽取前几条标题（不带链接）
    key_titles: List[str] = []
    for item in processed:
        title = _strip_links_and_shrink(str(item.get("title", "")), max_len=120)
        if title:
            key_titles.append(title)
        if len(key_titles) >= 8:
            break
    if key_titles:
        lines.append("\n**关键动态**")
        for idx, title in enumerate(key_titles, start=1):
            lines.append(f"{idx}. {title}")

    # 没有总结时（例如 coal），用内容纯文本兜底
    if len(lines) <= 1:
        plain = _strip_links_and_shrink(_html_to_plain_text(fallback_html_or_md, max_len=1800), max_len=1800)
        if plain:
            lines.append(plain)
        else:
            lines.append("今日报告已生成。")

    return "\n".join(lines).strip()


def _extract_first_price(text: str) -> Optional[float]:
    """从文本中提取首个形如 720 元/吨 的价格。"""
    if not text:
        return None
    m = re.search(r"(\d{2,4}(?:\.\d+)?)\s*元\s*/?\s*吨", text)
    if not m:
        return None
    try:
        return float(m.group(1))
    except (ValueError, TypeError):
        return None


def _extract_price_by_keywords(text: str, keywords: tuple[str, ...]) -> Optional[float]:
    """
    在文本中按“关键词附近价格”提取，优先命中更可靠的区域价位。
    例如：秦皇岛...720元/吨
    """
    if not text:
        return None
    for kw in keywords:
        # 关键词后 0~30 个任意字符内出现价格
        m = re.search(rf"{re.escape(kw)}[\s\S]{{0,30}}?(\d{{2,4}}(?:\.\d+)?)\s*元\s*/?\s*吨", text)
        if m:
            try:
                return float(m.group(1))
            except (ValueError, TypeError):
                continue
    return None


def _fetch_article_text(url: str) -> str:
    """抓取文章正文纯文本，用于二次抽取煤价。"""
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
        html = resp.text or ""
        if not html:
            return ""
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:12000]
    except Exception:
        return ""


def _extract_coal_prices(items: List[Dict]) -> Dict[str, float]:
    """从煤炭资讯中提取主流港口与煤矿价格（元/吨）。"""
    markers: List[tuple[str, tuple[str, ...]]] = [
        ("秦皇岛港", ("秦皇岛港", "秦皇岛")),
        ("曹妃甸港", ("曹妃甸港", "曹妃甸")),
        ("京唐港", ("京唐港", "京唐")),
        ("黄骅港", ("黄骅港", "黄骅")),
        ("榆林坑口", ("榆林坑口", "榆林")),
        ("鄂尔多斯坑口", ("鄂尔多斯坑口", "鄂尔多斯")),
        ("神木坑口", ("神木坑口", "神木")),
        ("府谷坑口", ("府谷坑口", "府谷")),
    ]
    prices: Dict[str, float] = {}
    missing = {name for name, _ in markers}

    # 第一轮：用 RSS 标题/摘要快速抽取
    for item in items:
        text = f"{item.get('title', '')} {item.get('content', '')}"
        if not text.strip():
            continue
        for name, kws in markers:
            if name not in missing:
                continue
            p = _extract_price_by_keywords(text, kws)
            if p is not None:
                prices[name] = p
                missing.discard(name)

    # 第二轮：命中不足时，抓取部分正文再抽取
    if missing:
        fetch_count = 0
        for item in items:
            if not missing or fetch_count >= 10:
                break
            url = str(item.get("url", "") or "").strip()
            if not url:
                continue
            article_text = _fetch_article_text(url)
            if not article_text:
                continue
            fetch_count += 1
            for name, kws in markers:
                if name not in missing:
                    continue
                p = _extract_price_by_keywords(article_text, kws)
                if p is not None:
                    prices[name] = p
                    missing.discard(name)

    if missing:
        logger.info("煤价提取未命中项: %s", ", ".join(sorted(missing)))
    return prices


def _coal_price_snapshot_path() -> Path:
    return Path("data") / "coal_price_snapshot.json"


def _load_last_coal_prices() -> Dict[str, float]:
    path = _coal_price_snapshot_path()
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


def _save_coal_prices(prices: Dict[str, float]) -> None:
    path = _coal_price_snapshot_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"prices": prices}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning("写入煤价快照失败: %s", e)


def _fmt_delta(curr: float, prev: Optional[float]) -> str:
    if prev is None:
        return "（首日无对比）"
    diff = curr - prev
    if abs(diff) < 1e-9:
        return "（较上次 持平）"
    sign = "+" if diff > 0 else ""
    trend = "上涨" if diff > 0 else "下跌"
    return f"（较上次 {trend} {sign}{diff:.1f} 元/吨）"


def _build_wecom_coal_price_brief(processed: List[Dict]) -> str:
    """企业微信煤炭简报：主流港口/煤矿价格 + 与上次对比。"""
    from utils.time import get_today_date

    current = _extract_coal_prices(processed)
    previous = _load_last_coal_prices()
    if current:
        _save_coal_prices(current)

    port_keys = ["秦皇岛港", "曹妃甸港", "京唐港", "黄骅港"]
    pit_keys = ["榆林坑口", "鄂尔多斯坑口", "神木坑口", "府谷坑口"]

    lines = [f"**煤炭价格快报 - {get_today_date()}**", ""]
    lines.append("**港口煤价（元/吨）**")
    has_port = False
    for k in port_keys:
        if k in current:
            has_port = True
            lines.append(f"- {k}：{current[k]:.1f} {_fmt_delta(current[k], previous.get(k))}")
    if not has_port:
        lines.append("- 暂未从当日资讯中提取到明确港口价格")

    lines.append("")
    lines.append("**坑口煤价（元/吨）**")
    has_pit = False
    for k in pit_keys:
        if k in current:
            has_pit = True
            lines.append(f"- {k}：{current[k]:.1f} {_fmt_delta(current[k], previous.get(k))}")
    if not has_pit:
        lines.append("- 暂未从当日资讯中提取到明确坑口价格")

    # 补充 3 条关键信息（无链接）
    key_titles: List[str] = []
    for item in processed:
        title = _strip_links_and_shrink(str(item.get("title", "")), max_len=120)
        if title:
            key_titles.append(title)
        if len(key_titles) >= 3:
            break
    if key_titles:
        lines.append("")
        lines.append("**关键信息**")
        for i, t in enumerate(key_titles, start=1):
            lines.append(f"{i}. {t}")

    return "\n".join(lines).strip()


def _run_one_report(mode: str) -> bool:
    """跑单份报告：采集 -> 处理 -> 生成 -> 推送。成功返回 True。"""
    from config import settings

    all_items = collect_all_data(mode=mode)
    if not all_items:
        logger.warning("未采集到任何数据 [%s]，跳过", mode)
        return True
    processed = process_data(all_items)
    if not processed:
        logger.warning("处理后无有效数据 [%s]，跳过", mode)
        return True

    report_summary: Optional[str] = None
    report_reasoning = ""
    stock_analysis: Optional[str] = None
    if settings.GITHUB_TOKEN and mode != "coal":
        try:
            result = generate_report_summary_with_reasoning(processed)
            report_summary = result.get("summary") or None
            report_reasoning = result.get("reasoning") or ""
        except Exception as e:
            logger.warning("报告总结生成失败: %s", e)
        try:
            if mode in ("daily_intel", "stock"):
                stock_analysis = generate_stock_analysis(processed)
        except Exception as e:
            logger.warning("股票简析生成失败: %s", e)

    report_content: str
    report_is_markdown = False
    if mode == "daily_intel":
        data_sources = _collect_data_sources()
        report_content = build_html_report(
            processed,
            report_summary=report_summary,
            reasoning=report_reasoning,
            data_sources=data_sources,
            stock_analysis=stock_analysis,
        )
    elif mode == "stock":
        report_content = build_stock_report(processed, stock_analysis=stock_analysis)
        report_is_markdown = True
    elif mode == "coal":
        report_content = build_coal_report(processed)
        report_is_markdown = True
    else:
        data_sources = _collect_data_sources()
        report_content = build_html_report(
            processed,
            report_summary=report_summary,
            reasoning=report_reasoning,
            data_sources=data_sources,
            stock_analysis=stock_analysis,
        )

    push_channels: List[str]
    if mode == "coal":
        push_channels = getattr(settings, "COAL_PUSH_CHANNELS", None) or ["wecom"]
    else:
        push_channels = getattr(settings, "PUSH_CHANNELS", None) or ["email", "feishu"]

    email_ok = False
    for ch in push_channels:
        if ch == "email":
            to_send = report_content if not report_is_markdown else _markdown_to_html_body(report_content)
            email_ok = send_report(to_send)
        elif ch == "feishu":
            try:
                feishu_url = getattr(settings, "FEISHU_WEBHOOK_URL", "") or ""
                if feishu_url:
                    html_f = report_content if not report_is_markdown else _markdown_to_html_body(report_content)
                    body = (report_content if report_is_markdown else report_summary) or ""
                    send_report_to_feishu(html_f, report_summary=body or None)
            except Exception as e:
                logger.warning("飞书推送失败: %s", e)
        elif ch == "wecom":
            try:
                # 企业微信只推“文字性总结 + 关键信息”，避免链接和 HTML 噪音
                wecom_body = _build_wecom_brief(
                    mode=mode,
                    processed=processed,
                    report_summary=report_summary,
                    stock_analysis=stock_analysis,
                    fallback_html_or_md=report_content,
                )
                send_wecom(wecom_body or "今日报告已生成。")
            except Exception as e:
                logger.warning("企业微信推送失败: %s", e)

    if "email" in push_channels and not email_ok:
        return False
    return True


def main():
    """
    主函数：按 REPORT_MODE 采集、生成报告、推送。
    REPORT_MODE=both 时依次运行全球日报 + 煤炭日报（日报推邮件/飞书，煤炭仅推企业微信）。
    """
    from config import settings
    try:
        cfg_mode = getattr(settings, "REPORT_MODE", "daily_intel") or "daily_intel"
        logger.info("=" * 60)
        logger.info("Daily Global Intelligence Engine 启动 [REPORT_MODE=%s]", cfg_mode)
        logger.info("=" * 60)

        modes_to_run: List[str] = ["daily_intel", "coal"] if cfg_mode == "both" else [cfg_mode]
        email_failed = False

        for m in modes_to_run:
            logger.info("\n" + "=" * 60)
            logger.info("运行报告 [%s]", m)
            logger.info("=" * 60)
            if not _run_one_report(m):
                if "email" in (getattr(settings, "PUSH_CHANNELS", None) or ["email", "feishu"]):
                    email_failed = True

        if email_failed:
            logger.error("✗ 邮件发送失败")
            sys.exit(1)
        logger.info("\n" + "=" * 60)
        logger.info("✓ 任务完成")
        logger.info("=" * 60)
        sys.exit(0)

    except KeyboardInterrupt:
        logger.warning("\n用户中断程序")
        sys.exit(1)
    except Exception as e:
        logger.error("\n程序执行失败: %s", e, exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

