"""
美股市场数据采集模块
采集主要指数和大涨个股（≥7%）
"""
import yfinance as yf
import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime, timezone

from config import settings
from utils.logger import logger
from utils.time import get_today_date

def get_index_data(symbol: str, name: str) -> Optional[Dict]:
    """
    获取指数数据
    
    Args:
        symbol: 股票代码
        name: 指数名称
    
    Returns:
        指数数据字典，失败返回 None
    """
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2d")
        
        if hist.empty:
            return None
        
        # 获取最新两天的数据
        latest = hist.iloc[-1]
        previous = hist.iloc[-2] if len(hist) > 1 else latest
        
        # 计算涨跌幅（避免除零错误）
        if previous["Close"] == 0 or pd.isna(previous["Close"]):
            return None
        change_pct = ((latest["Close"] - previous["Close"]) / previous["Close"]) * 100
        
        return {
            "category": "美股市场",
            "title": f"{name}：{change_pct:+.2f}%",
            "content": f"{name} 收盘 {latest['Close']:.2f}，涨跌幅 {change_pct:+.2f}%",
            "source": "Yahoo Finance",
            "url": f"https://finance.yahoo.com/quote/{symbol}",
            "published_at": get_today_date(),
        }
    except Exception as e:
        logger.warning(f"获取指数数据失败 {symbol}: {e}")
        return None

def get_surge_stocks(threshold: float = 7.0) -> List[Dict]:
    """
    获取大涨个股（涨幅≥阈值）
    
    Args:
        threshold: 涨幅阈值（百分比）
    
    Returns:
        大涨个股列表
    """
    surge_stocks: List[Dict] = []
    
    try:
        # 获取热门股票列表（使用 S&P 500 成分股）
        # 这里简化处理，实际可以获取更多股票
        popular_symbols = [
            "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
            "BRK-B", "V", "UNH", "JNJ", "WMT", "JPM", "MA", "PG",
            "HD", "DIS", "BAC", "ADBE", "NFLX", "CRM", "PYPL", "INTC",
            "CMCSA", "PEP", "TMO", "COST", "AVGO", "CSCO", "ABT"
        ]
        
        for symbol in popular_symbols:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="2d")
                
                if hist.empty or len(hist) < 2:
                    continue
                
                latest = hist.iloc[-1]
                previous = hist.iloc[-2]
                
                # 计算涨跌幅（避免除零错误）
                if previous["Close"] == 0 or pd.isna(previous["Close"]):
                    continue
                change_pct = ((latest["Close"] - previous["Close"]) / previous["Close"]) * 100
                
                # 只保留涨幅≥阈值的股票
                if change_pct >= threshold:
                    # 尝试获取新闻标题作为原因
                    reason = "市场表现强劲"
                    try:
                        news = ticker.news
                        if news and len(news) > 0:
                            # 获取最新新闻标题
                            latest_news = news[0]
                            reason = latest_news.get("title", reason)
                    except Exception:
                        pass
                    
                    stock_name = ticker.info.get("longName", symbol)
                    
                    surge_stocks.append({
                        "category": "大涨个股",
                        "title": f"{symbol} ({stock_name}) +{change_pct:.2f}%",
                        "content": f"{stock_name} ({symbol}) 涨幅 {change_pct:+.2f}%，原因：{reason}",
                        "source": "Yahoo Finance",
                        "url": f"https://finance.yahoo.com/quote/{symbol}",
                        "published_at": get_today_date(),
                        "change_pct": change_pct,  # 额外字段用于排序
                    })
            except Exception as e:
                logger.debug(f"获取股票 {symbol} 数据失败: {e}")
                continue
        
        # 按涨幅排序
        surge_stocks.sort(key=lambda x: x.get("change_pct", 0), reverse=True)
        
        logger.info(f"发现 {len(surge_stocks)} 只大涨个股（≥{threshold}%）")
    except Exception as e:
        logger.error(f"获取大涨个股失败: {e}")
    
    return surge_stocks

def collect_index_data() -> List[Dict]:
    """
    采集主要指数数据
    
    Returns:
        指数数据列表
    """
    indices: List[Dict] = []
    
    for name, symbol in settings.STOCK_INDICES.items():
        data = get_index_data(symbol, name)
        if data:
            indices.append(data)
    
    return indices

def collect_all() -> List[Dict]:
    """
    采集所有美股市场数据
    
    Returns:
        所有数据列表（指数 + 大涨个股）
    """
    all_data: List[Dict] = []
    
    # 采集指数数据
    try:
        indices = collect_index_data()
        all_data.extend(indices)
    except Exception as e:
        logger.error(f"采集指数数据失败: {e}")
    
    # 采集大涨个股
    try:
        surge_stocks = get_surge_stocks(settings.STOCK_SURGE_THRESHOLD)
        all_data.extend(surge_stocks)
    except Exception as e:
        logger.error(f"采集大涨个股失败: {e}")
    
    return all_data

