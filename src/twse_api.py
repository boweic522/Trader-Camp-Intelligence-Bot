"""
TWSE / TPEX 官方 API 模組
優先取官方數據，失敗時回傳 None 讓 yfinance 接手
"""
import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)
TW_TZ = timezone(timedelta(hours=8))
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
TIMEOUT = 10

SECTOR_TARGETS = {
    "半導體類指數": "半導體",
    "電子工業類指數": "電子工業",
    "電子零組件類指數": "電子零組件",
    "金融保險類指數": "金融保險",
    "航運類指數": "航運",
    "數位雲端類指數": "數位雲端",
    "建材營造類指數": "建材營造",
    "生技醫療類指數": "生技醫療",
    "光電類指數": "光電",
    "通信網路類指數": "通信網路",
}


def _today_tw() -> str:
    return datetime.now(tz=TW_TZ).strftime("%Y%m%d")


def _roc_date() -> str:
    now = datetime.now(tz=TW_TZ)
    return f"{now.year - 1911}/{now.month:02d}/{now.day:02d}"


def _get(url: str) -> Optional[dict]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        return r.json()
    except Exception as e:
        logger.warning("API 請求失敗 %s: %s", url[:80], e)
        return None


# ── 台灣加權指數 (TWSE) ─────────────────────────────────────

def fetch_taiex() -> Optional[dict]:
    """回傳 {price, change, change_pct, volume} 或 None"""
    date = _today_tw()

    # 端點 1：MI_INDEX (盤後市場指數)
    body = _get(
        f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
        f"?date={date}&type=MS&response=json"
    )
    if body and body.get("stat") == "OK":
        for row in body.get("data", []):
            if row and "加權" in str(row[0]):
                try:
                    price = float(str(row[1]).replace(",", ""))
                    change = float(str(row[2]).replace(",", "").replace("+", ""))
                    pct = float(str(row[3]).replace("%", "").replace("+", ""))
                    logger.info("TWSE MI_INDEX 取得加權指數: %.2f %+.2f (%.2f%%)",
                                price, change, pct)
                    return {"price": price, "change": change, "change_pct": pct}
                except (ValueError, IndexError):
                    pass

    # 端點 2：FMTQIK — fields: [日期, 成交股數, 成交金額, 成交筆數, 加權指數, 漲跌點數]
    body2 = _get(
        f"https://www.twse.com.tw/exchangeReport/FMTQIK"
        f"?response=json&date={date}"
    )
    if body2 and body2.get("stat") == "OK":
        rows = body2.get("data", [])
        # 找當日資料（日期欄位格式 "115/06/10"）
        today_tw = datetime.now(tz=TW_TZ)
        roc_today = f"{today_tw.year - 1911}/{today_tw.month:02d}/{today_tw.day:02d}"
        for row in reversed(rows):
            if not row or str(row[0]) != roc_today:
                continue
            try:
                price = float(str(row[4]).replace(",", ""))
                change = float(str(row[5]).replace(",", "").replace("+", ""))
                prev = price - change
                pct = (change / prev * 100) if prev else 0.0
                logger.info("TWSE FMTQIK 取得加權指數: %.2f %+.2f (%.2f%%)",
                            price, change, pct)
                return {"price": price, "change": change, "change_pct": pct}
            except (ValueError, IndexError):
                pass

    logger.warning("TWSE 官方 API 無法取得加權指數（date=%s）", date)
    return None


# ── 櫃買指數 (TPEX) ──────────────────────────────────────────

def fetch_tpex_index() -> Optional[dict]:
    """回傳 {price, change, change_pct} 或 None"""
    roc = _roc_date()

    # 端點 1：TPEX 每日收盤行情彙總
    body = _get(
        f"https://www.tpex.org.tw/web/stock/aftertrading/"
        f"otc_quotes_no1430/stk_wn1430_result.php"
        f"?l=zh-tw&d={roc}&se=EW&response=json"
    )
    if body and body.get("iTotalRecords", 0) > 0:
        # OTC index 通常在 aaData 的第一筆或 tpex_total
        stat = body.get("tpex_total")
        if stat:
            try:
                price = float(str(stat.get("close", "")).replace(",", ""))
                change = float(str(stat.get("change", "")).replace("+", ""))
                prev = price - change
                pct = change / prev * 100 if prev else 0.0
                logger.info("TPEX 取得櫃買指數: %.2f %+.2f (%.2f%%)",
                            price, change, pct)
                return {"price": price, "change": change, "change_pct": pct}
            except (ValueError, TypeError):
                pass

    # 端點 2：TPEX Market Report
    body2 = _get(
        f"https://www.tpex.org.tw/web/stock/aftertrading/"
        f"MarketReport/market_result.php?response=json&date={roc}"
    )
    if body2:
        try:
            idx = body2.get("index") or body2.get("tpex_index")
            if idx:
                price = float(str(idx.get("close", "")).replace(",", ""))
                change = float(str(idx.get("change", "")).replace("+", ""))
                prev = price - change
                pct = change / prev * 100 if prev else 0.0
                logger.info("TPEX MarketReport 取得櫃買指數: %.2f %+.2f (%.2f%%)",
                            price, change, pct)
                return {"price": price, "change": change, "change_pct": pct}
        except (ValueError, TypeError, AttributeError):
            pass

    logger.warning("TPEX 官方 API 無法取得櫃買指數（date=%s）", roc)
    return None


# ── 產業類股指數 (TWSE) ───────────────────────────────────────

def fetch_sector_indices() -> list:
    """回傳主要產業類股指數 list，格式: {name, short_name, price, change, change_pct}"""
    body = _get(
        "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
        "?type=ALL&response=json"
    )
    if not body:
        logger.warning("TWSE MI_INDEX 無法取得類股指數")
        return []

    results = []
    for table in body.get("tables", []):
        for row in table.get("data", []):
            if len(row) < 5:
                continue
            full_name = str(row[0])
            if full_name not in SECTOR_TARGETS:
                continue
            try:
                price = float(str(row[1]).replace(",", ""))
                change_pct = float(str(row[4]).replace("%", "").replace("+", ""))
                change_pts_abs = float(str(row[3]).replace(",", ""))
                change = change_pts_abs if change_pct >= 0 else -change_pts_abs
                results.append({
                    "name": SECTOR_TARGETS[full_name],
                    "price": price,
                    "change": change,
                    "change_pct": change_pct,
                })
            except (ValueError, IndexError) as e:
                logger.debug("解析類股 %s 失敗: %s", full_name, e)

    results.sort(key=lambda x: x["change_pct"], reverse=True)
    logger.info("TWSE 類股指數取得 %d 項", len(results))
    return results
