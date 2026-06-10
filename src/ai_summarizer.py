from dataclasses import dataclass, field
from typing import Optional

_POSITIVE = [
    "上漲", "創高", "強勁", "樂觀", "買超", "突破", "成長", "獲利",
    "上調", "利多", "反彈", "優於預期", "激增", "翻揚", "走強", "回升",
]
_NEGATIVE = [
    "下跌", "跌破", "悲觀", "賣超", "衰退", "虧損", "下調", "警告",
    "風險", "利空", "恐慌", "縮減", "暫停", "崩跌", "走弱", "受壓",
]


@dataclass
class MorningAnalysis:
    sentiment: str
    favorable_factors: list
    risk_factors: list
    key_observations: list
    top_sectors_for_today: list
    risk_reminder: str


@dataclass
class ClosingAnalysis:
    market_view: str
    up_reasons: list
    down_reasons: list
    institutional_focus: list
    tomorrow_observations: list
    tomorrow_trade_focus: list
    tomorrow_risk_events: list
    trader_camp_quote: str


def _count_kw(text: str, keywords: list) -> int:
    return sum(1 for kw in keywords if kw in text)


def _extract(headlines: list, polarity: str, max_items: int = 3) -> list:
    out = []
    for title in headlines:
        pos = _count_kw(title, _POSITIVE)
        neg = _count_kw(title, _NEGATIVE)
        match = (polarity == "pos" and pos > neg) or (polarity == "neg" and neg > pos)
        if match:
            short = title[:60] + "…" if len(title) > 60 else title
            out.append(short)
        if len(out) >= max_items:
            break
    return out


def _vol_desc(volume: Optional[float]) -> str:
    if not volume or volume <= 0:
        return "暫無法確認"
    b = volume / 1e8
    if b >= 3000:
        return f"爆量（{b:.0f}億）"
    if b >= 2000:
        return f"放量（{b:.0f}億）"
    if b >= 1000:
        return f"正常（{b:.0f}億）"
    return f"縮量（{b:.0f}億）"


def analyze_morning(morning_data, sectors: list, headlines: list) -> MorningAnalysis:
    sp500 = next((d for n, d in morning_data.indices if "S&P" in n and d), None)
    nasdaq = next((d for n, d in morning_data.indices if "NASDAQ" in n and d), None)
    sox = next((d for n, d in morning_data.indices if "費城" in n and d), None)

    pos, neg = 0, 0
    for data in [sp500, nasdaq, sox]:
        if data is None:
            continue
        if data.change_pct > 1.0:
            pos += 3
        elif data.change_pct > 0.3:
            pos += 1
        elif data.change_pct < -1.0:
            neg += 3
        elif data.change_pct < -0.3:
            neg += 1

    news_text = " ".join(headlines)
    pos += _count_kw(news_text, _POSITIVE)
    neg += _count_kw(news_text, _NEGATIVE)

    if pos >= neg + 4:
        sentiment = "偏多"
    elif neg >= pos + 4:
        sentiment = "偏空"
    else:
        sentiment = "中性"

    favorable = _extract(headlines, "pos") or ["美股維持相對平穩，暫無重大利空"]
    risks = _extract(headlines, "neg") or ["暫無重大風險訊號，維持謹慎觀察"]

    observations = []
    for s in sectors[:3]:
        sign = "+" if s.is_up else ""
        observations.append(
            f"{s.emoji} {s.name} 族群昨日 {s.arrow} {sign}{s.avg_change_pct:.2f}%，"
            f"代表股 {s.best_stock}（{'+' if s.best_stock_pct >= 0 else ''}{s.best_stock_pct:.2f}%）"
        )
    if not observations:
        observations = ["暫無法確認強勢族群"]

    top_today = [f"{s.emoji} {s.name}（{s.best_stock}）" for s in sectors[:3]]
    if not top_today:
        top_today = ["暫無法確認"]

    if sentiment == "偏多":
        reminder = "美股收紅，台股有望正向開出，但注意追高風險，設好停損再入場。"
    elif sentiment == "偏空":
        reminder = "美股走弱，台股開盤恐承壓，建議降低部位，待盤面穩定後再評估。"
    else:
        reminder = "多空訊號混雜，建議等待開盤方向確立後再決策，切勿倉促進場。"

    return MorningAnalysis(
        sentiment=sentiment,
        favorable_factors=favorable,
        risk_factors=risks,
        key_observations=observations,
        top_sectors_for_today=top_today,
        risk_reminder=reminder,
    )


