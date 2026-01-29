"""
Daily Global Intelligence Engine
主程序入口
"""
import sys
from typing import List, Dict

from utils.logger import logger
from utils.dedup import deduplicate_items
from sources import energy, ai, space, fed, stocks
from sources import web_sources, commodities_military, rss_extra
from llm.github_llm import summarize_batch_unified, generate_report_summary
from formatter.report_builder import build_html_report
from mail.mailer import send_report

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
    
    # 1. 启动网页来源采集（独立线程、60 秒间隔、仿真请求头），主流程不等待
    logger.info("\n[1/8] 采集网页来源（X/马斯克/特朗普，独立线程已启动）...")
    web_thread, web_result_list = None, []
    try:
        web_thread, web_result_list = web_sources.start_collection_thread()
    except Exception as e:
        logger.error(f"✗ 网页来源线程启动失败: {e}")

    # 2. 采集能源/电力数据
    logger.info("\n[2/8] 采集能源/电力数据...")
    try:
        energy_items = energy.collect_all()
        all_items.extend(energy_items)
        logger.info(f"✓ 采集到 {len(energy_items)} 条能源/电力数据")
    except Exception as e:
        logger.error(f"✗ 能源/电力数据采集失败: {e}")

    # 3. 采集黄金、石油、军事
    logger.info("\n[3/8] 采集黄金/石油/军事...")
    try:
        cm_items = commodities_military.collect_all()
        all_items.extend(cm_items)
        logger.info(f"✓ 采集到 {len(cm_items)} 条黄金/石油/军事数据")
    except Exception as e:
        logger.error(f"✗ 黄金/石油/军事采集失败: {e}")
    
    # 4. 采集 AI 应用数据
    logger.info("\n[4/8] 采集 AI 应用数据...")
    try:
        ai_items = ai.collect_all()
        all_items.extend(ai_items)
        logger.info(f"✓ 采集到 {len(ai_items)} 条 AI 应用数据")
    except Exception as e:
        logger.error(f"✗ AI 应用数据采集失败: {e}")
    
    # 5. 采集商业航天数据
    logger.info("\n[5/8] 采集商业航天数据...")
    try:
        space_items = space.collect_all()
        all_items.extend(space_items)
        logger.info(f"✓ 采集到 {len(space_items)} 条商业航天数据")
    except Exception as e:
        logger.error(f"✗ 商业航天数据采集失败: {e}")
    
    # 6. 采集美联储数据
    logger.info("\n[6/8] 采集美联储数据...")
    try:
        fed_items = fed.collect_all()
        all_items.extend(fed_items)
        logger.info(f"✓ 采集到 {len(fed_items)} 条美联储数据")
    except Exception as e:
        logger.error(f"✗ 美联储数据采集失败: {e}")
    
    # 7. 采集美股市场数据（Stooq 指数 + 大涨个股）
    logger.info("\n[7/8] 采集美股市场数据...")
    try:
        stocks_items = stocks.collect_all()
        all_items.extend(stocks_items)
        logger.info(f"✓ 采集到 {len(stocks_items)} 条美股市场数据")
    except Exception as e:
        logger.error(f"✗ 美股市场数据采集失败: {e}")

    # 8. 采集美股快讯 + SEC 监管（CNBC、MarketWatch、Seeking Alpha、SEC）
    logger.info("\n[8/8] 采集美股快讯与 SEC 监管...")
    try:
        rss_extra_items = rss_extra.collect_all()
        all_items.extend(rss_extra_items)
        logger.info(f"✓ 采集到 {len(rss_extra_items)} 条美股快讯/SEC 监管")
    except Exception as e:
        logger.error(f"✗ 美股快讯/SEC 采集失败: {e}")

    # 等待网页来源线程结束并合并结果
    if web_thread is not None and web_thread.is_alive():
        logger.info("\n等待网页来源采集线程结束...")
        web_thread.join()
    if web_result_list:
        all_items = web_result_list + all_items
        logger.info(f"✓ 网页来源采集到 {len(web_result_list)} 条（已合并）")
    
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
        
        # 3. 生成报告总结（一段话）
        logger.info("\n" + "=" * 60)
        logger.info("生成报告与总结")
        logger.info("=" * 60)
        report_summary = None
        try:
            from config import settings
            if settings.GITHUB_TOKEN:
                report_summary = generate_report_summary(processed_items)
                if report_summary:
                    logger.info("✓ 报告总结生成完成")
        except Exception as e:
            logger.warning(f"报告总结生成失败（不影响报告）: {e}")
        
        html_report = build_html_report(processed_items, report_summary=report_summary)
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

