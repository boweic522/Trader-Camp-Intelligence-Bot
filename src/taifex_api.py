"""
TAIFEX 台指期資料模組
注意：TAIFEX 官方網站使用 JavaScript 動態渲染，無公開 JSON REST API 可用。
所有函式目前回傳 None，架構保留供未來資料來源接入使用。
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def fetch_txf_daily() -> Optional[dict]:
    """台指期日盤結算價 — 目前無可用 API，回傳 None"""
    logger.debug("台指期日盤：TAIFEX 無公開 API，跳過")
    return None


def fetch_txf_night() -> Optional[dict]:
    """台指期夜盤（盤後）結算價 — 目前無可用 API，回傳 None"""
    logger.debug("台指期夜盤：TAIFEX 無公開 API，跳過")
    return None
