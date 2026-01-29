"""
美股市场数据采集模块
采集主要指数和大涨个股（≥7%）
完全使用 Stooq API（无反爬，更稳定）
"""
import time
import requests
import csv
import io
from typing import List, Dict, Optional
from datetime import datetime, timezone

from config import settings
from utils.logger import logger
from utils.time import get_today_date

STOOQ_RETRIES = 3  # Stooq 请求失败时重试次数

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
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = None
        for attempt in range(1, STOOQ_RETRIES + 1):
            try:
                response = requests.get(url, timeout=15, headers=headers)
                response.raise_for_status()
                break
            except Exception as e:
                if attempt < STOOQ_RETRIES:
                    time.sleep(2 * attempt)
                    logger.warning(f"Stooq 指数请求失败 {symbol} (第 {attempt}/{STOOQ_RETRIES} 次): {e}，重试中")
                else:
                    raise
        if not response:
            return None
        # 解析 CSV（Stooq 休市时可能只有表头+1 行，用该行作最新价，涨跌 0%）
        csv_content = response.text.strip()
        if not csv_content:
            return _get_index_fallback_yahoo(symbol, name)
        csv_reader = csv.reader(io.StringIO(csv_content))
        rows = list(csv_reader)
        if len(rows) < 2:
            return _get_index_fallback_yahoo(symbol, name)
        latest_row = rows[-1]
        previous_row = rows[-2] if len(rows) > 2 else latest_row
        try:
            # CSV：Symbol,Date,Time,Open,High,Low,Close,Volume
            latest_close = float(latest_row[6])
            previous_close = float(previous_row[6])
            if previous_close == 0:
                return _get_index_fallback_yahoo(symbol, name)
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
            return _get_index_fallback_yahoo(symbol, name)
    except Exception as e:
        logger.debug(f"获取 Stooq 指数数据失败 {symbol}: {e}")
        return _get_index_fallback_yahoo(symbol, name)


def _get_index_fallback_yahoo(symbol: str, name: str) -> Optional[Dict]:
    """Stooq 无数据时用 Yahoo 取指数（仅指数，无个股）。"""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d")
        if hist is None or hist.empty or len(hist) < 2:
            return None
        latest = hist.iloc[-1]
        prev = hist.iloc[-2]
        close = float(latest["Close"])
        prev_close = float(prev["Close"])
        if prev_close == 0:
            return None
        change_pct = ((close - prev_close) / prev_close) * 100
        stooq_symbol = symbol.replace("^", "")
        return {
            "category": "美股市场",
            "title": f"{name}：{change_pct:+.2f}%",
            "content": f"{name} 收盘 {close:.2f}，涨跌幅 {change_pct:+.2f}%",
            "source": "Yahoo Finance",
            "url": f"https://stooq.com/q/?s={stooq_symbol}",
            "published_at": get_today_date(),
        }
    except Exception as e:
        logger.debug(f"Yahoo 指数回退失败 {symbol}: {e}")
        return None

def get_stock_data_stooq(symbol: str) -> Optional[Dict]:
    """
    使用 Stooq 获取个股数据
    
    Args:
        symbol: 股票代码（如 AAPL）
    
    Returns:
        股票数据字典，失败返回 None
    """
    try:
        url = f"https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=csv"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = None
        for attempt in range(1, STOOQ_RETRIES + 1):
            try:
                response = requests.get(url, timeout=15, headers=headers)
                response.raise_for_status()
                break
            except Exception as e:
                if attempt < STOOQ_RETRIES:
                    time.sleep(2 * attempt)
                    logger.warning(f"Stooq 个股请求失败 {symbol} (第 {attempt}/{STOOQ_RETRIES} 次): {e}，重试中")
                else:
                    raise
        if not response:
            return None
        csv_content = response.text.strip()
        if not csv_content:
            return None
        
        csv_reader = csv.reader(io.StringIO(csv_content))
        rows = list(csv_reader)
        
        if len(rows) < 2:
            return None
        latest_row = rows[-1]
        previous_row = rows[-2] if len(rows) > 2 else latest_row
        try:
            latest_close = float(latest_row[6])
            previous_close = float(previous_row[6])
            if previous_close == 0:
                return None
            change_pct = ((latest_close - previous_close) / previous_close) * 100
            return {
                "symbol": symbol,
                "close": latest_close,
                "change_pct": change_pct,
            }
        except (ValueError, IndexError):
            return None
    except Exception as e:
        logger.debug(f"获取 Stooq 个股数据失败 {symbol}: {e}")
        return None

def get_surge_stocks(threshold: float = 7.0) -> List[Dict]:
    """
    获取大涨个股（涨幅≥阈值）
    只取前 20 大市值股票，使用 Stooq API，允许失败，不阻断流程
    
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
            stock_data = get_stock_data_stooq(symbol)
            if not stock_data:
                continue
            
            change_pct = stock_data["change_pct"]
            
            # 只保留涨幅≥阈值的股票
            if change_pct >= threshold:
                # Stooq 不提供新闻，使用通用原因
                reason = "市场表现强劲"
                
                surge_stocks.append({
                    "category": "大涨个股",
                    "title": f"{symbol} +{change_pct:.2f}%",
                    "content": f"{symbol} 涨幅 {change_pct:+.2f}%，原因：{reason}",
                    "source": "Stooq",
                    "url": f"https://stooq.com/q/?s={symbol}",
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

def collect_index_data() -> List[Dict]:
    """
    采集主要指数数据（使用 Stooq）
    
    Returns:
        指数数据列表
    """
    indices: List[Dict] = []
    
    for name, symbol in settings.STOCK_INDICES.items():
        data = get_index_data_stooq(symbol, name)
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
    
    # 采集指数数据（允许失败）
    try:
        indices = collect_index_data()
        all_data.extend(indices)
        logger.info(f"成功获取 {len(indices)} 个指数数据（Stooq）")
    except Exception as e:
        logger.warning(f"采集指数数据失败: {e}（不影响整体流程）")
    
    # 采集大涨个股（允许失败）
    try:
        surge_stocks = get_surge_stocks(settings.STOCK_SURGE_THRESHOLD)
        all_data.extend(surge_stocks)
        logger.info(f"成功获取 {len(surge_stocks)} 只大涨个股（Stooq）")
    except Exception as e:
        logger.warning(f"采集大涨个股失败: {e}（不影响整体流程）")
    
    return all_data
