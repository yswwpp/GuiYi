"""
WPS 在线文档适配器 - 通过 Chrome 插件接收文档

与其他适配器不同，WpsAdapter 是被动接收模式：
- 其他适配器主动拉取数据（调用 API、扫描文件）
- WpsAdapter 等待 Chrome 插件推送数据
"""

import hashlib
from datetime import datetime
from typing import Dict, List, Optional
import logging
import json
from pathlib import Path

from guiyi_server.config import settings, DATA_DIR

logger = logging.getLogger(__name__)


class WpsDocumentBuffer:
    """WPS 文档缓冲区（接收来自插件的文档）"""

    def __init__(self):
        self.documents: Dict[str, Dict] = {}  # doc_token -> document
        self.buffer_file = DATA_DIR / "wps_buffer.json"
        self._load_buffer()

    def _load_buffer(self):
        """加载缓冲区"""
        if self.buffer_file.exists():
            try:
                with open(self.buffer_file, 'r', encoding='utf-8') as f:
                    self.documents = json.load(f)
                logger.info(f"加载 WPS 缓冲区: {len(self.documents)} 个文档")
            except Exception as e:
                logger.warning(f"加载缓冲区失败: {e}")
                self.documents = {}

    def _save_buffer(self):
        """保存缓冲区"""
        try:
            self.buffer_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.buffer_file, 'w', encoding='utf-8') as f:
                json.dump(self.documents, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存缓冲区失败: {e}")

    def add_document(self, doc: Dict) -> str:
        """添加文档到缓冲区"""
        doc_token = doc.get('docToken') or doc.get('doc_token')
        if not doc_token:
            raise ValueError("缺少 doc_token")

        # 更新时间戳
        doc['received_at'] = datetime.now().timestamp()

        # 标准化字段名
        normalized_doc = {
            'id': doc.get('id') or f"wps_{doc.get('account', 'default')}_{doc_token}",
            'title': doc.get('title', '未命名文档'),
            'content': doc.get('content', '')[:50000],  # 限制内容长度
            'url': doc.get('url', ''),
            'source': 'wps',
            'account': f"wps_{doc.get('account', 'default')}",
            'doc_type': doc.get('docType') or doc.get('doc_type', 'doc'),
            'doc_token': doc_token,
            'updated_at': doc.get('updatedAt') or doc.get('updated_at') or datetime.now().timestamp(),
            'store_locally': False,
            'received_at': doc['received_at']
        }

        # 存储
        self.documents[doc_token] = normalized_doc
        self._save_buffer()

        logger.info(f"WPS 文档已缓冲: {doc_token} ({normalized_doc['title']})")
        return doc_token

    def get_document(self, doc_token: str) -> Optional[Dict]:
        """获取文档"""
        return self.documents.get(doc_token)

    def get_all_documents(self) -> List[Dict]:
        """获取所有文档"""
        return list(self.documents.values())

    def remove_document(self, doc_token: str):
        """移除文档"""
        if doc_token in self.documents:
            del self.documents[doc_token]
            self._save_buffer()

    def clear(self):
        """清空缓冲区"""
        self.documents.clear()
        self._save_buffer()


class WpsAdapter:
    """WPS 在线文档适配器"""

    def __init__(self):
        self.buffer = WpsDocumentBuffer()

    def receive_document(self, doc_data: Dict) -> Dict:
        """
        接收来自 Chrome 插件的文档

        Args:
            doc_data: 插件推送的文档数据

        Returns:
            处理结果
        """
        # 验证必要字段
        doc_token = doc_data.get('docToken') or doc_data.get('doc_token')
        if not doc_token:
            raise ValueError("缺少 doc_token")

        title = doc_data.get('title')
        if not title:
            raise ValueError("缺少 title")

        content = doc_data.get('content')
        if not content:
            raise ValueError("缺少 content")

        # 添加到缓冲区
        doc_token = self.buffer.add_document(doc_data)

        doc = self.buffer.get_document(doc_token)

        return {
            "status": "received",
            "doc_id": doc['id'],
            "doc_token": doc['doc_token'],
            "title": doc['title'],
            "message": f"文档已接收: {doc['title']}"
        }

    def fetch_all_for_index(self, account: Optional[str] = None) -> List[Dict]:
        """
        获取所有缓冲的文档用于索引

        Args:
            account: 账号标识（可选）

        Returns:
            文档列表
        """
        docs = self.buffer.get_all_documents()

        if account:
            docs = [d for d in docs if d.get('account') == account]

        logger.info(f"WPS 适配器返回 {len(docs)} 个文档")
        return docs

    def get_document_content(self, doc_id: str, **kwargs) -> Optional[str]:
        """
        获取文档内容

        Args:
            doc_id: 文档 ID

        Returns:
            文档内容
        """
        # 从缓冲区获取
        doc_token = doc_id.split('_')[-1]
        doc = self.buffer.get_document(doc_token)

        if doc:
            return doc.get('content', '')

        return None

    def clear_buffer(self):
        """清空缓冲区"""
        self.buffer.clear()


# 全局实例
wps_adapter = WpsAdapter()