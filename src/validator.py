"""
資料驗證模組：每筆數據送出前做三層驗證
  1. 數學一致性：漲跌幅 = 漲跌點 / 前收 × 100，誤差 < 0.1%
  2. 交叉來源：yfinance vs TWSE / CoinGecko，差異 > 0.5% 標記
  3. 內容一致性：報告文字方向必須與數字方向相符
"""
import logging
import time
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

TW_TZ = timezone(timedelta(hours=8))
CROSS_THRESHOLD = 0.5   # 跨來源差異觸發閾值 (%)
MATH_TOLERANCE = 0.1    # 數學一致性容許誤差 (%)
MAX_RETRIES = 3
RETRY_DELAY = 5          # 秒


def _today_tw() -> str:
    return datetime.now(tz=TW_TZ).strftime("%Y%m%d")


# ── 1. 數學一致性 ──────────────────────────────────────────────

def math_check(name: str, price: float, change: float, change_pct: float) -> Optional[str]:
    prev = price - change
    if prev <= 0:
        return f"⚠️ {name} 前收價為負值，資料異常"
    computed_pct = change / prev * 100
    diff = abs(computed_pct - change_pct)
    if diff > MATH_TOLERANCE:
        return (
            f"⚠️ {name} 數學不一致："
            f"漲跌點{change:+.2f} / 前收{prev:.2f} = {computed_pct:.2f}%，"
            f"但回報 {change_pct:.2f}%（差 {diff:.2f}%）"
        )
    return None


def validate_math(data_list: list) -> list:
    warnings = []
    for item in data_list:
        if item is None:
            continue
        warn = math_check(item.name, item.price, item.change, item.change_pct)
        if warn:
            logger.warning(warn)
            warnings.append(warn)
        else:
            logger.info("數學驗證通過 %s: %.2f %+.2f (%.2f%%)",
                        item.name, item.price, item.change, item.change_pct)
    return warnings


# ── 2. 跨來源驗證 ─────────────────────────────────────────────

def _get_with_retry(url: str, **kwargs) -> Optional[dict]:
    for i in range(MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=10, **kwargs)
            return resp.json()
        except Exception as e:
            if i < MAX_RETRIES - 1:
                logger.warning("第 %d 次重試 %s: %s", i + 1, url[:60], e)
                time.sleep(RETRY_DELAY)
            else:
                logger.warning("放棄 %s: %s", url[:60], e)
    return None


def _fetch_twse_taiex() -> Optional[float]:
    date = _today_tw()
    # 主端點：市場指數
    body = _get_with_retry(
        f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
        f"?date={date}&type=MS&response=json",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    if body and body.get("stat") == "OK":
        for row in body.get("data", []):
            if row and "加權" in str(row[0]):
                try:
                    return float(str(row[1]).replace(",", ""))
                except ValueError:
                    pass

    # 備用端點：每日收盤行情彙總
    body2 = _get_with_retry(
        f"https://www.twse.com.tw/exchangeReport/FMTQIK"
        f"?response=json&date={date}",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    if body2 and body2.get("stat") == "OK":
        for row in body2.get("data", []):
            if row and "加權" in str(row[0]):
                try:
                    return float(str(row[1]).replace(",", ""))
                except ValueError:
                    pass

    logger.warning("TWSE API 無法取得加權指數（兩端點均失敗或今日無資料）")
    return None


def _fetch_coingecko() -> dict:
    body = _get_with_retry(
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=bitcoin,ethereum&vs_currencies=usd"
    )
    if body:
        return {
            "BTC": body.get("bitcoin", {}).get("usd"),
            "ETH": body.get("ethereum", {}).get("usd"),
        }
    return {}


def _cross_check(name: str, yf_val: float, ref_val: float, ref_src: str) -> Optional[str]:
    if not yf_val or not ref_val or ref_val == 0:
        return None
    diff = abs(yf_val - ref_val) / ref_val * 100
    if diff > CROSS_THRESHOLD:
        return (
            f"⚠️ {name} 跨來源差異 {diff:.2f}%"
            f"（yfinance: {yf_val:,.2f} | {ref_src}: {ref_val:,.2f}）"
            f" → 以 {ref_src} 為準"
        )
    logger.info("跨來源驗證通過 %s: yf=%.2f ref=%.2f (diff=%.3f%%)",
                name, yf_val, ref_val, diff)
    return None


def validate_closing(closing_data) -> list:
    warnings = []

    # 取出所有指數資料做數學驗證
    items = [d for _, d in closing_data.indices if d]
    warnings += validate_math(items)

    # 跨來源：加權指數 vs TWSE
    twii = next((d for n, d in closing_data.indices if "加權" in n and d), None)
    if twii:
        twse_price = _fetch_twse_taiex()
        if twse_price:
            warn = _cross_check("加權指數", twii.price, twse_price, "TWSE")
            if warn:
                warnings.append(warn)
        else:
            warnings.append("⚠️ 加權指數：TWSE 官方資料暫無法取得，數據未驗證")

    return warnings


def validate_morning(morning_data) -> list:
    warnings = []

    items = [d for _, d in morning_data.indices if d] + \
            [d for _, d in morning_data.crypto if d]
    warnings += validate_math(items)

    # 跨來源：BTC/ETH vs CoinGecko
    cg = _fetch_coingecko()
    for label, key in [("BTC", "BTC"), ("ETH", "ETH")]:
        yf_data = next((d for n, d in morning_data.crypto if label in n and d), None)
        ref = cg.get(key)
        if yf_data and ref:
            warn = _cross_check(label, yf_data.price, float(ref), "CoinGecko")
            if warn:
                warnings.append(warn)

    return warnings


# ── 3. 內容一致性驗證 ─────────────────────────────────────────

def validate_content(report_text: str, closing_data=None, morning_data=None) -> list:
    warnings = []

    if closing_data:
        twii = next((d for n, d in closing_data.indices if "加權" in n and d), None)
        if twii:
            is_down = twii.change_pct < -0.5
            is_up = twii.change_pct > 0.5
            has_down_word = any(w in report_text for w in ["下跌", "收黑", "走弱", "重挫"])
            has_up_word = any(w in report_text for w in ["上漲", "收紅", "走強", "大漲"])

            if is_down and has_up_word and not has_down_word:
                warnings.append(
                    f"⚠️ 內容矛盾：加權指數實際下跌 {twii.change_pct:.2f}%，"
                    f"但報告描述為上漲"
                )
            if is_up and has_down_word and not has_up_word:
                warnings.append(
                    f"⚠️ 內容矛盾：加權指數實際上漲 {twii.change_pct:.2f}%，"
                    f"但報告描述為下跌"
                )

    return warnings
