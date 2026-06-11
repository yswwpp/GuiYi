"""
凭证管理 - 使用 macOS Keychain 安全存储凭证
"""

import keyring
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Keychain 服务名称
SERVICE_NAME = "GuiYi"


class KeychainManager:
    """macOS Keychain 凭证管理"""

    @staticmethod
    def save_credential(account: str, key: str, value: str) -> bool:
        """
        保存凭证到 Keychain

        Args:
            account: 账号标识（如 "feishu_company"）
            key: 凭证键（如 "app_id" 或 "app_secret"）
            value: 凭证值

        Returns:
            是否保存成功
        """
        try:
            service_key = f"{account}_{key}"
            keyring.set_password(SERVICE_NAME, service_key, value)
            logger.info(f"凭证已保存: {account}/{key}")
            return True
        except Exception as e:
            logger.error(f"保存凭证失败 [{account}/{key}]: {e}")
            return False

    @staticmethod
    def get_credential(account: str, key: str) -> Optional[str]:
        """
        从 Keychain 获取凭证

        Args:
            account: 账号标识
            key: 凭证键

        Returns:
            凭证值，如果不存在或失败返回 None
        """
        try:
            service_key = f"{account}_{key}"
            value = keyring.get_password(SERVICE_NAME, service_key)
            return value
        except Exception as e:
            logger.error(f"获取凭证失败 [{account}/{key}]: {e}")
            return None

    @staticmethod
    def delete_credential(account: str, key: str) -> bool:
        """
        从 Keychain 删除凭证

        Args:
            account: 账号标识
            key: 凭证键

        Returns:
            是否删除成功
        """
        try:
            service_key = f"{account}_{key}"
            keyring.delete_password(SERVICE_NAME, service_key)
            logger.info(f"凭证已删除: {account}/{key}")
            return True
        except keyring.errors.PasswordNotFoundError:
            logger.warning(f"凭证不存在: {account}/{key}")
            return False
        except Exception as e:
            logger.error(f"删除凭证失败 [{account}/{key}]: {e}")
            return False

    @staticmethod
    def save_feishu_account(name: str, app_id: str, app_secret: str, user_access_token: str = None, refresh_token: str = None) -> bool:
        """
        保存飞书账号凭证

        Args:
            name: 账号名称（如 "company" 或 "personal"）
            app_id: 飞书应用 ID
            app_secret: 飞书应用密钥
            user_access_token: 用户访问令牌（可选）
            refresh_token: 刷新令牌（可选）

        Returns:
            是否保存成功
        """
        account_key = f"feishu_{name}"

        success = True
        if not KeychainManager.save_credential(account_key, "app_id", app_id):
            success = False

        if not KeychainManager.save_credential(account_key, "app_secret", app_secret):
            success = False

        if user_access_token:
            if not KeychainManager.save_credential(account_key, "user_access_token", user_access_token):
                success = False

        if refresh_token:
            if not KeychainManager.save_credential(account_key, "refresh_token", refresh_token):
                success = False

        return success

    @staticmethod
    def get_feishu_account(name: str) -> Optional[dict]:
        """
        获取飞书账号凭证

        Args:
            name: 账号名称

        Returns:
            凭证字典 {"app_id": ..., "app_secret": ..., "user_access_token": ..., "refresh_token": ...}，如果不存在返回 None
        """
        account_key = f"feishu_{name}"

        app_id = KeychainManager.get_credential(account_key, "app_id")
        app_secret = KeychainManager.get_credential(account_key, "app_secret")
        user_access_token = KeychainManager.get_credential(account_key, "user_access_token")
        refresh_token = KeychainManager.get_credential(account_key, "refresh_token")

        if app_id and app_secret:
            result = {
                "app_id": app_id,
                "app_secret": app_secret
            }
            if user_access_token:
                result["user_access_token"] = user_access_token
            if refresh_token:
                result["refresh_token"] = refresh_token
            return result

        return None

    @staticmethod
    def delete_feishu_account(name: str) -> bool:
        """
        删除飞书账号凭证

        Args:
            name: 账号名称

        Returns:
            是否删除成功
        """
        account_key = f"feishu_{name}"

        success = True
        if not KeychainManager.delete_credential(account_key, "app_id"):
            success = False

        if not KeychainManager.delete_credential(account_key, "app_secret"):
            success = False

        return success

    @staticmethod
    def list_feishu_accounts() -> list:
        """
        列出所有飞书账号

        注意：keyring 库不支持直接列出所有账号，
        这里需要配合配置文件或数据库来管理账号列表。

        Returns:
            账号名称列表
        """
        # TODO: 从配置文件或数据库读取账号列表
        return []

    # ==================== 印象笔记账号 ====================

    @staticmethod
    def save_yinxiang_account(name: str, token: str, note_store_url: str) -> bool:
        """
        保存印象笔记账号凭证

        Args:
            name: 账号名称
            token: Developer Token
            note_store_url: NoteStore URL

        Returns:
            是否保存成功
        """
        account_key = f"yinxiang_{name}"

        success = True
        if not KeychainManager.save_credential(account_key, "token", token):
            success = False

        if not KeychainManager.save_credential(account_key, "note_store_url", note_store_url):
            success = False

        return success

    @staticmethod
    def get_yinxiang_account(name: str) -> Optional[dict]:
        """
        获取印象笔记账号凭证

        Args:
            name: 账号名称

        Returns:
            凭证字典 {"token": ..., "note_store_url": ...}，如果不存在返回 None
        """
        account_key = f"yinxiang_{name}"

        token = KeychainManager.get_credential(account_key, "token")
        note_store_url = KeychainManager.get_credential(account_key, "note_store_url")

        if token and note_store_url:
            return {
                "token": token,
                "note_store_url": note_store_url
            }

        return None

    @staticmethod
    def delete_yinxiang_account(name: str) -> bool:
        """
        删除印象笔记账号凭证

        Args:
            name: 账号名称

        Returns:
            是否删除成功
        """
        account_key = f"yinxiang_{name}"

        success = True
        if not KeychainManager.delete_credential(account_key, "token"):
            success = False

        if not KeychainManager.delete_credential(account_key, "note_store_url"):
            success = False

        return success


# 使用示例
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # 保存飞书账号
    KeychainManager.save_feishu_account(
        name="company",
        app_id="cli_company_app_id_here",
        app_secret="company_app_secret_here"
    )

    # 获取飞书账号
    credentials = KeychainManager.get_feishu_account("company")
    if credentials:
        print(f"App ID: {credentials['app_id']}")
        print(f"App Secret: {credentials['app_secret'][:10]}...")  # 只显示前 10 个字符
    else:
        print("未找到凭证")

    # 删除飞书账号
    # KeychainManager.delete_feishu_account("company")
