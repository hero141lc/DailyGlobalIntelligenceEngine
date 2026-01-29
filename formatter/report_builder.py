"""
报告生成器
按固定模板生成 HTML 邮件内容
"""
from typing import List, Dict
from datetime import datetime

from utils.logger import logger
from utils.time import get_today_date

# 板块顺序定义
CATEGORY_ORDER = [
    "马斯克",
    "特朗普",
    "能源/电力",
    "黄金",
    "石油",
    "军事",
    "AI 应用",
    "商业航天/星链",
    "美联储",
    "美股市场",
    "大涨个股",
]

def group_by_category(items: List[Dict]) -> Dict[str, List[Dict]]:
    """
    按类别分组数据项
    
    Args:
        items: 数据项列表
    
    Returns:
        按类别分组的字典
    """
    grouped: Dict[str, List[Dict]] = {}
    
    for item in items:
        category = item.get("category", "未分类")
        if category not in grouped:
            grouped[category] = []
        grouped[category].append(item)
    
    return grouped

def format_category_section(category: str, items: List[Dict]) -> str:
    """
    格式化单个板块的 HTML
    
    Args:
        category: 板块名称
        items: 该板块的数据项列表
    
    Returns:
        HTML 字符串
    """
    if not items:
        return ""
    
    html = f"""
    <div style="margin-bottom: 20px;">
        <h3 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; margin-bottom: 10px;">
            【{category}】
        </h3>
        <ul style="list-style-type: none; padding-left: 0;">
    """
    
    for item in items:
        title = item.get("title", "")
        summary = item.get("summary", item.get("content", ""))
        source = item.get("source", "")
        url = item.get("url", "")
        
        html += f"""
            <li style="margin-bottom: 15px; padding-left: 20px; border-left: 3px solid #ecf0f1;">
                <p style="margin: 0 0 5px 0; font-weight: bold; color: #34495e;">
                    {title}
                </p>
                <p style="margin: 0 0 5px 0; color: #7f8c8d; font-size: 14px;">
                    {summary}
                </p>
                <p style="margin: 0; font-size: 12px; color: #95a5a6;">
                    （来源：{source}）
                    {f'<a href="{url}" style="color: #3498db; text-decoration: none; margin-left: 10px;">查看原文</a>' if url else ''}
                </p>
            </li>
        """
    
    html += """
        </ul>
    </div>
    """
    
    return html

def format_stocks_section(items: List[Dict]) -> str:
    """
    格式化美股市场板块（特殊处理）
    
    Args:
        items: 数据项列表
    
    Returns:
        HTML 字符串
    """
    # 分离指数和大涨个股
    indices = [item for item in items if item.get("category") == "美股市场"]
    surge_stocks = [item for item in items if item.get("category") == "大涨个股"]
    
    html = """
    <div style="margin-bottom: 20px;">
        <h3 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; margin-bottom: 10px;">
            【美股市场】
        </h3>
    """
    
    # 指数部分
    if indices:
        html += '<div style="margin-bottom: 15px;">'
        for item in indices:
            title = item.get("title", "")
            html += f'<p style="margin: 5px 0; color: #34495e; font-weight: bold;">• {title}</p>'
        html += "</div>"
    
    # 大涨个股部分
    if surge_stocks:
        html += """
        <div style="margin-top: 15px;">
            <h4 style="color: #27ae60; margin-bottom: 10px;">【大涨个股】</h4>
            <ul style="list-style-type: none; padding-left: 0;">
        """
        
        for item in surge_stocks:
            title = item.get("title", "")
            content = item.get("summary", item.get("content", ""))
            source = item.get("source", "")
            url = item.get("url", "")
            
            html += f"""
                <li style="margin-bottom: 12px; padding-left: 20px; border-left: 3px solid #27ae60;">
                    <p style="margin: 0 0 5px 0; font-weight: bold; color: #27ae60;">
                        {title}
                    </p>
                    <p style="margin: 0 0 5px 0; color: #7f8c8d; font-size: 14px;">
                        {content}
                    </p>
                    <p style="margin: 0; font-size: 12px; color: #95a5a6;">
                        （来源：{source}）
                        {f'<a href="{url}" style="color: #3498db; text-decoration: none; margin-left: 10px;">查看详情</a>' if url else ''}
                    </p>
                </li>
            """
        
        html += """
            </ul>
        </div>
        """
    
    html += "</div>"
    return html

