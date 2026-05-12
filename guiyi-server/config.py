"""
GuiYi Backend - 配置管理
"""

import os
from pathlib import Path
from typing import Optional, List


class Settings:
    """应用配置"""

    # API 配置
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8765
    API_DEBUG: bool = True

    # 数据库配置
    DATABASE_URL: str = "sqlite:///data/sync_metadata.sqlite"

    # Obsidian 配置
    OBSIDIAN_VAULT_PATH: str = "data/obsidian_vault"

    # 索引配置
    INDEX_PATH: str = "data/index"

    # 飞书配置
    FEISHU_COMPANY_APP_ID: Optional[str] = None
    FEISHU_COMPANY_APP_SECRET: Optional[str] = None
    FEISHU_PERSONAL_APP_ID: Optional[str] = None
    FEISHU_PERSONAL_APP_SECRET: Optional[str] = None

    # 印象笔记配置
    YINXIANG_DEV_TOKEN: Optional[str] = None

    # 夸克网盘配置
    QUARK_COOKIE: Optional[str] = None

    # WPS 配置
    WPS_WATCH_DIRS: List[str] = []

    # 同步配置
    SYNC_INTERVAL_HOURS: int = 24

    def __init__(self):
        """从环境变量加载配置"""
        # API 配置
        self.API_HOST = os.getenv("API_HOST", self.API_HOST)
        self.API_PORT = int(os.getenv("API_PORT", self.API_PORT))
        self.API_DEBUG = os.getenv("API_DEBUG", "true").lower() == "true"

        # 数据库配置
        self.DATABASE_URL = os.getenv("DATABASE_URL", self.DATABASE_URL)

        # Obsidian 配置
        self.OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", self.OBSIDIAN_VAULT_PATH)

        # 索引配置
        self.INDEX_PATH = os.getenv("INDEX_PATH", self.INDEX_PATH)

        # 飞书配置
        self.FEISHU_COMPANY_APP_ID = os.getenv("FEISHU_COMPANY_APP_ID")
        self.FEISHU_COMPANY_APP_SECRET = os.getenv("FEISHU_COMPANY_APP_SECRET")
        self.FEISHU_PERSONAL_APP_ID = os.getenv("FEISHU_PERSONAL_APP_ID")
        self.FEISHU_PERSONAL_APP_SECRET = os.getenv("FEISHU_PERSONAL_APP_SECRET")

        # 印象笔记配置
        self.YINXIANG_DEV_TOKEN = os.getenv("YINXIANG_DEV_TOKEN")

        # 夸克网盘配置
        self.QUARK_COOKIE = os.getenv("QUARK_COOKIE")

        # 同步配置
        self.SYNC_INTERVAL_HOURS = int(os.getenv("SYNC_INTERVAL_HOURS", self.SYNC_INTERVAL_HOURS))


# 全局配置实例
settings = Settings()
