"""
凭证管理 - 使用 JSON 文件存储凭证

凭证文件路径由 GUIYI_CREDENTIALS_FILE 环境变量控制，
默认为 ${GUIYI_DATA_DIR}/../config/credentials.json。
文件权限 600，仅文件属主可读写。
"""

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Optional

import logging

logger = logging.getLogger(__name__)


def _credentials_path() -> Path:
    """获取凭证文件路径，从 settings 延迟导入避免循环依赖"""
    from guiyi_server.config import settings
    return Path(settings.CREDENTIALS_FILE).expanduser().resolve()


def _load_credentials() -> dict:
    """读取凭证文件，文件不存在时返回空 dict"""
    path = _credentials_path()
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"读取凭证文件失败 [{path}]: {e}")
        return {}


def _save_credentials(data: dict) -> bool:
    """原子写入凭证文件"""
    path = _credentials_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        # 原子写入：先写临时文件再 rename
        fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, str(path))
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        # 设置文件权限 600
        os.chmod(str(path), stat.S_IRUSR | stat.S_IWUSR)
        return True
    except Exception as e:
        logger.error(f"写入凭证文件失败 [{path}]: {e}")
        return False


class KeychainManager:
    """JSON 文件凭证管理（兼容原 KeychainManager 接口）"""

    @staticmethod
    def save_credential(account: str, key: str, value: str) -> bool:
        try:
            data = _load_credentials()
            data.setdefault(account, {})[key] = value
            if _save_credentials(data):
                logger.info(f"凭证已保存: {account}/{key}")
                return True
            return False
        except Exception as e:
            logger.error(f"保存凭证失败 [{account}/{key}]: {e}")
            return False

    @staticmethod
    def get_credential(account: str, key: str) -> Optional[str]:
        try:
            data = _load_credentials()
            return data.get(account, {}).get(key)
        except Exception as e:
            logger.error(f"获取凭证失败 [{account}/{key}]: {e}")
            return None

    @staticmethod
    def delete_credential(account: str, key: str) -> bool:
        try:
            data = _load_credentials()
            if account in data and key in data[account]:
                del data[account][key]
                if not data[account]:
                    del data[account]
                if _save_credentials(data):
                    logger.info(f"凭证已删除: {account}/{key}")
                    return True
            logger.warning(f"凭证不存在: {account}/{key}")
            return False
        except Exception as e:
            logger.error(f"删除凭证失败 [{account}/{key}]: {e}")
            return False

    @staticmethod
    def save_feishu_account(name: str, app_id: str, app_secret: str, user_access_token: str = None, refresh_token: str = None) -> bool:
        try:
            data = _load_credentials()
            account_data = {"app_id": app_id, "app_secret": app_secret}
            if user_access_token:
                account_data["user_access_token"] = user_access_token
            if refresh_token:
                account_data["refresh_token"] = refresh_token
            data.setdefault("feishu", {})[name] = account_data
            if _save_credentials(data):
                logger.info(f"飞书账号凭证已保存: {name}")
                return True
            return False
        except Exception as e:
            logger.error(f"保存飞书账号凭证失败 [{name}]: {e}")
            return False

    @staticmethod
    def get_feishu_account(name: str) -> Optional[dict]:
        try:
            data = _load_credentials()
            account_data = data.get("feishu", {}).get(name)
            if account_data and account_data.get("app_id") and account_data.get("app_secret"):
                return dict(account_data)
            return None
        except Exception as e:
            logger.error(f"获取飞书账号凭证失败 [{name}]: {e}")
            return None

    @staticmethod
    def delete_feishu_account(name: str) -> bool:
        try:
            data = _load_credentials()
            if name in data.get("feishu", {}):
                del data["feishu"][name]
                if not data["feishu"]:
                    del data["feishu"]
                if _save_credentials(data):
                    logger.info(f"飞书账号凭证已删除: {name}")
                    return True
            logger.warning(f"飞书账号不存在: {name}")
            return False
        except Exception as e:
            logger.error(f"删除飞书账号凭证失败 [{name}]: {e}")
            return False

    @staticmethod
    def list_feishu_accounts() -> list:
        try:
            data = _load_credentials()
            return list(data.get("feishu", {}).keys())
        except Exception as e:
            logger.error(f"列出飞书账号失败: {e}")
            return []

    # ==================== 印象笔记账号 ====================

    @staticmethod
    def save_yinxiang_account(name: str, token: str, note_store_url: str) -> bool:
        try:
            data = _load_credentials()
            data.setdefault("yinxiang", {})[name] = {
                "token": token,
                "note_store_url": note_store_url
            }
            if _save_credentials(data):
                logger.info(f"印象笔记账号凭证已保存: {name}")
                return True
            return False
        except Exception as e:
            logger.error(f"保存印象笔记账号凭证失败 [{name}]: {e}")
            return False

    @staticmethod
    def get_yinxiang_account(name: str) -> Optional[dict]:
        try:
            data = _load_credentials()
            account_data = data.get("yinxiang", {}).get(name)
            if account_data and account_data.get("token") and account_data.get("note_store_url"):
                return dict(account_data)
            return None
        except Exception as e:
            logger.error(f"获取印象笔记账号凭证失败 [{name}]: {e}")
            return None

    @staticmethod
    def delete_yinxiang_account(name: str) -> bool:
        try:
            data = _load_credentials()
            if name in data.get("yinxiang", {}):
                del data["yinxiang"][name]
                if not data["yinxiang"]:
                    del data["yinxiang"]
                if _save_credentials(data):
                    logger.info(f"印象笔记账号凭证已删除: {name}")
                    return True
            logger.warning(f"印象笔记账号不存在: {name}")
            return False
        except Exception as e:
            logger.error(f"删除印象笔记账号凭证失败 [{name}]: {e}")
            return False
