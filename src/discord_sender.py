import logging
from datetime import datetime, timezone, timedelta
import requests
from config import Config

logger = logging.getLogger(__name__)

TW_TZ = timezone(timedelta(hours=8))
BOT_NAME = "Trader Camp Intelligence Bot"


def _now_str() -> str:
    now = datetime.now(tz=TW_TZ)
    weekday = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"][now.weekday()]
    return now.strftime(f"%Y/%m/%d ({weekday})")


def _fmt_index(data) -> str:
    if data is None:
        return "暫無法確認"
    sign = "+" if data.change >= 0 else ""
    return f"{data.price:,.2f}　{data.arrow} {sign}{data.change:.2f}（{sign}{data.change_pct:.2f}%）"


def _fmt_crypto(data) -> str:
    if data is None:
        return "暫無法確認"
    sign = "+" if data.change >= 0 else ""
    return f"{data.price:,.0f}　{data.arrow} {sign}{data.change:.0f}（{sign}{data.change_pct:.2f}%）"


def _post(webhook_url: str, content: str) -> bool:
    payload = {"content": content, "username": BOT_NAME}
    try:
        resp = requests.post(webhook_url, json=payload, timeout=Config.REQUEST_TIMEOUT)
        if resp.status_code in (200, 204):
            return True
        logger.error("Discord 回傳 %d: %s", resp.status_code, resp.text[:200])
        return False
    except requests.RequestException as e:
        logger.error("Discord 發送失敗: %s", e)
        return False


def _send_long(webhook_url: str, text: str) -> bool:
    MAX = 1900
    if len(text) <= MAX:
        return _post(webhook_url, text)
    lines = text.split("\n")
    chunks, current, cur_len = [], [], 0
    for line in lines:
        n = len(line) + 1
        if cur_len + n > MAX and current:
            chunks.append("\n".join(current))
            current, cur_len = [line], n
        else:
            current.append(line)
            cur_len += n
    if current:
        chunks.append("\n".join(current))
    ok = True
    for chunk in chunks:
        if not _post(webhook_url, chunk):
            ok = False
    return ok


def build_morning_report(morning_data, sectors, headlines, events, analysis) -> str:
    medals = ["🥇", "🥈", "🥉"]
    lines = [
        f"🌅 **Trader Camp Intelligence** | 每日早盤快訊 V2.0",
        f"📅 {_now_str()}",
        "",
        "━━━━ 🌎 昨夜市場總覽 ━━━━",
        f"🇺🇸 **S&P 500**：{_fmt_index(next((d for n,d in morning_data.indices if 'S&P' in n), None))}",
        f"🇺🇸 **NASDAQ**：{_fmt_index(next((d for n,d in morning_data.indices if 'NASDAQ' in n), None))}",
        f"💾 **費城半導體**：{_fmt_index(next((d for n,d in morning_data.indices if '費城' in n), None))}",
        f"💵 **美元指數**：{_fmt_index(next((d for n,d in morning_data.indices if '美元' in n), None))}",
        f"🪙 **BTC**：{_fmt_crypto(next((d for n,d in morning_data.crypto if 'BTC' in n), None))}",
        f"🪙 **ETH**：{_fmt_crypto(next((d for n,d in morning_data.crypto if 'ETH' in n), None))}",
        "",
        "━━━━ 🔥 昨日強勢族群 ━━━━",
    ]
    strong = [s for s in sectors if s.is_up][:3]
    if strong:
        for i, s in enumerate(strong):
            lines.append(f"{medals[i]} {s.emoji} **{s.name}**　▲{s.avg_change_pct:.2f}%　代表：{s.best_stock}")
    else:
        lines.append("暫無法確認")

    lines += ["", "━━━━ 📰 今晨重要新聞 ━━━━"]
    if headlines:
        for i, h in enumerate(headlines[:6], 1):
            short = h[:65] + "…" if len(h) > 65 else h
            lines.append(f"{i}. {short}")
    else:
        lines.append("暫無法確認")

    lines += ["", "━━━━ 🤖 AI 盤前重點 ━━━━"]
    lines.append(f"📈 **市場情緒**：{analysis.sentiment}")
    lines.append("✅ **有利因素**：")
    for f in analysis.favorable_factors:
        lines.append(f"　• {f}")
    lines.append("⚠️ **風險因素**：")
    for r in analysis.risk_factors:
        lines.append(f"　• {r}")
    lines.append("🎯 **今日觀察重點**：")
    for o in analysis.key_observations:
        lines.append(f"　• {o}")

    lines += ["", "━━━━ 👀 今日關注族群 ━━━━"]
    for i, g in enumerate(analysis.top_sectors_for_today[:3]):
        m = medals[i] if i < 3 else "  "
        lines.append(f"{m} {g}")

    lines += ["", "━━━━ 📅 本週重要事件 ━━━━"]
    event_icons = {
        "Fed 利率": "🏦 Fed",
        "CPI 通膨": "📊 CPI",
        "非農就業": "👷 非農",
        "NVIDIA": "🟢 NVIDIA",
        "台積電": "🔵 台積電",
    }
    for key, label in event_icons.items():
        val = events.get(key)
        if val:
            short = val[:55] + "…" if len(val) > 55 else val
            lines.append(f"{label}：{short}")
        else:
            lines.append(f"{label}：暫無法確認")

    lines += ["", "━━━━ 🚨 風險提醒 ━━━━"]
    lines.append(analysis.risk_reminder)

    return "\n".join(lines)


