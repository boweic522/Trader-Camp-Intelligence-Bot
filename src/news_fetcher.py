import logging
from urllib.parse import quote
import feedparser
import requests

logger = logging.getLogger(__name__)

_MORNING_QUERIES = [
    "台股 財經 美股 台積電",
    "NASDAQ 聯準會 半導體 美股",
]
_CLOSING_QUERIES = [
    "台股 今日 收盤 漲跌",
    "台積電 外資 今日 法人",
]
_EVENT_QUERIES = {
    "Fed 利率": "Fed 聯準會 利率 FOMC 決議",
    "CPI 通膨": "CPI 美國通膨 消費者物價指數",
    "非農就業": "非農就業 美國就業 就業人數",
    "NVIDIA": "NVIDIA 輝達 財報 業績 GPU",
    "台積電": "台積電 TSMC 法說 業績 財報",
}


def _fetch_google_news(query: str, max_items: int = 10) -> list:
    url = (
        "https://news.google.com/rss/search"
        f"?q={quote(query)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    )
    try:
        headers = {"User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        titles = [e.get("title", "").strip() for e in feed.entries if e.get("title", "").strip()]
        logger.info("Google News (%s...) 取得 %d 則", query[:20], len(titles))
        return titles[:max_items]
    except Exception as e:
        logger.warning("Google News RSS 失敗 (%s): %s", query[:20], e)
        return []


def fetch_news_headlines(max_count: int = 6, report_type: str = "morning") -> list:
    queries = _CLOSING_QUERIES if report_type == "closing" else _MORNING_QUERIES
    seen: set = set()
    headlines: list = []
    for query in queries:
        for title in _fetch_google_news(query):
            key = title[:40].lower()
            if key not in seen:
                seen.add(key)
                headlines.append(title)
                if len(headlines) >= max_count:
                    return headlines
    return headlines


def fetch_weekly_events() -> dict:
    events: dict = {}
    for event_key, query in _EVENT_QUERIES.items():
        titles = _fetch_google_news(query, max_items=3)
        events[event_key] = titles[0] if titles else None
        logger.info("事件查詢 [%s]: %s", event_key, "找到" if titles else "無")
    return events
