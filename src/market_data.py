import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional
import yfinance as yf

logger = logging.getLogger(__name__)

MORNING_INDICES = [
    ("S&P 500", "^GSPC"),
    ("NASDAQ", "^IXIC"),
    ("費城半導體", "^SOX"),
    ("美元指數", "DX-Y.NYB"),
    ("VIX恐慌指數", "^VIX"),
]
MORNING_CRYPTO = [
    ("BTC", "BTC-USD"),
    ("ETH", "ETH-USD"),
]
CLOSING_INDICES = [
    ("加權指數", "^TWII"),
    ("櫃買指數", "^TWOII"),   # Taiwan OTC index; fallback to 暫無法確認 if unavailable
]

TAIWAN_SECTORS = [
    ("AI伺服器", "🤖", [("廣達", "2382.TW"), ("緯穎", "6669.TW"), ("英業達", "2356.TW")]),
    ("PCB", "💾", [("欣興", "3037.TW"), ("健鼎", "3044.TW"), ("金像電", "2368.TW")]),
    ("散熱", "🌡️", [("奇鋐", "3017.TW"), ("超眾", "6230.TW"), ("建準", "5007.TW")]),
    ("網通", "📡", [("中磊", "5388.TW"), ("智邦", "2345.TW"), ("正文", "4906.TW")]),
    ("ASIC", "🧠", [("世芯-KY", "3661.TW"), ("創意", "3443.TW"), ("智原", "3035.TW")]),
    ("半導體", "⚡", [("台積電", "2330.TW"), ("聯電", "2303.TW"), ("日月光", "3711.TW")]),
    ("記憶體", "💿", [("南亞科", "2408.TW"), ("旺宏", "2337.TW"), ("群聯", "8271.TW")]),
    ("電源被動", "⚙️", [("台達電", "2308.TW"), ("國巨", "2327.TW"), ("禾伸堂", "3026.TW")]),
]


@dataclass
class SymbolData:
    name: str
    symbol: str
    price: float
    change: float
    change_pct: float
    data_date: str
    volume: Optional[float] = None

    @property
    def is_up(self) -> bool:
        return self.change >= 0

    @property
    def arrow(self) -> str:
        return "▲" if self.is_up else "▼"


@dataclass
class SectorData:
    name: str
    emoji: str
    avg_change_pct: float
    best_stock: str
    best_stock_pct: float

    @property
    def is_up(self) -> bool:
        return self.avg_change_pct >= 0

    @property
    def arrow(self) -> str:
        return "▲" if self.is_up else "▼"


@dataclass
class SectorIndex:
    name: str
    price: float
    change: float
    change_pct: float

    @property
    def is_up(self) -> bool:
        return self.change_pct >= 0

    @property
    def arrow(self) -> str:
        return "▲" if self.is_up else "▼"


@dataclass
class MorningMarketData:
    indices: list
    crypto: list
    sector_indices: list = field(default_factory=list)
    txf_night: Optional[dict] = None


@dataclass
class ClosingMarketData:
    indices: list
    sector_indices: list = field(default_factory=list)
    txf_daily: Optional[dict] = None
    vix: Optional["SymbolData"] = None


def _fetch(name: str, symbol: str, with_volume: bool = False) -> Optional[SymbolData]:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d")
        if hist.empty:
            logger.warning("無資料 %s (%s)", name, symbol)
            return None

        latest = hist.iloc[-1]
        price = float(latest["Close"])

        # 優先使用 yfinance info 的官方前收盤價，避免跨假日計算錯誤
        prev_close = None
        try:
            info = ticker.info
            prev_close = (
                info.get("previousClose")
                or info.get("regularMarketPreviousClose")
            )
            if prev_close:
                prev_close = float(prev_close)
        except Exception:
            pass

        if not prev_close and len(hist) >= 2:
            prev_close = float(hist.iloc[-2]["Close"])

        if not prev_close:
            logger.warning("無法取得 %s 前收盤價", name)
            return None

        change = price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0.0

        # 合理性防護：指數單日超過 ±15% 代表 previousClose 錯誤，改用歷史比較
        if abs(change_pct) > 15 and len(hist) >= 2:
            hist_prev = float(hist.iloc[-2]["Close"])
            hist_change = price - hist_prev
            hist_pct = hist_change / hist_prev * 100 if hist_prev else 0.0
            logger.warning(
                "%s previousClose 異常（%.2f%%），改用歷史前收 %.2f → %.2f%%",
                name, change_pct, hist_prev, hist_pct
            )
            prev_close, change, change_pct = hist_prev, hist_change, hist_pct

        vol_raw = float(latest.get("Volume", 0)) if with_volume else None
        volume = vol_raw if (vol_raw is not None and vol_raw > 0) else None

        logger.debug("%s price=%.2f prev=%.2f chg=%.2f pct=%.2f%%",
                     name, price, prev_close, change, change_pct)

        return SymbolData(
            name=name, symbol=symbol, price=price,
            change=change, change_pct=change_pct,
            data_date=hist.index[-1].strftime("%Y/%m/%d"),
            volume=volume,
        )
    except Exception as e:
        logger.error("取得 %s 失敗: %s", name, e)
        return None


