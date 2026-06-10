import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

TW_TZ = timezone(timedelta(hours=8))
THRESHOLD_PCT = 0.5


def _today_tw() -> str:
    return datetime.now(tz=TW_TZ).strftime("%Y%m%d")


def _fetch_twse_taiex() -> Optional[float]:
    date = _today_tw()
    url = (
        f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
        f"?date={date}&type=MS&response=json"
    )
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        body = resp.json()
        if body.get("stat") != "OK":
            logger.warning("TWSE MI_INDEX stat=%s", body.get("stat"))
            return None
        for row in body.get("data", []):
            label = str(row[0]) if row else ""
            if "加權" in label:
                price_str = str(row[1]).replace(",", "")
                return float(price_str)
    except Exception as e:
        logger.warning("TWSE API 失敗: %s", e)
    return None


def _fetch_coingecko() -> dict:
    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=bitcoin,ethereum&vs_currencies=usd"
    )
    try:
        resp = requests.get(url, timeout=10)
        body = resp.json()
        return {
            "BTC": body.get("bitcoin", {}).get("usd"),
            "ETH": body.get("ethereum", {}).get("usd"),
        }
    except Exception as e:
        logger.warning("CoinGecko API 失敗: %s", e)
        return {}


def _check(name: str, yf_val: float, ref_val: float) -> Optional[str]:
    if not yf_val or not ref_val or ref_val == 0:
        return None
    diff = abs(yf_val - ref_val) / ref_val * 100
    if diff > THRESHOLD_PCT:
        return (
            f"⚠️ {name} 資料差異 {diff:.2f}%"
            f"（yfinance: {yf_val:,.2f}  |  官方: {ref_val:,.2f}）"
        )
    logger.info("驗證通過 %s：yfinance %.2f | 官方 %.2f（差 %.3f%%）",
                name, yf_val, ref_val, diff)
    return None


def validate_closing(closing_data) -> list:
    warnings = []
    twii = next((d for n, d in closing_data.indices if "加權" in n and d), None)
    if twii is None:
        return warnings
    twse_price = _fetch_twse_taiex()
    if twse_price:
        warn = _check("加權指數", twii.price, twse_price)
        if warn:
            warnings.append(warn)
    else:
        logger.warning("TWSE 官方資料不可用，跳過收盤驗證")
    return warnings


def validate_morning(morning_data) -> list:
    warnings = []
    cg = _fetch_coingecko()
    for label, key in [("BTC", "BTC"), ("ETH", "ETH")]:
        yf_data = next((d for n, d in morning_data.crypto if label in n and d), None)
        ref = cg.get(key)
        if yf_data and ref:
            warn = _check(label, yf_data.price, ref)
            if warn:
                warnings.append(warn)
    return warnings