def build_closing_report(closing_data, sectors, headlines, analysis) -> str:
    medals = ["🥇", "🥈", "🥉"]
    twii = next((d for n, d in closing_data.indices if "加權" in n and d), None)
    tpex = next((d for n, d in closing_data.indices if "櫃買" in n and d), None)

    twii_str = "暫無法確認"
    vol_str = ""
    if twii:
        twii_str = f"{twii.price:,.2f} 點　{twii.arrow} {twii.change:+.2f}（{twii.change_pct:+.2f}%）"
        if twii.volume:
            vol_str = f"　成交量 {twii.volume/1e8:.0f}億"

    tpex_str = "暫無法確認"
    if tpex:
        tpex_str = f"{tpex.price:,.2f} 點　{tpex.arrow} {tpex.change:+.2f}（{tpex.change_pct:+.2f}%）"

    lines = [
        f"🌙 **Trader Camp Intelligence** | 每日收盤整理 V2.0",
        f"📅 {_now_str()}",
        "",
        "━━━━ 📊 台股收盤概況 ━━━━",
        f"📈 **加權指數**：{twii_str}{vol_str}",
        f"📈 **櫃買指數**：{tpex_str}",
        "",
        "━━━━ 🔥 今日強勢族群 ━━━━",
    ]
    strong = [s for s in sectors if s.is_up][:3]
    if strong:
        for i, s in enumerate(strong):
            lines.append(
                f"{medals[i]} {s.emoji} **{s.name}**　▲{s.avg_change_pct:.2f}%　"
                f"代表：{s.best_stock}（▲{s.best_stock_pct:.2f}%）"
            )
    else:
        lines.append("今日無明顯強勢族群")

    lines += ["", "━━━━ ❄️ 今日弱勢族群 ━━━━"]
    weak = sorted([s for s in sectors if not s.is_up], key=lambda x: x.avg_change_pct)[:3]
    if weak:
        for i, s in enumerate(weak):
            lines.append(
                f"{medals[i]} {s.emoji} **{s.name}**　▼{abs(s.avg_change_pct):.2f}%　"
                f"代表：{s.best_stock}（{s.best_stock_pct:.2f}%）"
            )
    else:
        lines.append("今日無明顯弱勢族群")

    lines += ["", "━━━━ 📰 今日重要新聞 ━━━━"]
    if headlines:
        for i, h in enumerate(headlines[:6], 1):
            short = h[:65] + "…" if len(h) > 65 else h
            lines.append(f"{i}. {short}")
    else:
        lines.append("暫無法確認")

    lines += ["", "━━━━ 🤖 AI 收盤解析 ━━━━"]
    lines.append(f"📌 **今日盤勢判讀**：{analysis.market_view}")
    lines.append("📌 **今日上漲原因**：")
    for r in analysis.up_reasons:
        lines.append(f"　• {r}")
    lines.append("📌 **今日下跌原因**：")
    for r in analysis.down_reasons:
        lines.append(f"　• {r}")
    lines.append("📌 **法人可能關注方向**：")
    for f in analysis.institutional_focus:
        lines.append(f"　• {f}")

    lines += ["", "━━━━ 🎯 明日觀察重點 ━━━━"]
    for o in analysis.tomorrow_observations:
        lines.append(f"• {o}")

    lines += ["", "━━━━ 🧭 明日交易焦點 ━━━━"]
    for i, focus in enumerate(analysis.tomorrow_trade_focus[:3]):
        m = medals[i] if i < 3 else "  "
        lines.append(f"{m} {focus}")

    lines += ["", "━━━━ ⚠️ 明日風險事件 ━━━━"]
    for r in analysis.tomorrow_risk_events:
        lines.append(f"• {r}")

    lines += ["", "━━━━ 💬 Trader Camp 一句話 ━━━━"]
    lines.append(f"「{analysis.trader_camp_quote}」")

    return "\n".join(lines)


def send_morning_report(morning_data, sectors, headlines, events, analysis) -> bool:
    if not Config.DISCORD_WEBHOOK_URL:
        logger.error("DISCORD_WEBHOOK_URL 未設定")
        return False
    text = build_morning_report(morning_data, sectors, headlines, events, analysis)
    logger.info("發送早盤快訊（%d 字）", len(text))
    return _send_long(Config.DISCORD_WEBHOOK_URL, text)


def send_closing_report(closing_data, sectors, headlines, analysis) -> bool:
    if not Config.DISCORD_WEBHOOK_URL:
        logger.error("DISCORD_WEBHOOK_URL 未設定")
        return False
    text = build_closing_report(closing_data, sectors, headlines, analysis)
    logger.info("發送收盤整理（%d 字）", len(text))
    return _send_long(Config.DISCORD_WEBHOOK_URL, text)


def send_error_notification(error_msg: str) -> None:
    if not Config.DISCORD_WEBHOOK_URL:
        return
    payload = {
        "username": BOT_NAME,
        "embeds": [{
            "title": "⚠️ Bot 執行錯誤",
            "description": f"```\n{error_msg[:1900]}\n```",
            "color": 0xE74C3C,
        }],
    }
    try:
        requests.post(Config.DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    except Exception:
        pass