def build_html_report(items: List[Dict], report_summary: str = None) -> str:
    """
    构建完整的 HTML 邮件报告
    
    Args:
        items: 所有数据项列表
        report_summary: 可选，报告末尾的「今日总结」一段话
    
    Returns:
        完整的 HTML 邮件内容
    """
    today = get_today_date()
    
    # 按类别分组
    grouped = group_by_category(items)
    
    # 总结段落（在页脚前）
    summary_block = ""
    if report_summary and report_summary.strip():
        summary_block = f"""
            <div style="margin-top: 24px; margin-bottom: 20px; padding: 16px; background-color: #f8f9fa; border-left: 4px solid #3498db; border-radius: 4px;">
                <h3 style="color: #2c3e50; margin: 0 0 10px 0; font-size: 16px;">【今日总结】</h3>
                <p style="margin: 0; color: #34495e; line-height: 1.6; font-size: 14px;">{report_summary.strip()}</p>
            </div>
        """
    
    # 构建 HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>全球科技与金融情报速览 - {today}</title>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; background-color: #f5f5f5;">
        <div style="background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <h1 style="color: #2c3e50; text-align: center; margin-bottom: 30px; border-bottom: 3px solid #3498db; padding-bottom: 15px;">
                📌 全球科技与金融情报速览（{today}）
            </h1>
    """
    
    # 按顺序输出各个板块
    for category in CATEGORY_ORDER:
        if category in grouped and grouped[category]:
            if category in ["美股市场", "大涨个股"]:
                # 特殊处理美股市场板块
                stocks_items = grouped.get("美股市场", []) + grouped.get("大涨个股", [])
                html += format_stocks_section(stocks_items)
                # 避免重复输出
                if "大涨个股" in grouped:
                    del grouped["大涨个股"]
            else:
                html += format_category_section(category, grouped[category])
    
    # 输出其他未分类的板块
    for category, category_items in grouped.items():
        if category not in CATEGORY_ORDER:
            html += format_category_section(category, category_items)
    
    html += summary_block
    html += """
            <div style="margin-top: 30px; padding-top: 20px; border-top: 2px solid #ecf0f1; text-align: center; color: #95a5a6; font-size: 12px;">
                <p>本报告由 Daily Global Intelligence Engine 自动生成</p>
                <p>数据来源：公开 RSS 源、Yahoo Finance、xcancel/Nitter 等</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html

def build_text_report(items: List[Dict], report_summary: str = None) -> str:
    """
    构建纯文本报告（备用）
    
    Args:
        items: 所有数据项列表
        report_summary: 可选，报告末尾的「今日总结」一段话
    
    Returns:
        纯文本报告内容
    """
    today = get_today_date()
    grouped = group_by_category(items)
    
    text = f"📌 全球科技与金融情报速览（{today}）\n\n"
    text += "=" * 50 + "\n\n"
    
    for category in CATEGORY_ORDER:
        if category in grouped and grouped[category]:
            text += f"【{category}】\n"
            text += "-" * 30 + "\n"
            
            for item in grouped[category]:
                title = item.get("title", "")
                summary = item.get("summary", item.get("content", ""))
                source = item.get("source", "")
                
                text += f"• {title}\n"
                text += f"  {summary}\n"
                text += f"  （来源：{source}）\n\n"
            
            text += "\n"
    
    if report_summary and report_summary.strip():
        text += "\n【今日总结】\n"
        text += "-" * 30 + "\n"
        text += report_summary.strip() + "\n\n"
    
    text += "\n" + "=" * 50 + "\n"
    text += "本报告由 Daily Global Intelligence Engine 自动生成\n"
    
    return text

