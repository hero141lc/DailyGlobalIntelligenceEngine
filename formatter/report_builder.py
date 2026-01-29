"""
报告生成器
按固定模板生成 HTML 邮件内容
"""
from typing import List, Dict
from datetime import datetime

from utils.logger import logger
from utils.time import get_today_date

# 每板块默认展示的缩略条数，其余在「点击展开」抽屉内
PREVIEW_COUNT = 3

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
    "美股快讯",
    "SEC监管",
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

def _render_one_item(item: Dict, compact: bool = False) -> str:
    """渲染单条：标题、摘要、来源、链接。compact 为 True 时只出一行缩略。"""
    title = item.get("title", "")
    summary = item.get("summary", item.get("content", ""))
    source = item.get("source", "")
    url = item.get("url", "")
    if compact:
        summary_short = (summary[:60] + "…") if summary and len(summary) > 60 else (summary or "")
        return f"""<li style="margin-bottom: 8px; padding-left: 16px; border-left: 3px solid #ecf0f1;">
                <p style="margin: 0; font-size: 14px; color: #34495e;"><strong>{title}</strong> {summary_short}</p>
                <p style="margin: 2px 0 0 0; font-size: 12px; color: #95a5a6;">来源：{source}{f' · <a href="{url}" style="color: #3498db;">原文</a>' if url else ''}</p>
            </li>"""
    return f"""<li style="margin-bottom: 15px; padding-left: 20px; border-left: 3px solid #ecf0f1;">
                <p style="margin: 0 0 5px 0; font-weight: bold; color: #34495e;">{title}</p>
                <p style="margin: 0 0 5px 0; color: #7f8c8d; font-size: 14px;">{summary}</p>
                <p style="margin: 0; font-size: 12px; color: #95a5a6;">（来源：{source}）{f'<a href="{url}" style="color: #3498db; text-decoration: none; margin-left: 10px;">查看原文</a>' if url else ''}</p>
            </li>"""


def format_category_section(category: str, items: List[Dict]) -> str:
    """
    格式化单个板块：默认折叠成抽屉，只展示前 PREVIEW_COUNT 条缩略，提示点击展开显示全部。
    """
    if not items:
        return ""
    n = len(items)
    preview_items = items[:PREVIEW_COUNT]
    html = f"""
    <div style="margin-bottom: 20px;">
        <h3 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; margin-bottom: 10px;">
            【{category}】
        </h3>
        <ul style="list-style-type: none; padding-left: 0;">
    """
    for item in preview_items:
        html += _render_one_item(item, compact=True)
    html += """
        </ul>
    """
    if n > PREVIEW_COUNT:
        html += f"""
        <details style="margin-top: 8px;">
            <summary style="cursor: pointer; color: #3498db; font-size: 13px;">▼ 点击展开显示本模块全部文章（共 {n} 条）</summary>
            <ul style="list-style-type: none; padding-left: 0; margin-top: 10px;">
        """
        for item in items:
            html += _render_one_item(item, compact=False)
        html += """
            </ul>
        </details>
        """
    else:
        html += f'<p style="margin: 6px 0 0 0; font-size: 12px; color: #95a5a6;">共 {n} 条</p>'
    html += """
    </div>
    """
    return html

def _format_index_table(indices: List[Dict]) -> str:
    """指数表格：名称、最新、涨跌幅，更像行情表。"""
    if not indices:
        return ""
    rows = []
    for item in indices:
        name = item.get("name") or item.get("title", "").split("：")[0]
        close = item.get("close")
        change_pct = item.get("change_pct", 0)
        url = item.get("url", "")
        close_str = f"{close:,.2f}" if close is not None else "—"
        color = "#27ae60" if change_pct >= 0 else "#c0392b"
        link = f'<a href="{url}" style="color:#3498db;text-decoration:none;">{name}</a>' if url else name
        rows.append(f'<tr><td style="padding:6px 10px;border-bottom:1px solid #eee;">{link}</td><td style="padding:6px 10px;border-bottom:1px solid #eee;text-align:right;">{close_str}</td><td style="padding:6px 10px;border-bottom:1px solid #eee;text-align:right;color:{color};font-weight:bold;">{change_pct:+.2f}%</td></tr>')
    return f"""
    <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <thead><tr style="background:#f8f9fa;"><th style="padding:8px 10px;text-align:left;">指数</th><th style="padding:8px 10px;text-align:right;">最新</th><th style="padding:8px 10px;text-align:right;">涨跌幅</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
    </table>"""


def _format_stock_row(item: Dict, label_style: str = "color:#27ae60;") -> str:
    """单只股票/涨跌一行：代码、涨跌幅、收盘（可选）、链接。"""
    title = item.get("title", "")
    symbol = item.get("symbol", "")
    change_pct = item.get("change_pct", 0)
    close = item.get("close")
    url = item.get("url", "")
    color = "#27ae60" if change_pct >= 0 else "#c0392b"
    link = f'<a href="{url}" style="color:#3498db;">{symbol or title}</a>' if url else (symbol or title)
    close_str = f" {close:,.2f}" if close is not None else ""
    return f'<tr><td style="padding:6px 10px;border-bottom:1px solid #eee;">{link}</td><td style="padding:6px 10px;text-align:right;color:{color};font-weight:bold;">{change_pct:+.2f}%</td><td style="padding:6px 10px;text-align:right;">{close_str}</td></tr>'


