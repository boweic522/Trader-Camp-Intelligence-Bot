import argparse
import logging
import sys
from pathlib import Path

Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Trader Camp Intelligence Bot V2.0")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--now", "--morning",
        dest="morning",
        action="store_true",
        help="立即執行一次早盤快訊（08:50 格式）",
    )
    group.add_argument(
        "--closing",
        action="store_true",
        help="立即執行一次收盤整理（13:25 格式）",
    )
    args = parser.parse_args()

    if args.morning:
        from config import Config
        Config.validate()
        from scheduler import run_morning_report
        logger.info("手動觸發早盤快訊...")
        run_morning_report()
    elif args.closing:
        from config import Config
        Config.validate()
        from scheduler import run_closing_report
        logger.info("手動觸發收盤整理...")
        run_closing_report()
    else:
        from scheduler import run_scheduler
        run_scheduler()


if __name__ == "__main__":
    main()
