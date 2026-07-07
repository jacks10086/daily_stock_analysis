# -*- coding: utf-8 -*-
"""
===================================
美股板块轮动数据模块
===================================

使用行业 ETF 作为板块代理，通过 yfinance 获取每日涨跌幅数据，
计算板块强弱排名，用于大盘复盘中的板块轮动分析。

支持的板块 ETF 列表：
- 11 个 S&P 行业 SPDR (XLK, XLF, XLV, XLE, XLY, XLP, XLU, XLI, XLB, XLRE, XLC)
- 3 个细分行业 ETF (SMH 半导体, XSD 电子半导体等权, XAR 航天国防)

使用方式:
    from data_provider.us_sector_etf import get_us_sector_performance
    result = get_us_sector_performance()
    print(result["top"])    # 领涨板块
    print(result["bottom"]) # 领跌板块
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 美股板块 ETF 映射表
# 格式: { ticker: { name, category } }
# ticker: 可直接用于 yfinance 的符号
# name: 中文/英文显示名称（用于报告）
# category: 分类标签（core=行业核心, sub=细分板块）
US_SECTOR_ETFS = {
    # === S&P 行业核心板块（Sector SPDRs）===
    "XLK": {"name": "科技", "category": "core"},
    "XLF": {"name": "金融", "category": "core"},
    "XLV": {"name": "医疗", "category": "core"},
    "XLE": {"name": "能源", "category": "core"},
    "XLY": {"name": "可选消费", "category": "core"},
    "XLP": {"name": "必需消费", "category": "core"},
    "XLU": {"name": "公用事业", "category": "core"},
    "XLI": {"name": "工业", "category": "core"},
    "XLB": {"name": "材料", "category": "core"},
    "XLRE": {"name": "房地产", "category": "core"},
    "XLC": {"name": "通信服务", "category": "core"},
    # === 细分板块（与持仓股相关）===
    "SMH": {"name": "半导体", "category": "sub"},  # MU 所在行业
    "XSD": {"name": "电子半导体(等权)", "category": "sub"},  # SNDK 所在行业
    "XAR": {"name": "航天与国防", "category": "sub"},  # RKLB 所在行业
}


def _build_sector_item(
    ticker: str,
    info: Dict[str, Any],
    *,
    close: float,
    prev_close: float,
    close_5d: Optional[float] = None,
) -> Dict[str, Any]:
    """构建标准化的板块数据项。"""
    change_pct = ((close - prev_close) / prev_close * 100) if prev_close else 0.0
    category = info.get("category", "core")
    item = {
        "ticker": ticker,
        "name": f"{ticker}({info.get('name', ticker)})",
        "category": category,
        "close": round(close, 2),
        "change_pct": round(change_pct, 2),
        "volume": 0,
        "prev_close": round(prev_close, 2),
    }
    if close_5d is not None and close_5d:
        change_pct_5d = ((close - close_5d) / close_5d * 100) if close_5d else 0.0
        item["change_pct_5d"] = round(change_pct_5d, 2)
    return item


def get_us_sector_performance(
    lookback_days: int = 5,
) -> Optional[Dict[str, Any]]:
    """
    获取美股板块 ETF 涨跌幅排名数据。

    使用 yfinance 批量拉取板块 ETF 行情，计算当日涨跌幅，
    按涨跌幅排序返回领涨/领跌板块列表。

    Args:
        lookback_days: 用于计算 5 日涨跌幅的回看天数

    Returns:
        Dict with keys:
            - timestamp: 数据时间戳
            - top: 领涨板块列表（按涨跌幅降序）
            - bottom: 领跌板块列表（按涨跌幅升序）
            - all: 全部板块（按涨跌幅降序）
        ETF 数据获取失败或所有数据为空时返回 None
    """
    import yfinance as yf

    tickers = list(US_SECTOR_ETFS.keys())
    if not tickers:
        logger.warning("[USSector] 板块 ETF 列表为空，跳过数据获取")
        return None

    try:
        logger.info("[USSector] action=fetch_sector_data status=start tickers=%s", tickers)
        # 拉取足够的天数来覆盖假日/周末，确保有 2 个有效交易日
        fetch_period = f"{lookback_days + 5}d"
        df = yf.download(
            tickers=tickers,
            period=fetch_period,
            progress=False,
            auto_adjust=True,
            group_by="ticker",
        )

        if df is None or df.empty:
            logger.warning("[USSector] action=fetch_sector_data status=empty response")
            return None

        logger.info("[USSector] action=fetch_sector_data status=success shape=%s", df.shape)

        sectors = []
        # yfinance.download 返回多层索引，列顺序为 (OHLCV, Ticker)
        # 所以 ticker 在 columns.levels[1] 中
        for ticker in tickers:
            try:
                if hasattr(df.columns, "levels") and ticker in df.columns.levels[1]:
                    ticker_df = df.xs(ticker, level=1, axis=1)
                else:
                    # 单个 ticker 或扁平 DataFrame
                    ticker_df = df

                if ticker_df.empty:
                    logger.debug("[USSector] ticker=%s 无数据，跳过", ticker)
                    continue

                # 取最新的非空 close 行
                valid_rows = ticker_df["Close"].dropna()
                if valid_rows.empty:
                    logger.debug("[USSector] ticker=%s Close 列无有效数据，跳过", ticker)
                    continue

                close = float(valid_rows.iloc[-1])
                if len(valid_rows) < 2:
                    # 只有一天数据，无法计算涨跌幅
                    logger.debug("[USSector] ticker=%s 数据不足 2 个交易日，跳过", ticker)
                    continue

                prev_close = float(valid_rows.iloc[-2])
                close_5d = None
                if len(valid_rows) >= lookback_days:
                    close_5d = float(valid_rows.iloc[-min(lookback_days, len(valid_rows))])

                etf_info = US_SECTOR_ETFS.get(ticker, {"name": ticker, "category": "core"})
                sector_item = _build_sector_item(
                    ticker,
                    etf_info,
                    close=close,
                    prev_close=prev_close,
                    close_5d=close_5d,
                )
                # 添加 volume（可选字段）
                try:
                    vol = ticker_df["Volume"].dropna()
                    if not vol.empty:
                        sector_item["volume"] = int(vol.iloc[-1])
                except (KeyError, IndexError, TypeError, ValueError):
                    pass

                sectors.append(sector_item)

            except Exception as ticker_err:
                logger.debug("[USSector] ticker=%s 处理异常: %s", ticker, ticker_err)
                continue

        if not sectors:
            logger.warning("[USSector] 所有板块数据均获取失败")
            return None

        # 按涨跌幅排序
        sectors.sort(key=lambda x: x.get("change_pct", 0.0), reverse=True)
        all_sorted = list(sectors)

        # 至少需要 2 个板块才有排名意义
        if len(all_sorted) >= 2:
            top = all_sorted[:5]
            bottom = list(reversed(all_sorted[-5:]))
        else:
            top = all_sorted
            bottom = []

        result: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "top": top,
            "bottom": bottom,
            "all": all_sorted,
        }
        logger.info(
            "[USSector] 板块数据获取完成: top=%s, bottom=%s",
            [s.get("ticker") for s in top],
            [s.get("ticker") for s in bottom],
        )
        return result

    except ImportError:
        logger.error("[USSector] yfinance 未安装，无法获取板块数据")
        return None
    except Exception as e:
        logger.warning("[USSector] 获取美股板块数据失败: %s", e, exc_info=True)
        return None


def format_sector_ranking_summary(ranking: List[Dict], limit: int = 3) -> str:
    """Format sector ranking list to compact summary string."""
    if not ranking:
        return "N/A"
    parts = []
    for item in ranking[:limit]:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or "") or str(item.get("name") or "")
        change = item.get("change_pct")
        if change is not None:
            try:
                parts.append(f"{ticker}({float(change):+.2f}%)")
            except (TypeError, ValueError):
                parts.append(ticker)
        else:
            parts.append(ticker)
    return ", ".join(parts)