def format_stocks_section(items: List[Dict]) -> str:
    """
    美股市场板块：指数表格 + 大涨个股 + 今日涨跌一览，更像行情；默认折叠，仅展示指数表与 3 条缩略。
    """
    indices = [i for i in items if i.get("category") == "美股市场"]
    surge_stocks = [i for i in items if i.get("category") == "大涨个股"]
    daily_movers = [i for i in items if i.get("category") == "今日涨跌"]
    # 预览：指数表 + 最多 3 条其他（大涨或涨跌）
    preview_others = (surge_stocks + daily_movers)[:PREVIEW_COUNT]
    all_others = surge_stocks + daily_movers

    html = """
    <div style="margin-bottom: 20px;">
        <h3 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; margin-bottom: 10px;">
            【美股市场】
        </h3>
    """
    # 指数表格（始终展示）
    html += _format_index_table(indices)
    # 个股/涨跌预览：统一一张表，最多 PREVIEW_COUNT 条
    if preview_others:
        html += '<p style="margin:10px 0 4px 0;font-size:13px;color:#7f8c8d;">个股与涨跌预览</p>'
        html += '<table style="width:100%;border-collapse:collapse;font-size:13px;"><thead><tr style="background:#f8f9fa;"><th style="padding:6px 10px;text-align:left;">代码</th><th style="padding:6px 10px;text-align:right;">涨跌幅</th><th style="padding:6px 10px;text-align:right;">最新</th></tr></thead><tbody>'
        for item in preview_others:
            html += _format_stock_row(item)
        html += "</tbody></table>"
    # 若有多于 PREVIEW_COUNT 的个股/涨跌，加折叠抽屉
    if len(all_others) > PREVIEW_COUNT:
        html += f"""
        <details style="margin-top: 8px;">
            <summary style="cursor: pointer; color: #3498db; font-size: 13px;">▼ 点击展开显示本模块全部个股与涨跌（共 {len(all_others)} 条）</summary>
            <div style="margin-top: 10px;">
        """
        if surge_stocks:
            html += '<h4 style="color:#27ae60;margin:8px 0 4px 0;font-size:14px;">【大涨个股】</h4><table style="width:100%;border-collapse:collapse;font-size:13px;"><tbody>'
            for item in surge_stocks:
                html += _format_stock_row(item)
            html += "</tbody></table>"
        if daily_movers:
            html += '<h4 style="color:#34495e;margin:12px 0 4px 0;font-size:14px;">【今日涨跌一览】</h4><table style="width:100%;border-collapse:collapse;font-size:13px;"><tbody>'
            for item in daily_movers:
                html += _format_stock_row(item)
            html += "</tbody></table>"
        html += "</div></details>"
    html += "</div>"
    return html

def build_html_report(items: List[Dict], report_summary: str = None) -> str:
    """
    构建完整的 HTML 邮件报告
    
    Args:
        items: 所有数据项列表
        report_summary: 可选，报告最前面的「今日总结与展望」长段
    
    Returns:
        完整的 HTML 邮件内容
    """
    today = get_today_date()
    
    # 按类别分组
    grouped = group_by_category(items)
    
    # 总结段落（放在标题后、正文最前面）
    summary_block = ""
    if report_summary and report_summary.strip():
        summary_block = f"""
            <div style="margin-bottom: 28px; padding: 20px; background-color: #f8f9fa; border-left: 4px solid #3498db; border-radius: 4px;">
                <h3 style="color: #2c3e50; margin: 0 0 12px 0; font-size: 16px;">【今日总结与展望】</h3>
                <p style="margin: 0; color: #34495e; line-height: 1.7; font-size: 14px; white-space: pre-line;">{report_summary.strip()}</p>
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
    html += summary_block
    html += "\n    "
    
    # 按顺序输出各个板块
    for category in CATEGORY_ORDER:
        if category in grouped and grouped[category]:
            if category in ["美股市场", "大涨个股", "今日涨跌"]:
                # 特殊处理美股市场板块（含指数、大涨个股、今日涨跌一览）
                stocks_items = (
                    grouped.get("美股市场", []) +
                    grouped.get("大涨个股", []) +
                    grouped.get("今日涨跌", [])
                )
                html += format_stocks_section(stocks_items)
                if "大涨个股" in grouped:
                    del grouped["大涨个股"]
                if "今日涨跌" in grouped:
                    del grouped["今日涨跌"]
            else:
                html += format_category_section(category, grouped[category])
    
    # 输出其他未分类的板块
    for category, category_items in grouped.items():
        if category not in CATEGORY_ORDER:
            html += format_category_section(category, category_items)
    
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
        report_summary: 可选，报告最前面的「今日总结与展望」长段
    
    Returns:
        纯文本报告内容
    """
    today = get_today_date()
    grouped = group_by_category(items)
    
    text = f"📌 全球科技与金融情报速览（{today}）\n\n"
    text += "=" * 50 + "\n\n"
    if report_summary and report_summary.strip():
        text += "【今日总结与展望】\n"
        text += "-" * 30 + "\n"
        text += report_summary.strip() + "\n\n"
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
    
    text += "\n" + "=" * 50 + "\n"
    text += "本报告由 Daily Global Intelligence Engine 自动生成\n"
    
    return text

