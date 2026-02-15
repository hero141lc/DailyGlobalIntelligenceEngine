"""
Daily Global Intelligence Engine
主程序入口
"""
import sys
from typing import List, Dict

from utils.logger import logger
from utils.dedup import deduplicate_items
from utils import google_rss
from sources import energy, ai, space, fed, stocks
from sources import web_sources, commodities_military, rss_extra, twitter
from llm.github_llm import summarize_batch_unified, generate_report_summary_with_reasoning, generate_stock_analysis
from formatter.report_builder import build_html_report
from mail.mailer import send_report


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


def collect_all_data() -> List[Dict]:
    """
    采集所有数据源的数据
    
    Returns:
        所有数据项列表
    """
    all_items: List[Dict] = []
    
    logger.info("=" * 60)
    logger.info("开始数据采集")
    logger.info("=" * 60)
    
    # 1. 启动网页来源与 Google News RSS 采集（独立线程），主流程不等待
    logger.info("\n[1/10] 采集网页来源（X/马斯克/特朗普，独立线程已启动）...")
    web_thread, web_result_list = None, []
    try:
        web_thread, web_result_list = web_sources.start_collection_thread()
    except Exception as e:
        logger.error(f"✗ 网页来源线程启动失败: {e}")
    logger.info("[2/10] 采集 Google News RSS（世界新闻，独立线程已启动）...")
    google_rss_thread, google_rss_result_list = None, []
    try:
        google_rss_thread, google_rss_result_list = google_rss.start_google_rss_collection_thread()
    except Exception as e:
        logger.error(f"✗ Google RSS 线程启动失败: {e}")

    # 3. 采集能源/电力数据
    logger.info("\n[3/10] 采集能源/电力数据...")
    try:
        energy_items = energy.collect_all()
        all_items.extend(energy_items)
        logger.info(f"✓ 采集到 {len(energy_items)} 条能源/电力数据")
    except Exception as e:
        logger.error(f"✗ 能源/电力数据采集失败: {e}")

    # 4. 采集黄金、石油、军事
    logger.info("\n[4/10] 采集黄金/石油/军事...")
    try:
        cm_items = commodities_military.collect_all()
        all_items.extend(cm_items)
        logger.info(f"✓ 采集到 {len(cm_items)} 条黄金/石油/军事数据")
    except Exception as e:
        logger.error(f"✗ 黄金/石油/军事采集失败: {e}")
    
    # 5. 采集 AI 应用数据
    logger.info("\n[5/10] 采集 AI 应用数据...")
    try:
        ai_items = ai.collect_all()
        all_items.extend(ai_items)
        logger.info(f"✓ 采集到 {len(ai_items)} 条 AI 应用数据")
    except Exception as e:
        logger.error(f"✗ AI 应用数据采集失败: {e}")
    
    # 6. 采集商业航天数据
    logger.info("\n[6/10] 采集商业航天数据...")
    try:
        space_items = space.collect_all()
        all_items.extend(space_items)
        logger.info(f"✓ 采集到 {len(space_items)} 条商业航天数据")
    except Exception as e:
        logger.error(f"✗ 商业航天数据采集失败: {e}")
    
    # 7. 采集美联储数据
    logger.info("\n[7/10] 采集美联储数据...")
    try:
        fed_items = fed.collect_all()
        all_items.extend(fed_items)
        logger.info(f"✓ 采集到 {len(fed_items)} 条美联储数据")
    except Exception as e:
        logger.error(f"✗ 美联储数据采集失败: {e}")
    
    # 8. 采集美股市场数据（Stooq 指数 + 大涨个股）
    logger.info("\n[8/10] 采集美股市场数据...")
    try:
        stocks_items = stocks.collect_all()
        all_items.extend(stocks_items)
        logger.info(f"✓ 采集到 {len(stocks_items)} 条美股市场数据")
    except Exception as e:
        logger.error(f"✗ 美股市场数据采集失败: {e}")

    # 9. 采集美股快讯 + SEC 监管（CNBC、MarketWatch、Seeking Alpha、SEC）
    logger.info("\n[9/10] 采集美股快讯与 SEC 监管...")
    try:
        rss_extra_items = rss_extra.collect_all()
        all_items.extend(rss_extra_items)
        logger.info(f"✓ 采集到 {len(rss_extra_items)} 条美股快讯/SEC 监管")
    except Exception as e:
        logger.error(f"✗ 美股快讯/SEC 采集失败: {e}")

    # 10. 马斯克/特朗普 Google News RSS（与网页抓取并存）
    logger.info("\n[10/10] 采集马斯克/特朗普 RSS（Google News）...")
    twitter_rss_items: List[Dict] = []
    try:
        twitter_rss_items = twitter.collect_all()
        logger.info(f"✓ 采集到 {len(twitter_rss_items)} 条马斯克/特朗普 RSS")
    except Exception as e:
        logger.error(f"✗ 马斯克/特朗普 RSS 采集失败: {e}")

    # 等待网页来源与 Google RSS 线程结束并合并结果
    if web_thread is not None and web_thread.is_alive():
        logger.info("\n等待网页来源采集线程结束...")
        web_thread.join()
    if google_rss_thread is not None and google_rss_thread.is_alive():
        logger.info("等待 Google News RSS 采集线程结束...")
        google_rss_thread.join()
    if web_result_list:
        logger.info(f"✓ 网页来源采集到 {len(web_result_list)} 条（已合并）")
    if google_rss_result_list:
        logger.info(f"✓ Google News RSS 采集到 {len(google_rss_result_list)} 条（已合并）")
    all_items = web_result_list + google_rss_result_list + twitter_rss_items + all_items
    
    logger.info("\n" + "=" * 60)
    logger.info(f"数据采集完成，共采集 {len(all_items)} 条数据")
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

