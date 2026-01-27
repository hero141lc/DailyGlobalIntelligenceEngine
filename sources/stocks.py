"""
美股市场数据采集模块
采集主要指数和大涨个股（≥7%）
使用 Stooq 获取指数数据（更稳定），个股允许失败
"""
import requests
import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime, timezone

from config import settings
from utils.logger import logger
from utils.time import get_today_date

def get_index_data_stooq(symbol: str, name: str) -> Optional[Dict]:
    """
    使用 Stooq 获取指数数据（更稳定，无反爬）
    
    Args:
        symbol: 股票代码（Stooq 格式：^GSPC）
        name: 指数名称
    
    Returns:
        指数数据字典，失败返回 None
    """
    try:
        # Stooq API（更稳定）
        # 格式：https://stooq.com/q/l/?s=^GSPC&f=sd2t2ohlcv&h&e=csv
        stooq_symbol = symbol.replace("^", "")  # 去掉 ^ 符号
        url = f"https://stooq.com/q/l/?s={stooq_symbol}&f=sd2t2ohlcv&h&e=csv"
        
        response = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        response.raise_for_status()
        
        # 解析 CSV
        lines = response.text.strip().split('\n')
        if len(lines) < 2:
            return None
        
        # 获取最新两行数据
        latest_line = lines[-1].split(',')
        previous_line = lines[-2].split(',') if len(lines) > 2 else latest_line
        
        try:
            latest_close = float(latest_line[5])  # Close 价格
            previous_close = float(previous_line[5])
            
            if previous_close == 0:
                return None
            
            change_pct = ((latest_close - previous_close) / previous_close) * 100
            
            return {
                "category": "美股市场",
                "title": f"{name}：{change_pct:+.2f}%",
                "content": f"{name} 收盘 {latest_close:.2f}，涨跌幅 {change_pct:+.2f}%",
                "source": "Stooq",
                "url": f"https://stooq.com/q/?s={stooq_symbol}",
                "published_at": get_today_date(),
            }
        except (ValueError, IndexError) as e:
            logger.debug(f"解析 Stooq 数据失败 {symbol}: {e}")
            return None
            
    except Exception as e:
        logger.debug(f"获取 Stooq 指数数据失败 {symbol}: {e}")
        return None

def get_index_data_yfinance(symbol: str, name: str) -> Optional[Dict]:
    """
    使用 yfinance 获取指数数据（备用方案）
    
    Args:
        symbol: 股票代码
        name: 指数名称
    
    Returns:
        指数数据字典，失败返回 None
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2d", timeout=10)
        
        if hist.empty or len(hist) == 0:
            return None
        
        latest = hist.iloc[-1]
        previous = hist.iloc[-2] if len(hist) > 1 else latest
        
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
        logger.debug(f"获取 yfinance 指数数据失败 {symbol}: {e}")
        return None

def collect_index_data() -> List[Dict]:
    """
    采集主要指数数据（优先使用 Stooq，失败则尝试 yfinance）
    
    Returns:
        指数数据列表
    """
    indices: List[Dict] = []
    
    for name, symbol in settings.STOCK_INDICES.items():
        # 优先使用 Stooq
        data = get_index_data_stooq(symbol, name)
        if not data:
            # Stooq 失败，尝试 yfinance
            data = get_index_data_yfinance(symbol, name)
        
        if data:
            indices.append(data)
    
    return indices

def get_surge_stocks(threshold: float = 7.0) -> List[Dict]:
    """
    获取大涨个股（涨幅≥阈值）
    只取前 20 大市值股票，允许失败，不阻断流程
    
    Args:
        threshold: 涨幅阈值（百分比）
    
    Returns:
        大涨个股列表
    """
    surge_stocks: List[Dict] = []
    
    # 只取前 20 大市值股票（减少请求，提高成功率）
    popular_symbols = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
        "BRK-B", "V", "UNH", "JNJ", "WMT", "JPM", "MA", "PG",
        "HD", "DIS", "BAC", "ADBE", "NFLX"
    ]
    
    for symbol in popular_symbols:
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="2d", timeout=10)
            
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
                    "change_pct": change_pct,
                })
        except Exception as e:
            # 个股失败不影响整体流程
            logger.debug(f"获取股票 {symbol} 数据失败: {e}")
            continue
    
    # 按涨幅排序
    surge_stocks.sort(key=lambda x: x.get("change_pct", 0), reverse=True)
    
    logger.info(f"发现 {len(surge_stocks)} 只大涨个股（≥{threshold}%）")
    return surge_stocks

def collect_all() -> List[Dict]:
    """
    采集所有美股市场数据
    
    Returns:
        所有数据列表（指数 + 大涨个股）
    """
    all_data: List[Dict] = []
    
    # 采集指数数据（允许失败）
    try:
        indices = collect_index_data()
        all_data.extend(indices)
        logger.info(f"成功获取 {len(indices)} 个指数数据")
    except Exception as e:
        logger.warning(f"采集指数数据失败: {e}（不影响整体流程）")
    
    # 采集大涨个股（允许失败）
    try:
        surge_stocks = get_surge_stocks(settings.STOCK_SURGE_THRESHOLD)
        all_data.extend(surge_stocks)
        logger.info(f"成功获取 {len(surge_stocks)} 只大涨个股")
    except Exception as e:
        logger.warning(f"采集大涨个股失败: {e}（不影响整体流程）")
    
    return all_data