def _fetch_change_pct(symbol: str) -> Optional[float]:
    try:
        hist = yf.Ticker(symbol).history(period="3d")
        if len(hist) < 2:
            return None
        latest = float(hist.iloc[-1]["Close"])
        prev = float(hist.iloc[-2]["Close"])
        return (latest - prev) / prev * 100 if prev else None
    except Exception:
        return None


def fetch_sector_performance() -> list:
    results = []
    for sector_name, emoji, stocks in TAIWAN_SECTORS:
        changes = []
        best_stock, best_pct = "", -999.0
        for stock_name, ticker in stocks:
            pct = _fetch_change_pct(ticker)
            if pct is not None:
                changes.append(pct)
                if pct > best_pct:
                    best_pct, best_stock = pct, stock_name
        if not changes:
            logger.warning("族群 %s 無法取得資料", sector_name)
            continue
        avg = sum(changes) / len(changes)
        results.append(SectorData(
            name=sector_name, emoji=emoji,
            avg_change_pct=avg,
            best_stock=best_stock,
            best_stock_pct=best_pct,
        ))
    results.sort(key=lambda x: x.avg_change_pct, reverse=True)
    logger.info("族群分析完成，共 %d 個族群", len(results))
    return results


def fetch_morning_data() -> MorningMarketData:
    from src.twse_api import fetch_sector_indices
    from src.taifex_api import fetch_txf_night
    raw_sectors = fetch_sector_indices()
    sector_indices = [
        SectorIndex(name=s["name"], price=s["price"],
                    change=s["change"], change_pct=s["change_pct"])
        for s in raw_sectors
    ]
    return MorningMarketData(
        indices=[(n, _fetch(n, s)) for n, s in MORNING_INDICES],
        crypto=[(n, _fetch(n, s)) for n, s in MORNING_CRYPTO],
        sector_indices=sector_indices,
        txf_night=fetch_txf_night(),
    )


def _build_symbol_data(name: str, official: dict, symbol: str,
                        with_volume: bool = False) -> Optional[SymbolData]:
    """用官方 API 數據建立 SymbolData，成交量仍從 yfinance 補充"""
    try:
        price = official["price"]
        change = official["change"]
        change_pct = official["change_pct"]
        volume = None
        if with_volume:
            try:
                hist = yf.Ticker(symbol).history(period="2d")
                if not hist.empty:
                    vol_raw = float(hist.iloc[-1].get("Volume", 0))
                    volume = vol_raw if vol_raw > 0 else None
            except Exception:
                pass
        return SymbolData(
            name=name, symbol=symbol,
            price=price, change=change, change_pct=change_pct,
            data_date=datetime.now(tz=timezone(timedelta(hours=8))).strftime("%Y/%m/%d"),
            volume=volume,
        )
    except (KeyError, TypeError, ValueError) as e:
        logger.error("建立 %s SymbolData 失敗: %s", name, e)
        return None


def fetch_closing_data() -> ClosingMarketData:
    from src.twse_api import fetch_taiex, fetch_tpex_index, fetch_sector_indices
    from src.taifex_api import fetch_txf_daily
    from datetime import timezone, timedelta

    # 加權指數：官方 TWSE 優先，失敗才用 yfinance
    twii_official = fetch_taiex()
    if twii_official:
        twii = _build_symbol_data("加權指數", twii_official, "^TWII", with_volume=True)
        logger.info("加權指數採用 TWSE 官方資料")
    else:
        twii = _fetch("加權指數", "^TWII", with_volume=True)
        logger.warning("加權指數回退使用 yfinance")

    # 櫃買指數：官方 TPEX 優先，失敗才用 yfinance
    tpex_official = fetch_tpex_index()
    if tpex_official:
        tpex = _build_symbol_data("櫃買指數", tpex_official, "^TWOII")
        logger.info("櫃買指數採用 TPEX 官方資料")
    else:
        tpex = _fetch("櫃買指數", "^TWOII")
        logger.warning("櫃買指數回退使用 yfinance")

    # 產業類股指數
    raw_sectors = fetch_sector_indices()
    sector_indices = [
        SectorIndex(name=s["name"], price=s["price"],
                    change=s["change"], change_pct=s["change_pct"])
        for s in raw_sectors
    ]

    vix = _fetch("VIX恐慌指數", "^VIX")

    return ClosingMarketData(
        indices=[("加權指數", twii), ("櫃買指數", tpex)],
        sector_indices=sector_indices,
        txf_daily=fetch_txf_daily(),
        vix=vix,
    )


# Legacy support
@dataclass
class MarketSnapshot:
    indices: list
    crypto: list


def fetch_all_market_data() -> MarketSnapshot:
    _ALL = [("台灣加權指數", "^TWII"), ("S&P 500", "^GSPC"),
            ("NASDAQ", "^IXIC"), ("費城半導體", "^SOX"), ("美元/台幣", "TWD=X")]
    _CRYPTO = [("BTC", "BTC-USD"), ("ETH", "ETH-USD")]
    return MarketSnapshot(
        indices=[(n, _fetch(n, s)) for n, s in _ALL],
        crypto=[(n, _fetch(n, s)) for n, s in _CRYPTO],
    )
