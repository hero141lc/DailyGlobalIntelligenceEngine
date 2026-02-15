"""
美股市场数据采集模块
采集主要指数和大涨个股（≥7%）
个股优先用 yfinance 一次批量拉取，失败时回退 Stooq 逐只请求
"""
import time
import requests
import csv
import io
from typing import List, Dict, Optional

from config import settings
from utils.logger import logger
from utils.time import get_today_date

try:
    import pandas as pd
except ImportError:
    pd = None  # type: ignore

STOOQ_RETRIES = 3  # Stooq 请求失败时重试次数
STOOQ_DELAY = 0.5  # 每次请求间隔（秒），仅回退时使用

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
                "close": latest_close,
                "change_pct": change_pct,
                "name": name,
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
            "close": close,
            "change_pct": change_pct,
            "name": name,
        }
    except Exception as e:
        logger.debug(f"Yahoo 指数回退失败 {symbol}: {e}")
        return None

def get_stocks_batch_yfinance(symbols: List[str]) -> List[Dict]:
    """
    使用 yfinance 一次请求拉取多只股票最近行情，返回与 get_stock_data_stooq 兼容的列表。
    每项为 {symbol, close, change_pct, name}，失败或数据不足的标的跳过。
    """
    if not symbols:
        return []
    if pd is None:
        return []
    try:
        import yfinance as yf
        sym_list = [s.strip() for s in symbols if s and str(s).strip()]
        if not sym_list:
            return []
        # 一次下载所有标的，period=5d 取最近 5 日用于算涨跌；group_by='ticker' 列为 (Ticker, OHLCV)
        df = yf.download(
            sym_list,
            period="5d",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
            timeout=30,
        )
        if df is None or df.empty or len(df) < 2:
            return []
        out: List[Dict] = []
        # 多标的：列为 MultiIndex 第一层为 Ticker
        if hasattr(df.columns, "get_level_values") and df.columns.nlevels >= 2:
            tickers = df.columns.get_level_values(0).unique().tolist()
            for sym in tickers:
                try:
                    close_ser = df[sym]["Close"]
                    if close_ser is None or close_ser.empty or len(close_ser) < 2:
                        continue
                    close_ser = close_ser.dropna()
                    if len(close_ser) < 2:
                        continue
                    latest = float(close_ser.iloc[-1])
                    prev = float(close_ser.iloc[-2])
                    if prev == 0:
                        continue
                    change_pct = ((latest - prev) / prev) * 100
                    out.append({"symbol": sym, "close": latest, "change_pct": change_pct, "name": sym})
                except Exception as e:
                    logger.debug(f"yfinance 解析 {sym} 失败: {e}")
        else:
            # 单标的：列为 Open, High, Low, Close, ...
            try:
                close_ser = df["Close"].dropna() if "Close" in df.columns else None
                if close_ser is not None and len(close_ser) >= 2:
                    latest = float(close_ser.iloc[-1])
                    prev = float(close_ser.iloc[-2])
                    if prev != 0:
                        sym = sym_list[0]
                        out.append({
                            "symbol": sym,
                            "close": latest,
                            "change_pct": ((latest - prev) / prev) * 100,
                            "name": sym,
                        })
            except Exception as e:
                logger.debug(f"yfinance 单标的解析失败: {e}")
        return out
    except Exception as e:
        logger.warning(f"yfinance 批量拉取失败: {e}")
        return []


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
                "name": symbol,
            }
        except (ValueError, IndexError):
            return None
    except Exception as e:
        logger.debug(f"获取 Stooq 个股数据失败 {symbol}: {e}")
        return None

