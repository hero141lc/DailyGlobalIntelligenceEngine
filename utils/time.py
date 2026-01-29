"""
时间处理工具
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

def get_today_date() -> str:
    """
    获取今天的日期字符串（YYYY-MM-DD）
    
    Returns:
        日期字符串
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def parse_date(date_str: str) -> Optional[datetime]:
    """
    解析日期字符串，支持多种格式
    
    Args:
        date_str: 日期字符串
    
    Returns:
        datetime 对象，解析失败返回 None
    """
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S %z",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    # 尝试使用 dateutil 解析
    try:
        from dateutil import parser
        return parser.parse(date_str)
    except Exception:
        pass
    
    return None

def is_today(date_str: str) -> bool:
    """
    判断日期字符串是否为今天
    
    Args:
        date_str: 日期字符串
    
    Returns:
        是否为今天
    """
    parsed = parse_date(date_str)
    if not parsed:
        return False
    
    # 转换为 UTC 时区
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    
    today = datetime.now(timezone.utc).date()
    return parsed.date() == today


def is_today_or_yesterday(date_str: str) -> bool:
    """
    判断日期字符串是否为今天或昨天（用于石油/军事等 RSS 时区差异时多收一些条目）。
    """
    parsed = parse_date(date_str)
    if not parsed:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    today = now.date()
    yesterday = (now - timedelta(days=1)).date()
    return parsed.date() in (today, yesterday)


def format_date_for_display(dt: datetime) -> str:
    """
    格式化日期用于显示
    
    Args:
        dt: datetime 对象
    
    Returns:
        格式化后的日期字符串
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%d")

