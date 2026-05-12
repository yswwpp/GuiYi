"""
txtai 语义索引管理

优化版本：最小化内存使用
- 使用 faiss 后端，不存储内容到 SQLite
- 向量索引只存储 ID 和嵌入向量
- 文档内容单独存储在 JSON 元数据文件
"""

from txtai import Embeddings
from pathlib import Path
from typing import List, Dict, Optional
import json
import logging

# 配置日志
logger = logging.getLogger(__name__)

# 最大内容长度（字符）- 用于嵌入和预览
# 嵌入使用较短长度，让关键信息（标题）权重更高
MAX_EMBEDDING_LENGTH = 1500   # 嵌入使用的最大字符数（缩短以提高关键信息权重）
MAX_PREVIEW_LENGTH = 50000    # 预览最大字符数（增大以包含完整表格内容）
MIN_CONTENT_LENGTH = 50       # 最小内容长度，过滤空内容文档（避免文件夹节点干扰搜索）


class IndexManager:
    """语义索引管理器"""

    def __init__(self, index_path: str = "data/index"):
        """
        初始化索引管理器

        Args:
            index_path: 索引存储路径
        """
        logger.info(f"初始化索引管理器: {index_path}")
        self.index_path = Path(index_path)
        self.index_path.mkdir(parents=True, exist_ok=True)

        # 初始化 txtai Embeddings
        # 关键优化：不使用 content 存储，避免 SQLite 序列化问题
        logger.info("加载向量模型: BAAI/bge-m3")
        self.embeddings = Embeddings(
            path="BAAI/bge-m3",
            content=False,     # 禁用内容存储！这是关键
            objects=False,     # 不存储原始对象
            backend="faiss"    # 使用 faiss 后端
        )

        # 索引文件路径（txtai保存索引的目录）
        self.index_dir = self.index_path / "documents"

        # 元数据文件路径（存储完整的文档信息）
        self.metadata_file = self.index_path / "metadata.json"
        self.metadata = self._load_metadata()

        # 加载已有索引
        doc_count = 0
        if self.index_dir.exists():
            try:
                self.embeddings.load(str(self.index_dir))
                doc_count = self.embeddings.count()
            except Exception as e:
                logger.warning(f"加载索引失败: {e}")

        logger.info(f"索引管理器初始化完成，当前文档数: {len(self.metadata)} (索引: {doc_count})")

    def _load_metadata(self) -> Dict:
        """加载元数据"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                logger.debug("加载元数据文件")
                return json.load(f)
        logger.debug("元数据文件不存在，创建空元数据")
        return {}

    def _save_metadata(self) -> None:
        """保存元数据"""
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        logger.debug("元数据保存完成")

    def index_document(self, doc: Dict) -> None:
        """
        索引单个文档

        Args:
            doc: 文档数据（包含 id, title, content, url 等）
        """
        doc_id = doc["id"]
        logger.debug(f"索引文档: {doc_id}")

        content = doc.get('content', '')
        title = doc["title"]

        # 过滤内容过短的文档（空内容文件夹节点）
        if len(content) < MIN_CONTENT_LENGTH:
            logger.debug(f"跳过空内容文档: {doc_id} (标题: {title}, 内容长度: {len(content)})")
            return

        # 优化嵌入内容：标题重复以提高权重，解决标题精确匹配问题
        # 格式：标题(重复) + 关键实体 + 内容摘要
        key_entities = self._extract_key_entities(content)

        # 标题重复3次，确保标题关键词权重最高
        title_boost = f"{title}\n{title}\n{title}\n"

        if key_entities:
            text_for_embedding = f"{title_boost}\n工作表: {key_entities}\n\n{content}"[:MAX_EMBEDDING_LENGTH]
        else:
            text_for_embedding = f"{title_boost}\n\n{content}"[:MAX_EMBEDDING_LENGTH]

        # 添加到向量索引（使用元组格式）
        self.embeddings.upsert([(doc_id, text_for_embedding)])

        # 保存元数据
        content_preview = content[:MAX_PREVIEW_LENGTH] if len(content) > MAX_PREVIEW_LENGTH else content
        self.metadata[doc_id] = {
            "id": doc_id,
            "title": title,
            "url": doc["url"],
            "source": doc.get("source", "web"),
            "account": doc.get("account"),
            "saved_at": doc.get("saved_at"),
            "content_preview": content_preview,
            }
        self._save_metadata()

        # 保存索引
        self._save_index()

        logger.info(f"文档索引成功: {doc_id} (标题: {doc['title']})")

    def _extract_key_entities(self, content: str) -> str:
        """
        从内容中提取关键实体（如工作表名称）

        Args:
            content: 文档内容

        Returns:
            提取的关键实体字符串
        """
        import re

        # 提取飞书表格的工作表名称
        # 格式：【工作表：xxx】或【工作表列表】xxx | xxx | xxx
        sheet_names = []

        # 从工作表列表中提取
        list_match = re.search(r'【工作表列表】\s*(.+?)(?:\n|【)', content)
        if list_match:
            names_text = list_match.group(1)
            sheet_names = [name.strip() for name in names_text.split('|') if name.strip()]

        # 从单个工作表标题中提取
        for match in re.finditer(r'【工作表：([^】]+)】', content):
            name = match.group(1).strip()
            if name and name not in sheet_names:
                sheet_names.append(name)

        if sheet_names:
            return ', '.join(sheet_names[:20])  # 最多20个，避免过长

        return ""

    def index_documents(self, docs: List[Dict]) -> None:
        """
        批量索引文档

        Args:
            docs: 文档列表
        """
        logger.info(f"批量索引 {len(docs)} 个文档")
        data = []
        skipped_empty = 0

        for doc in docs:
            doc_id = doc["id"]
            content = doc.get('content', doc.get('content_summary', ''))
            title = doc["title"]

            # 过滤内容过短的文档
            if len(content) < MIN_CONTENT_LENGTH:
                skipped_empty += 1
                continue

            # 优化嵌入内容：标题重复以提高权重
            key_entities = self._extract_key_entities(content)
            title_boost = f"{title}\n{title}\n{title}\n"

            if key_entities:
                text_for_embedding = f"{title_boost}\n工作表: {key_entities}\n\n{content}"[:MAX_EMBEDDING_LENGTH]
            else:
                text_for_embedding = f"{title_boost}\n\n{content}"[:MAX_EMBEDDING_LENGTH]

            # 使用元组格式 (id, text) - 更轻量
            data.append((doc_id, text_for_embedding))

            # 保存元数据到独立 JSON 文件
            content_preview = content[:MAX_PREVIEW_LENGTH] if len(content) > MAX_PREVIEW_LENGTH else content
            self.metadata[doc_id] = {
                "id": doc_id,
                "title": title,
                "url": doc["url"],
                "source": doc.get("source", "web"),
                "account": doc.get("account"),
                "saved_at": doc.get("saved_at"),
                "content_preview": content_preview,
            }

        # 批量添加到索引
        try:
            self.embeddings.upsert(data)
        except Exception as e:
            logger.error(f"批量索引失败: {e}")
            # 尝试逐个索引
            for doc_id, text in data:
                try:
                    self.embeddings.upsert([(doc_id, text)])
                except Exception as e2:
                    logger.error(f"索引文档 {doc_id} 失败: {e2}")

        # 保存
        self._save_metadata()
        self._save_index()

        if skipped_empty > 0:
            logger.info(f"批量索引完成，共 {len(data)} 个文档（跳过 {skipped_empty} 个空内容文档）")
        else:
            logger.info(f"批量索引完成，共 {len(data)} 个文档")

    def search(
        self,
        query: str,
        source: Optional[str] = None,
        account: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        语义搜索

        Args:
            query: 搜索查询
            source: 数据源筛选
            account: 账号筛选
            limit: 返回结果数量

        Returns:
            搜索结果列表
        """
        logger.debug(f"执行搜索: query='{query}', source={source}, account={account}, limit={limit}")

        # 执行搜索 - 返回 (id, score) 元组列表
        results = self.embeddings.search(query, limit)

        # 格式化结果
        formatted_results = []
        for result in results:
            # content=False 时返回的是 (id, score) 元组
            if isinstance(result, tuple):
                uid, score = result
            else:
                uid = result.get("id")
                score = result.get("score", 0.0)

            # 从元数据中获取文档信息
            doc_data = self.metadata.get(uid, {})
            if not doc_data:
                continue

            # 应用筛选条件
            if source and doc_data.get("source") != source:
                continue
            if account and doc_data.get("account") != account:
                continue

            formatted_results.append({
                "id": uid,
                "title": doc_data.get("title"),
                "url": doc_data.get("url"),
                "source": doc_data.get("source"),
                "account": doc_data.get("account"),
                "score": float(score),
                "text": doc_data.get("content_preview", "")[:200]
            })

        logger.info(f"搜索完成，返回 {len(formatted_results)} 个结果")
        return formatted_results

    def delete_document(self, doc_id: str) -> None:
        """
        删除文档索引

        Args:
            doc_id: 文档 ID
        """
        logger.debug(f"删除文档索引: {doc_id}")
        self.embeddings.delete([doc_id])
        if doc_id in self.metadata:
            del self.metadata[doc_id]
            self._save_metadata()
        self._save_index()
        logger.info(f"文档索引删除成功: {doc_id}")

    def _save_index(self) -> None:
        """保存索引到磁盘"""
        self.embeddings.save(str(self.index_dir))
        logger.debug(f"索引已保存到: {self.index_dir}")

    def save(self) -> None:
        """手动保存索引和元数据"""
        self._save_index()
        self._save_metadata()
        logger.info(f"索引和元数据已保存，文档数: {self.embeddings.count()}")

    def load_index(self) -> bool:
        """
        从磁盘加载索引

        Returns:
            是否成功加载
        """
        if self.index_dir.exists():
            self.embeddings.load(str(self.index_dir))
            logger.info(f"索引加载成功，文档数: {self.embeddings.count()}")
            return True
        logger.info("索引目录不存在，跳过加载")
        return False

    def get_stats(self) -> Dict:
        """
        获取索引统计信息

        Returns:
            统计信息
        """
        # 获取文档数量
        count = self.embeddings.count()

        return {
            "total_documents": count,
            "index_path": str(self.index_path),
            "model": "BAAI/bge-m3"
        }