def get_surge_stocks(threshold: float = 7.0) -> List[Dict]:
    """
    获取大涨个股（涨幅≥阈值）
    优先用 yfinance 一次批量拉取，失败或数据不足时回退 Stooq 逐只请求
    """
    popular_symbols = getattr(settings, "STOCK_WATCHLIST", None) or [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
        "BRK-B", "V", "UNH", "JNJ", "WMT", "JPM", "MA", "PG",
        "HD", "DIS", "BAC", "ADBE", "NFLX", "VRT", "MU", "ORCL", "INTC", "AMD",
        "XOM", "CVX", "CRM",
    ]
    surge_stocks: List[Dict] = []
    batch = get_stocks_batch_yfinance(popular_symbols)
    if batch:
        for d in batch:
            change_pct = d["change_pct"]
            if change_pct >= threshold:
                sym = d["symbol"]
                surge_stocks.append({
                    "category": "大涨个股",
                    "title": f"{sym} +{change_pct:.2f}%",
                    "content": f"{sym} 涨幅 {change_pct:+.2f}%，原因：市场表现强劲",
                    "source": "Yahoo Finance",
                    "url": f"https://finance.yahoo.com/quote/{sym}",
                    "published_at": get_today_date(),
                    "change_pct": change_pct,
                    "close": d.get("close"),
                    "symbol": sym,
                })
        surge_stocks.sort(key=lambda x: x.get("change_pct", 0), reverse=True)
        logger.info(f"发现 {len(surge_stocks)} 只大涨个股（≥{threshold}%），来源：批量拉取")
        return surge_stocks
    # 回退：Stooq 逐只请求
    for i, symbol in enumerate(popular_symbols):
        if i > 0:
            time.sleep(getattr(settings, "STOOQ_DELAY", 0.5) or 0.5)
        try:
            stock_data = get_stock_data_stooq(symbol)
            if not stock_data or stock_data["change_pct"] < threshold:
                continue
            change_pct = stock_data["change_pct"]
            surge_stocks.append({
                "category": "大涨个股",
                "title": f"{symbol} +{change_pct:.2f}%",
                "content": f"{symbol} 涨幅 {change_pct:+.2f}%，原因：市场表现强劲",
                "source": "Stooq",
                "url": f"https://stooq.com/q/?s={symbol}",
                "published_at": get_today_date(),
                "change_pct": change_pct,
                "close": stock_data.get("close"),
                "symbol": symbol,
            })
        except Exception as e:
            logger.debug(f"获取股票 {symbol} 数据失败: {e}")
    surge_stocks.sort(key=lambda x: x.get("change_pct", 0), reverse=True)
    logger.info(f"发现 {len(surge_stocks)} 只大涨个股（≥{threshold}%），来源：Stooq 回退")
    return surge_stocks


def get_daily_movers(top_n: int = 5) -> List[Dict]:
    """
    获取今日涨跌一览：涨幅前 top_n 与跌幅前 top_n 的个股。
    优先用 yfinance 一次批量拉取，失败时回退 Stooq 逐只请求。
    """
    popular_symbols = getattr(settings, "STOCK_WATCHLIST", None) or [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
        "BRK-B", "V", "UNH", "JNJ", "WMT", "JPM", "MA", "PG",
        "HD", "DIS", "BAC", "ADBE", "NFLX", "CRM", "ORCL", "INTC", "AMD",
        "VRT", "MU", "XOM", "CVX",
    ]
    all_data: List[Dict] = []
    batch = get_stocks_batch_yfinance(popular_symbols)
    if batch:
        for d in batch:
            sym = d["symbol"]
            chg = d["change_pct"]
            close = d.get("close", 0)
            all_data.append({
                "category": "今日涨跌",
                "title": f"{sym} {chg:+.2f}%",
                "content": f"{sym} 收盘 {close:.2f}，涨跌 {chg:+.2f}%",
                "source": "Yahoo Finance",
                "url": f"https://finance.yahoo.com/quote/{sym}",
                "published_at": get_today_date(),
                "change_pct": chg,
                "close": close,
                "symbol": sym,
            })
    if not all_data:
        for i, symbol in enumerate(popular_symbols):
            if i > 0:
                time.sleep(getattr(settings, "STOOQ_DELAY", 0.5) or 0.5)
            try:
                d = get_stock_data_stooq(symbol)
                if d:
                    all_data.append({
                        "category": "今日涨跌",
                        "title": f"{d['symbol']} {d['change_pct']:+.2f}%",
                        "content": f"{d['symbol']} 收盘 {d.get('close', 0):.2f}，涨跌 {d['change_pct']:+.2f}%",
                        "source": "Stooq",
                        "url": f"https://stooq.com/q/?s={symbol}",
                        "published_at": get_today_date(),
                        "change_pct": d["change_pct"],
                        "close": d.get("close"),
                        "symbol": d["symbol"],
                    })
            except Exception:
                continue
    all_data.sort(key=lambda x: x.get("change_pct", 0), reverse=True)
    gainers = all_data[:top_n]
    gainer_symbols = {g["symbol"] for g in gainers}
    loser_candidates = [x for x in all_data if x["symbol"] not in gainer_symbols]
    losers = loser_candidates[-top_n:] if len(loser_candidates) >= top_n else loser_candidates
    losers.reverse()
    result = []
    for g in gainers:
        result.append({**g, "sub_label": "涨幅"})
    for L in losers:
        result.append({**L, "sub_label": "跌幅", "category": "今日涨跌"})
    logger.info(f"今日涨跌一览：涨幅 {len(gainers)} 只，跌幅 {len(losers)} 只（共 {len(all_data)} 只面板）")
    return result


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
    
    # 今日涨跌一览（涨幅/跌幅前 N，丰富股票板块）
    try:
        top_n = getattr(settings, "STOCK_DAILY_MOVERS_TOP", 5) or 5
        movers = get_daily_movers(top_n)
        all_data.extend(movers)
    except Exception as e:
        logger.warning(f"采集今日涨跌一览失败: {e}（不影响整体流程）")
    
    return all_data
