#!/usr/bin/env python3
"""
凭证从 macOS Keychain 迁移到 JSON 文件

用法：
    cd ~/deploy/GuiYi/guiyi-server
    /Users/yswwpp/deploy/GuiYi/.venv/bin/python scripts/migrate_keychain_to_file.py

迁移完成后，在 .venv 中可以卸载 keyring 依赖。
此脚本是一次性工具，迁移成功后可删除。

注意：脚本会从 Keychain 读取凭证，最后会触发若干次 Keychain 密码弹窗。
在 macOS 弹窗中点"始终允许"可以减少弹窗次数。
"""

import json
import os
import stat
import sys
import tempfile
from pathlib import Path


def main() -> int:
    # 必须用 keyring 直接读，不走 KeychainManager（KeychainManager 已经是文件版本）
    try:
        import keyring
    except ImportError:
        print("ERROR: keyring 库未安装，无法从 Keychain 读取凭证", file=sys.stderr)
        print("请先 pip install keyring，运行迁移后再卸载", file=sys.stderr)
        return 1

    SERVICE_NAME = "GuiYi"

    # 待迁移的飞书账号（从原 load_saved_feishu_accounts 硬编码列表来）
    feishu_accounts = ["wiki_user"]

    # 待迁移的印象笔记账号（从 yinxiang_accounts.json 读）
    data_dir = Path(os.getenv("GUIYI_DATA_DIR", "")).expanduser().resolve()
    yinxiang_names_file = data_dir / "yinxiang_accounts.json"
    yinxiang_accounts = []
    if yinxiang_names_file.exists():
        try:
            yinxiang_accounts = json.loads(yinxiang_names_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"警告: 读取 {yinxiang_names_file} 失败: {e}", file=sys.stderr)

    # 凭证文件路径
    credentials_path = data_dir.parent / "config" / "credentials.json"
    credentials_path = Path(os.getenv("GUIYI_CREDENTIALS_FILE", str(credentials_path))).expanduser().resolve()

    print(f"目标凭证文件: {credentials_path}")
    print(f"待迁移飞书账号: {feishu_accounts}")
    print(f"待迁移印象笔记账号: {yinxiang_accounts}")
    print()

    if credentials_path.exists():
        existing = json.loads(credentials_path.read_text(encoding="utf-8"))
        print(f"凭证文件已存在，现有内容: feishu={list(existing.get('feishu', {}).keys())}, "
              f"yinxiang={list(existing.get('yinxiang', {}).keys())}")
        data = existing
    else:
        data = {}

    # 迁移飞书
    feishu_data = data.setdefault("feishu", {})
    for name in feishu_accounts:
        account_key = f"feishu_{name}"
        app_id = keyring.get_password(SERVICE_NAME, f"{account_key}_app_id")
        app_secret = keyring.get_password(SERVICE_NAME, f"{account_key}_app_secret")
        user_access_token = keyring.get_password(SERVICE_NAME, f"{account_key}_user_access_token")
        refresh_token = keyring.get_password(SERVICE_NAME, f"{account_key}_refresh_token")

        if not (app_id and app_secret):
            print(f"  [跳过] feishu/{name}: 未在 Keychain 中找到 app_id/app_secret")
            continue

        entry = {"app_id": app_id, "app_secret": app_secret}
        if user_access_token:
            entry["user_access_token"] = user_access_token
        if refresh_token:
            entry["refresh_token"] = refresh_token
        feishu_data[name] = entry
        token_status = []
        if user_access_token:
            token_status.append("user_access_token")
        if refresh_token:
            token_status.append("refresh_token")
        print(f"  [成功] feishu/{name}: app_id={app_id[:8]}..., {', '.join(token_status) if token_status else '无 token'}")

    # 迁移印象笔记
    yinxiang_data = data.setdefault("yinxiang", {})
    for name in yinxiang_accounts:
        account_key = f"yinxiang_{name}"
        token = keyring.get_password(SERVICE_NAME, f"{account_key}_token")
        note_store_url = keyring.get_password(SERVICE_NAME, f"{account_key}_note_store_url")

        if not (token and note_store_url):
            print(f"  [跳过] yinxiang/{name}: 未在 Keychain 中找到 token/note_store_url")
            continue

        yinxiang_data[name] = {"token": token, "note_store_url": note_store_url}
        print(f"  [成功] yinxiang/{name}: token={token[:8]}..., url={note_store_url[:40]}...")

    # 清理空 section
    if not data.get("feishu"):
        data.pop("feishu", None)
    if not data.get("yinxiang"):
        data.pop("yinxiang", None)

    if not data:
        print("\n没有可迁移的凭证，退出。")
        return 0

    # 原子写入
    credentials_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(credentials_path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, str(credentials_path))
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    os.chmod(str(credentials_path), stat.S_IRUSR | stat.S_IWUSR)

    print(f"\n✓ 已写入 {credentials_path}")
    print(f"  飞书账号数: {len(data.get('feishu', {}))}")
    print(f"  印象笔记账号数: {len(data.get('yinxiang', {}))}")
    print(f"\n下一步：重启 GuiYi 服务，确认接口正常后可以从 Keychain 中清理这些条目")
    print("        以及从 requirements.txt 中移除 keyring 依赖")
    return 0


if __name__ == "__main__":
    sys.exit(main())
