import logging
from dataclasses import dataclass
from typing import Optional
import yfinance as yf

logger = logging.getLogger(__name__)

MORNING_INDICES = [
    ("S&P 500", "^GSPC"),
    ("NASDAQ", "^IXIC"),
    ("費城半導體", "^SOX"),
    ("美元指數", "DX-Y.NYB"),
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
    ("記憶體", "💿", [("南亞科", "2408.TW"), ("力旺", "3529.TW"), ("鈺創", "5351.TW")]),
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
class MorningMarketData:
    indices: list
    crypto: list


@dataclass
class ClosingMarketData:
    indices: list


def _fetch(name: str, symbol: str, with_volume: bool = False) -> Optional[SymbolData]:
    try:
        hist = yf.Ticker(symbol).history(period="5d")
        if hist.empty:
            logger.warning("無資料 %s (%s)", name, symbol)
            return None

        latest = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) >= 2 else hist.iloc[-1]
        price = float(latest["Close"])
        prev_close = float(prev["Close"])
        change = price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0.0
        vol_raw = float(latest.get("Volume", 0)) if with_volume else None
        volume = vol_raw if (vol_raw is not None and vol_raw > 0) else None

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
    return MorningMarketData(
        indices=[(n, _fetch(n, s)) for n, s in MORNING_INDICES],
        crypto=[(n, _fetch(n, s)) for n, s in MORNING_CRYPTO],
    )


def fetch_closing_data() -> ClosingMarketData:
    return ClosingMarketData(
        indices=[
            ("加權指數", _fetch("加權指數", "^TWII", with_volume=True)),
            ("櫃買指數", _fetch("櫃買指數", "^TWOII", with_volume=False)),
        ]
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
