import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    PROJECT_NAME: str = "Trader Camp Intelligence"
    VERSION: str = "2.0"

    DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")
    MORNING_TIME: str = os.getenv("MORNING_TIME", "08:50")
    CLOSING_TIME: str = os.getenv("CLOSING_TIME", "13:25")
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Taipei")
    MAX_NEWS: int = int(os.getenv("MAX_NEWS_PER_CATEGORY", "6"))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "15"))

    # Backward compatibility
    SCHEDULE_TIME: str = os.getenv("MORNING_TIME", "08:50")

    @classmethod
    def validate(cls) -> None:
        if not cls.DISCORD_WEBHOOK_URL:
            raise ValueError("缺少必要環境變數: DISCORD_WEBHOOK_URL")
