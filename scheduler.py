import logging
import traceback
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from config import Config

logger = logging.getLogger(__name__)


def run_morning_report() -> None:
    from src.market_data import fetch_morning_data, fetch_sector_performance
    from src.news_fetcher import fetch_news_headlines, fetch_weekly_events
    from src.ai_summarizer import analyze_morning
    from src.discord_sender import send_morning_report, send_error_notification

    logger.info("===== 開始執行每日早盤快訊 =====")
    try:
        logger.info("取得美股市場資料...")
        morning_data = fetch_morning_data()

        logger.info("分析台股族群表現...")
        sectors = fetch_sector_performance()

        logger.info("抓取今晨財經新聞...")
        headlines = fetch_news_headlines(max_count=Config.MAX_NEWS, report_type="morning")

        logger.info("查詢本週重要事件...")
        events = fetch_weekly_events()

        logger.info("執行 AI 盤前分析...")
        analysis = analyze_morning(morning_data, sectors, headlines)

        logger.info("發送 Discord 早盤快訊...")
        ok = send_morning_report(morning_data, sectors, headlines, events, analysis)

        if ok:
            logger.info("早盤快訊執行完成 ✓")
        else:
            logger.error("早盤快訊發送失敗")
    except Exception as e:
        err = traceback.format_exc()
        logger.error("早盤快訊執行錯誤:\n%s", err)
        from src.discord_sender import send_error_notification
        send_error_notification(err)


def run_closing_report() -> None:
    from src.market_data import fetch_closing_data, fetch_sector_performance
    from src.news_fetcher import fetch_news_headlines
    from src.ai_summarizer import analyze_closing
    from src.discord_sender import send_closing_report, send_error_notification

    logger.info("===== 開始執行每日收盤整理 =====")
    try:
        logger.info("取得台股收盤資料...")
        closing_data = fetch_closing_data()

        logger.info("分析台股族群表現...")
        sectors = fetch_sector_performance()

        logger.info("抓取今日財經新聞...")
        headlines = fetch_news_headlines(max_count=Config.MAX_NEWS, report_type="closing")

        logger.info("執行 AI 收盤解析...")
        analysis = analyze_closing(closing_data, sectors, headlines)

        logger.info("發送 Discord 收盤整理...")
        ok = send_closing_report(closing_data, sectors, headlines, analysis)

        if ok:
            logger.info("收盤整理執行完成 ✓")
        else:
            logger.error("收盤整理發送失敗")
    except Exception as e:
        err = traceback.format_exc()
        logger.error("收盤整理執行錯誤:\n%s", err)
        from src.discord_sender import send_error_notification
        send_error_notification(err)


def run_scheduler() -> None:
    Config.validate()
    tz = pytz.timezone(Config.TIMEZONE)

    mh, mm = Config.MORNING_TIME.split(":")
    ch, cm = Config.CLOSING_TIME.split(":")

    scheduler = BlockingScheduler(timezone=tz)
    scheduler.add_job(
        run_morning_report,
        trigger=CronTrigger(hour=int(mh), minute=int(mm), timezone=tz),
        id="morning_report",
        name="每日早盤快訊",
        misfire_grace_time=300,
        coalesce=True,
    )
    scheduler.add_job(
        run_closing_report,
        trigger=CronTrigger(hour=int(ch), minute=int(cm), timezone=tz),
        id="closing_report",
        name="每日收盤整理",
        misfire_grace_time=300,
        coalesce=True,
    )

    logger.info(
        "[%s V%s] 排程器啟動 — 早盤快訊 %s | 收盤整理 %s (%s)",
        Config.PROJECT_NAME, Config.VERSION,
        Config.MORNING_TIME, Config.CLOSING_TIME, Config.TIMEZONE,
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("排程器已停止")