def analyze_closing(closing_data, sectors: list, headlines: list) -> ClosingAnalysis:
    twii = next((d for n, d in closing_data.indices if "加權" in n and d), None)

    if twii is None:
        market_view = "暫無法確認今日台股走勢"
    elif twii.change_pct >= 1.5:
        market_view = (
            f"台股強勢大漲，加權指數收 {twii.price:,.2f} 點，"
            f"上漲 {twii.change_pct:.2f}%，成交量{_vol_desc(twii.volume)}，多方氣勢旺盛。"
        )
    elif twii.change_pct > 0.3:
        market_view = (
            f"台股小幅收紅，加權指數收 {twii.price:,.2f} 點，"
            f"上漲 {twii.change_pct:.2f}%，成交量{_vol_desc(twii.volume)}，多空力道相當。"
        )
    elif twii.change_pct >= -0.3:
        market_view = (
            f"台股盤整格局，加權指數收 {twii.price:,.2f} 點，"
            f"小幅變動 {twii.change_pct:.2f}%，成交量{_vol_desc(twii.volume)}，方向待確認。"
        )
    elif twii.change_pct > -1.5:
        market_view = (
            f"台股小幅收黑，加權指數收 {twii.price:,.2f} 點，"
            f"下跌 {abs(twii.change_pct):.2f}%，成交量{_vol_desc(twii.volume)}，空方略佔上風。"
        )
    else:
        market_view = (
            f"台股明顯下跌，加權指數收 {twii.price:,.2f} 點，"
            f"重挫 {abs(twii.change_pct):.2f}%，成交量{_vol_desc(twii.volume)}，市場避險情緒升溫。"
        )

    up_reasons = _extract(headlines, "pos", 3) or ["今日上漲原因暫無法從新聞確認"]
    down_reasons = _extract(headlines, "neg", 3) or ["今日下跌原因暫無法從新聞確認"]

    inst_focus = [f"{s.emoji} {s.name}（{s.best_stock}）" for s in sectors[:3]]
    if not inst_focus:
        inst_focus = ["暫無法確認"]

    tomorrow_obs = []
    for s in sectors[:2]:
        tomorrow_obs.append(f"觀察 {s.emoji}{s.name} 族群能否延續動能")
    tomorrow_obs.append("留意法人籌碼動向與資金流向")
    if not tomorrow_obs:
        tomorrow_obs = ["暫無法確認"]

    tomorrow_focus = [f"{s.emoji} {s.name}" for s in sectors[:3]]
    if not tomorrow_focus:
        tomorrow_focus = ["暫無法確認"]

    tomorrow_risks = _extract(headlines, "neg", 2) or ["暫無明顯風險事件"]

    if twii and twii.change_pct >= 0.5:
        quote = "攻勢延續，強者恆強，跟著籌碼走，設好停損紀律操作。"
    elif twii and twii.change_pct <= -0.5:
        quote = "空頭壓力不可輕忽，保留子彈，靜待更好的進場時機。"
    else:
        quote = "盤整蓄勢中，耐心等待方向確立，切忌追漲殺跌。"

    return ClosingAnalysis(
        market_view=market_view,
        up_reasons=up_reasons,
        down_reasons=down_reasons,
        institutional_focus=inst_focus,
        tomorrow_observations=tomorrow_obs,
        tomorrow_trade_focus=tomorrow_focus,
        tomorrow_risk_events=tomorrow_risks,
        trader_camp_quote=quote,
    )