def main():
    """
    主函数
    """
    try:
        logger.info("=" * 60)
        logger.info("Daily Global Intelligence Engine 启动")
        logger.info("=" * 60)
        
        # 1. 采集数据
        all_items = collect_all_data()
        
        if not all_items:
            logger.warning("未采集到任何数据，退出程序")
            logger.warning("注意：不会发送空邮件")
            sys.exit(0)
        
        # 2. 处理数据
        processed_items = process_data(all_items)
        
        if not processed_items:
            logger.warning("处理后无有效数据，退出程序")
            logger.warning("注意：不会发送空邮件")
            sys.exit(0)
        
        # 3. 生成报告总结（DeepSeek-R1 带思考，单次约 4000 token）
        logger.info("\n" + "=" * 60)
        logger.info("生成报告与总结")
        logger.info("=" * 60)
        report_summary = None
        report_reasoning = ""
        try:
            from config import settings
            if settings.GITHUB_TOKEN:
                result = generate_report_summary_with_reasoning(processed_items)
                report_summary = result.get("summary") or None
                report_reasoning = result.get("reasoning") or ""
                if report_summary:
                    logger.info("✓ 报告总结生成完成")
        except Exception as e:
            logger.warning(f"报告总结生成失败（不影响报告）: {e}")

        # 股票简析（涨跌原因、可关注、建议规避）
        stock_analysis = None
        try:
            if settings.GITHUB_TOKEN:
                stock_analysis = generate_stock_analysis(processed_items)
                if stock_analysis:
                    logger.info("✓ 股票简析生成完成")
        except Exception as e:
            logger.warning(f"股票简析生成失败（不影响报告）: {e}")

        # 收集数据来源列表（用于报告内默认折叠展示）
        data_sources = _collect_data_sources()

        html_report = build_html_report(
            processed_items,
            report_summary=report_summary,
            reasoning=report_reasoning,
            data_sources=data_sources,
            stock_analysis=stock_analysis,
        )
        logger.info("✓ HTML 报告生成完成")
        
        # 4. 发送邮件
        logger.info("\n" + "=" * 60)
        logger.info("发送邮件")
        logger.info("=" * 60)
        
        success = send_report(html_report)
        
        if success:
            logger.info("\n" + "=" * 60)
            logger.info("✓ 任务完成！邮件已成功发送")
            logger.info("=" * 60)
            sys.exit(0)
        else:
            logger.error("\n" + "=" * 60)
            logger.error("✗ 邮件发送失败")
            logger.error("=" * 60)
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.warning("\n用户中断程序")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n程序执行失败: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

