"""
增量同步引擎 - 支持用户身份和应用身份
"""

from typing import List, Dict, Optional
from datetime import datetime
import logging
import requests

from guiyi_server.sync.metadata import SyncMetadata
from guiyi_server.index.txtai_index import IndexManager

logger = logging.getLogger(__name__)


class SyncEngine:
    """增量同步引擎"""

    def __init__(self, metadata: SyncMetadata, index_manager: IndexManager):
        """
        Args:
            metadata: 同步元数据管理器
            index_manager: 索引管理器
        """
        self.metadata = metadata
        self.index = index_manager

    def sync_source(
        self,
        source_name: str,
        adapter,
        account: str = None,
        user_access_token: str = None
    ) -> Dict[str, int]:
        """
        同步单个数据源

        Args:
            source_name: 数据源名称（feishu/wps/yinxiang/quark）
            adapter: 对应的适配器实例
            account: 账号标识（可选）
            user_access_token: 用户访问令牌（可选，用于用户身份访问）

        Returns:
            统计信息字典
        """
        logger.info(f"[{datetime.now().isoformat()}] 开始同步 {source_name} ({account or 'default'})")

        # 1. 获取当前文档列表
        try:
            current_docs = adapter.fetch_all_for_index(account)
        except Exception as e:
            logger.error(f"获取文档列表失败 [{source_name}]: {e}")
            return {"added": 0, "updated": 0, "skipped": 0, "deleted": 0, "failed": 0}

        current_ids = {doc["id"] for doc in current_docs}

        stats = {
            "added": 0,
            "updated": 0,
            "skipped": 0,
            "deleted": 0,
            "failed": 0
        }

        # 2. 逐个文档对比并获取内容
        for doc in current_docs:
            try:
                doc_id = doc["id"]

                # 获取文档内容（如果没有）
                if not doc.get('content'):
                    content = self._fetch_document_content(
                        doc, adapter, account, user_access_token
                    )
                    doc['content'] = content

                # 计算哈希
                content = doc.get("content", "")
                content_hash = self.metadata._calculate_hash(content)

                # 获取最后修改时间
                last_modified = doc.get("updated_at")

                # 获取上次同步状态
                last_state = self.metadata.get_doc_state(doc_id)

                if last_state is None:
                    # 新增文档
                    if content:  # 只索引有内容的文档
                        logger.info(f"  [+] 新增：{doc['title']}")
                        self._add_document(doc, content_hash, last_modified)
                        stats["added"] += 1
                    else:
                        logger.debug(f"  [ ] 跳过空文档：{doc['title']}")
                        stats["skipped"] += 1

                elif last_state["content_hash"] != content_hash:
                    # 内容变更
                    if content:
                        logger.info(f"  [~] 更新：{doc['title']}")
                        self._update_document(doc, content_hash, last_modified)
                        stats["updated"] += 1
                    else:
                        stats["skipped"] += 1

                else:
                    # 未变更，跳过
                    stats["skipped"] += 1

            except Exception as e:
                logger.error(f"  [!] 失败：{doc.get('title', doc_id)} - {e}")
                self.metadata.log_sync(
                    source=source_name,
                    action="failed",
                    doc_id=doc_id,
                    doc_title=doc.get("title", ""),
                    account=account,
                    error=str(e)
                )
                stats["failed"] += 1

        # 3. 清理已删除文档
        try:
            deleted = self.metadata.cleanup_deleted(current_ids, source_name, account)
            for doc_id in deleted:
                logger.info(f"  [-] 删除：{doc_id}")
                self._delete_document(doc_id)
            stats["deleted"] = len(deleted)
        except Exception as e:
            logger.error(f"清理已删除文档失败: {e}")

        logger.info(f"[{datetime.now().isoformat()}] 同步完成：{stats}")
        return stats

    def _fetch_document_content(
        self,
        doc: Dict,
        adapter,
        account: str,
        user_access_token: str = None
    ) -> str:
        """获取文档内容"""
        try:
            doc_token = doc.get('doc_token')
            if not doc_token:
                return ""

            # 获取文档对象类型
            obj_type = doc.get('obj_type', 'docx')

            # 使用适配器获取内容
            content = adapter.get_document_content(
                doc_id=doc['id'],
                doc_token=doc_token,
                account_name=account,
                user_access_token=user_access_token,
                obj_type=obj_type
            )

            return content or ""

        except Exception as e:
            logger.warning(f"获取文档内容失败: {e}")
            return ""

    def _add_document(self, doc: Dict, content_hash: str, last_modified: float):
        """新增文档到索引"""
        try:
            self.index.index_documents([doc])

            self.metadata.upsert_doc(
                doc_id=doc["id"],
                source=doc.get("source", "unknown"),
                account=doc.get("account"),
                url=doc.get("url", ""),
                title=doc.get("title", "无标题"),
                content_hash=content_hash,
                last_modified=last_modified
            )
        except Exception as e:
            logger.error(f"新增文档失败: {e}")
            raise

    def _update_document(self, doc: Dict, content_hash: str, last_modified: float):
        """更新文档索引"""
        try:
            self.index.index_documents([doc])

            self.metadata.upsert_doc(
                doc_id=doc["id"],
                source=doc.get("source", "unknown"),
                account=doc.get("account"),
                url=doc.get("url", ""),
                title=doc.get("title", "无标题"),
                content_hash=content_hash,
                last_modified=last_modified
            )
        except Exception as e:
            logger.error(f"更新文档失败: {e}")
            raise

    def _delete_document(self, doc_id: str):
        """从索引中删除文档"""
        try:
            self.index.delete_document(doc_id)
        except Exception as e:
            logger.error(f"删除文档失败: {e}")
