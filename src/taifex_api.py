"""
TAIFEX 台指期資料模組
使用 TradingView scanner API (TAIFEX:TXF1! 近月連續合約)
"""
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Origin": "https://www.tradingview.com",
    "Referer": "https://www.tradingview.com/",
}
TIMEOUT = 10

TV_FIELDS = "close,change,change_abs,open,high,low,volume"
TV_URL = (
    "https://scanner.tradingview.com/symbol"
    "?symbol=TAIFEX:TXF1!&fields=" + TV_FIELDS + "&no_404=true"
)


def _fetch_txf() -> Optional[dict]:
    """從 TradingView 取得台指期近月合約數據"""
    try:
        r = requests.get(TV_URL, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            logger.warning("TradingView API 回傳 %d", r.status_code)
            return None
        data = r.json()
        if not data or data.get("close") is None:
            logger.warning("TradingView 回傳空資料")
            return None
        close = float(data["close"])
        change_abs = float(data.get("change_abs", 0))
        change_pct = float(data.get("change", 0))
        logger.info("台指期 TXF1! 取得: %.0f %+.0f (%.2f%%)", close, change_abs, change_pct)
        return {
            "price": close,
            "change": change_abs,
            "change_pct": change_pct,
            "open": float(data.get("open") or 0),
            "high": float(data.get("high") or 0),
            "low": float(data.get("low") or 0),
        }
    except Exception as e:
        logger.warning("台指期 TradingView 取得失敗: %s", e)
        return None


def fetch_txf_daily() -> Optional[dict]:
    """台指期日盤（近月合約收盤）"""
    return _fetch_txf()


def fetch_txf_night() -> Optional[dict]:
    """台指期夜盤（近月合約最後盤後收盤）"""
    return _fetch_txf()
