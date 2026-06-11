#!/usr/bin/env python3
"""同步飞书知识库文档到GuiYi索引"""

import sys
import os
import logging
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from guiyi_server.adapters.feishu_adapter import FeishuAdapter, FeishuAccount
from guiyi_server.sync.metadata import SyncMetadata
from guiyi_server.index.txtai_index import IndexManager
from guiyi_server.storage.keychain import KeychainManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def sync_feishu_wiki():
    """同步飞书知识库文档"""

    logger.info("=" * 60)
    logger.info("开始同步飞书知识库文档")
    logger.info("=" * 60)

    # 1. 初始化组件
    logger.info("\n[1/4] 初始化组件...")

    # 初始化索引管理器
    index_manager = IndexManager()
    logger.info("✓ 索引管理器初始化完成")

    # 初始化同步元数据
    metadata = SyncMetadata()
    logger.info("✓ 同步元数据初始化完成")

    # 初始化飞书适配器
    adapter = FeishuAdapter()

    # 从 Keychain 加载账号
    credentials = KeychainManager.get_feishu_account('wiki_user')
    if not credentials:
        logger.error("未找到飞书账号 wiki_user，请先通过 API 添加账号")
        return {"error": "账号未配置"}

    account = FeishuAccount(
        name="wiki_user",
        app_id=credentials["app_id"],
        app_secret=credentials["app_secret"],
        user_access_token=credentials.get("user_access_token"),
        refresh_token=credentials.get("refresh_token")
    )

    # 刷新用户令牌
    if account.refresh_user_token():
        # 保存刷新后的令牌
        KeychainManager.save_feishu_account(
            name='wiki_user',
            app_id=account.app_id,
            app_secret=account.app_secret,
            user_access_token=account.user_access_token,
            refresh_token=account.refresh_token
        )
        logger.info("✓ 用户令牌已刷新并保存")
    else:
        logger.warning("用户令牌刷新失败，尝试使用现有令牌...")
        if not account.user_access_token:
            logger.error("没有可用的用户令牌")
            return {"error": "令牌不可用"}

    adapter.add_account(account)
    logger.info("✓ 飞书适配器初始化完成")

    # 2. 获取文档列表
    logger.info("\n[2/4] 获取知识库文档列表...")

    docs = adapter.fetch_all_for_index(account_name="wiki_user")
    logger.info(f"✓ 获取到 {len(docs)} 个文档")

    # 统计文档类型
    type_counts = {}
    for doc in docs:
        obj_type = doc.get('obj_type', 'unknown')
        type_counts[obj_type] = type_counts.get(obj_type, 0) + 1

    logger.info("文档类型统计:")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  - {t}: {c} 个")

    # 3. 获取文档内容并索引
    logger.info("\n[3/4] 获取文档内容并建立索引...")

    stats = {
        "added": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0
    }

    for i, doc in enumerate(docs):
        try:
            doc_id = doc["id"]
            title = doc.get("title", "unnamed")
            obj_type = doc.get("obj_type", "docx")

            # 获取文档内容
            if not doc.get('content'):
                doc_token = doc.get('doc_token')
                if doc_token:
                    content = adapter.get_document_content(
                        doc_id=doc_id,
                        doc_token=doc_token,
                        account_name="wiki_user",
                        user_access_token=account.user_access_token,
                        obj_type=obj_type
                    )
                    doc['content'] = content or ""

            content = doc.get('content', '')

            # 计算哈希
            import hashlib
            content_hash = hashlib.md5(content.encode()).hexdigest()

            # 检查是否需要更新
            last_state = metadata.get_doc_state(doc_id)

            if last_state is None:
                # 新增
                if content:
                    logger.info(f"  [{i+1}/{len(docs)}] [+] 新增: {title[:50]}... ({obj_type})")
                    index_manager.index_documents([doc])
                    metadata.upsert_doc(
                        doc_id=doc_id,
                        source="feishu",
                        account=doc.get("account"),
                        url=doc.get("url", ""),
                        title=title,
                        content_hash=content_hash,
                        last_modified=datetime.now().timestamp()
                    )
                    stats["added"] += 1
                else:
                    stats["skipped"] += 1

            elif last_state["content_hash"] != content_hash:
                # 更新
                if content:
                    logger.info(f"  [{i+1}/{len(docs)}] [~] 更新: {title[:50]}... ({obj_type})")
                    index_manager.index_documents([doc])
                    metadata.upsert_doc(
                        doc_id=doc_id,
                        source="feishu",
                        account=doc.get("account"),
                        url=doc.get("url", ""),
                        title=title,
                        content_hash=content_hash,
                        last_modified=datetime.now().timestamp()
                    )
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1

            else:
                stats["skipped"] += 1

        except Exception as e:
            logger.error(f"  [{i+1}/{len(docs)}] [!] 失败: {doc.get('title', 'unknown')} - {e}")
            stats["failed"] += 1

    # 4. 完成
    logger.info("\n[4/4] 同步完成!")
    logger.info(f"统计: 新增 {stats['added']}, 更新 {stats['updated']}, 跳过 {stats['skipped']}, 失败 {stats['failed']}")

    # 保存索引
    index_manager.save()
    logger.info("✓ 索引已保存")

    return stats

if __name__ == "__main__":
    try:
        sync_feishu_wiki()
    except KeyboardInterrupt:
        logger.info("\n用户中断")
    except Exception as e:
        logger.error(f"同步失败: {e}")
        import traceback
        traceback.print_exc()
