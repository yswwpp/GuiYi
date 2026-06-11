"""
GuiYi Backend - 配置管理
"""

import os
from pathlib import Path
from typing import List, Optional


SERVER_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("GUIYI_DATA_DIR", SERVER_ROOT / "data")).expanduser().resolve()


class Settings:
    """应用配置"""

    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8765
    API_DEBUG: bool = True

    DB_CONFIG_PATH: str = str(DATA_DIR / "db_config.json")
    OBSIDIAN_VAULT_PATH: str = str(DATA_DIR / "obsidian_vault")
    INDEX_PATH: str = str(DATA_DIR / "index")
    AI_CONFIG_PATH: str = str(DATA_DIR / "ai_config.json")
    SCHEDULER_JOBS_PATH: str = str(DATA_DIR / "scheduler_jobs.json")
    YINXIANG_SYNC_STATE_PATH: str = str(DATA_DIR / "yinxiang_sync_state.json")
    YINXIANG_ACCOUNTS_PATH: str = str(DATA_DIR / "yinxiang_accounts.json")
    WEB_ASSETS_PATH: str = str(DATA_DIR / "obsidian_vault" / "inbox" / "assets")

    FEISHU_COMPANY_APP_ID: Optional[str] = None
    FEISHU_COMPANY_APP_SECRET: Optional[str] = None
    FEISHU_PERSONAL_APP_ID: Optional[str] = None
    FEISHU_PERSONAL_APP_SECRET: Optional[str] = None

    YINXIANG_DEV_TOKEN: Optional[str] = None
    QUARK_COOKIE: Optional[str] = None
    WPS_WATCH_DIRS: List[str] = []
    SYNC_INTERVAL_HOURS: int = 24

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        self.API_HOST = os.getenv("API_HOST", self.API_HOST)
        self.API_PORT = int(os.getenv("API_PORT", self.API_PORT))
        self.API_DEBUG = os.getenv("API_DEBUG", "true").lower() == "true"

        self.DB_CONFIG_PATH = os.getenv("DB_CONFIG_PATH", self.DB_CONFIG_PATH)
        self.OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", self.OBSIDIAN_VAULT_PATH)
        self.INDEX_PATH = os.getenv("INDEX_PATH", self.INDEX_PATH)
        self.AI_CONFIG_PATH = os.getenv("AI_CONFIG_PATH", self.AI_CONFIG_PATH)
        self.SCHEDULER_JOBS_PATH = os.getenv("SCHEDULER_JOBS_PATH", self.SCHEDULER_JOBS_PATH)
        self.YINXIANG_SYNC_STATE_PATH = os.getenv("YINXIANG_SYNC_STATE_PATH", self.YINXIANG_SYNC_STATE_PATH)
        self.YINXIANG_ACCOUNTS_PATH = os.getenv("YINXIANG_ACCOUNTS_PATH", self.YINXIANG_ACCOUNTS_PATH)
        self.WEB_ASSETS_PATH = os.getenv("WEB_ASSETS_PATH", self.WEB_ASSETS_PATH)

        self.FEISHU_COMPANY_APP_ID = os.getenv("FEISHU_COMPANY_APP_ID")
        self.FEISHU_COMPANY_APP_SECRET = os.getenv("FEISHU_COMPANY_APP_SECRET")
        self.FEISHU_PERSONAL_APP_ID = os.getenv("FEISHU_PERSONAL_APP_ID")
        self.FEISHU_PERSONAL_APP_SECRET = os.getenv("FEISHU_PERSONAL_APP_SECRET")
        self.YINXIANG_DEV_TOKEN = os.getenv("YINXIANG_DEV_TOKEN")
        self.QUARK_COOKIE = os.getenv("QUARK_COOKIE")
        self.SYNC_INTERVAL_HOURS = int(os.getenv("SYNC_INTERVAL_HOURS", self.SYNC_INTERVAL_HOURS))


settings = Settings()
