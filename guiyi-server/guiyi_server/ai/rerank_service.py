"""
Rerank 重排服务 - 可插拔设计

支持多种实现：
- BGEReranker: 本地 bge-reranker-v2-m3
- CohereReranker: Cohere API
- JinaReranker: Jina AI API
"""

import logging
import math
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RerankConfig:
    """重排器配置"""
    enabled: bool = False
    reranker_type: str = "bge"  # "bge" | "cohere" | "jina"

    # BGE 本地模型配置
    bge_model: str = "BAAI/bge-reranker-v2-m3"

    # Cohere API 配置
    cohere_url: str = "https://api.cohere.ai/v1"
    cohere_key: str = ""
    cohere_model: str = "rerank-v3.5"

    # Jina API 配置
    jina_url: str = "https://api.jina.ai/v1/rerank"
    jina_key: str = ""
    jina_model: str = "jina-reranker-v2-base-multilingual"

    # 通用配置
    top_n: int = 20
    vector_score_weight: float = 0.3  # 向量分数权重
    rerank_score_weight: float = 0.7  # 重排分数权重


class RerankerBase(ABC):
    """重排器基类 - 所有实现必须继承"""

    @abstractmethod
    def rerank(self, query: str, documents: List[Dict], top_n: int = None) -> List[Dict]:
        """
        对搜索结果重排

        Args:
            query: 原始查询
            documents: 搜索结果列表，每个文档包含:
                - id, title, text, score 等字段
            top_n: 返回数量

        Returns:
            重排后的结果列表，每个文档新增:
                - rerank_score: 重排分数
                - final_score: 综合分数
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """检查模型/服务是否可用"""
        pass

    def _calculate_final_score(self, vector_score: float, rerank_score: float) -> float:
        """计算综合分数"""
        # 使用默认权重（可从 RerankConfig 实例获取）
        return vector_score * 0.3 + rerank_score * 0.7

    def _process_api_result(self, response: Dict, documents: List[Dict]) -> List[Dict]:
        """处理 API 响应（Cohere/Jina 通用）"""
        results = response.get("results", [])
        reranked_docs = []

        for r in results:
            index = r.get("index", 0)
            relevance_score = r.get("relevance_score", 0.0)

            if index < len(documents):
                doc = documents[index].copy()
                doc['rerank_score'] = relevance_score
                doc['final_score'] = self._calculate_final_score(
                    doc.get('score', 0.0),
                    relevance_score
                )
                reranked_docs.append(doc)

        return reranked_docs


class BGEReranker(RerankerBase):
    """本地 BGE Reranker 实现

    使用 sentence_transformers CrossEncoder
    首次加载自动下载模型（约 1.2GB）
    """

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        self.model_name = model_name
        self._model = None  # 延迟加载
        self._available = None

    def _load_model(self):
        """延迟加载模型"""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                logger.info(f"正在加载 BGE Reranker 模型: {self.model_name}")
                self._model = CrossEncoder(self.model_name)
                self._available = True
                logger.info(f"BGE Reranker 模型加载成功")
            except Exception as e:
                logger.error(f"BGE Reranker 模型加载失败: {e}")
                self._available = False
                raise

    def is_available(self) -> bool:
        """检查模型是否可用"""
        if self._available is None:
            try:
                self._load_model()
            except Exception:
                return False
        return self._available

    def rerank(self, query: str, documents: List[Dict], top_n: int = None) -> List[Dict]:
        """使用 BGE Reranker 重排"""
        if not documents:
            return documents

        # 确保模型已加载
        self._load_model()

        if not self._available:
            logger.warning("BGE Reranker 不可用，返回原始结果")
            return documents

        top_n = top_n or len(documents)

        try:
            # 构建查询-文档对
            pairs = []
            for doc in documents:
                doc_text = f"{doc.get('title', '')}\n{doc.get('text', '')}"
                pairs.append((query, doc_text))

            # 执行重排
            scores = self._model.predict(pairs)

            # 合并结果
            reranked_docs = []
            for i, score in enumerate(scores):
                # BGE Reranker 输出是 logits，使用 sigmoid 转换成 0-1 概率分数
                # sigmoid(x) = 1 / (1 + exp(-x))
                normalized_score = 1 / (1 + math.exp(-float(score)))

                doc = documents[i].copy()
                doc['rerank_score'] = normalized_score  # 归一化后的分数 (0-1)
                doc['final_score'] = self._calculate_final_score(
                    doc.get('score', 0.0),
                    normalized_score
                )
                reranked_docs.append(doc)

            # 按重排分数排序
            reranked_docs.sort(key=lambda x: x.get('rerank_score', 0), reverse=True)

            # 返回 top_n
            return reranked_docs[:top_n]

        except Exception as e:
            logger.error(f"BGE Rerank 执行失败: {e}")
            return documents  # fallback


class CohereReranker(RerankerBase):
    """Cohere API Reranker 实现"""

    def __init__(self, url: str, api_key: str, model: str = "rerank-v3.5"):
        self.url = url.rstrip('/')
        self.api_key = api_key
        self.model = model
        self._client = None  # 延迟初始化，复用连接

    def _get_client(self):
        """获取 HTTP 客户端（复用连接）"""
        if self._client is None:
            import httpx
            self._client = httpx.Client(timeout=30.0)
        return self._client

    def is_available(self) -> bool:
        return bool(self.api_key)

    def rerank(self, query: str, documents: List[Dict], top_n: int = None) -> List[Dict]:
        """使用 Cohere API 重排"""
        if not documents or not self.api_key:
            return documents

        top_n = top_n or len(documents)

        try:
            doc_texts = [f"{d.get('title', '')}\n{d.get('text', '')}" for d in documents]

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.model,
                "query": query,
                "documents": doc_texts,
                "top_n": min(top_n, len(documents))
            }

            client = self._get_client()
            response = client.post(f"{self.url}/rerank", headers=headers, json=payload)

            if response.status_code == 200:
                return self._process_api_result(response.json(), documents)
            else:
                logger.error(f"Cohere API 调用失败: {response.status_code}")
                return documents

        except Exception as e:
            logger.error(f"Cohere Rerank 执行失败: {e}")
            return documents


class JinaReranker(RerankerBase):
    """Jina AI API Reranker 实现"""

    def __init__(self, url: str, api_key: str, model: str = "jina-reranker-v2-base-multilingual"):
        self.url = url
        self.api_key = api_key
        self.model = model
        self._client = None  # 延迟初始化，复用连接

    def _get_client(self):
        """获取 HTTP 客户端（复用连接）"""
        if self._client is None:
            import httpx
            self._client = httpx.Client(timeout=30.0)
        return self._client

    def is_available(self) -> bool:
        return bool(self.api_key)

    def rerank(self, query: str, documents: List[Dict], top_n: int = None) -> List[Dict]:
        """使用 Jina API 重排"""
        if not documents or not self.api_key:
            return documents

        top_n = top_n or len(documents)

        try:
            doc_texts = [f"{d.get('title', '')}\n{d.get('text', '')}" for d in documents]

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.model,
                "query": query,
                "documents": doc_texts,
                "top_n": min(top_n, len(documents))
            }

            client = self._get_client()
            response = client.post(self.url, headers=headers, json=payload)

            if response.status_code == 200:
                return self._process_api_result(response.json(), documents)
            else:
                logger.error(f"Jina API 调用失败: {response.status_code}")
                return documents

        except Exception as e:
            logger.error(f"Jina Rerank 执行失败: {e}")
            return documents


class MockReranker(RerankerBase):
    """Mock 重排器 - 用于测试"""

    def is_available(self) -> bool:
        return True

    def rerank(self, query: str, documents: List[Dict], top_n: int = None) -> List[Dict]:
        """Mock 重排：简单返回原始结果"""
        for doc in documents:
            doc['rerank_score'] = doc.get('score', 0.0)
            doc['final_score'] = doc.get('score', 0.0)
        return documents


# 工厂方法
def create_reranker(config: RerankConfig) -> RerankerBase:
    """根据配置创建重排器实例"""
    reranker_type = config.reranker_type.lower()

    if reranker_type == "bge":
        return BGEReranker(config.bge_model)
    elif reranker_type == "cohere":
        return CohereReranker(config.cohere_url, config.cohere_key, config.cohere_model)
    elif reranker_type == "jina":
        return JinaReranker(config.jina_url, config.jina_key, config.jina_model)
    elif reranker_type == "mock":
        return MockReranker()
    else:
        logger.warning(f"未知的重排器类型: {reranker_type}, 使用 Mock")
        return MockReranker()


# 导出
__all__ = [
    'RerankConfig',
    'RerankerBase',
    'BGEReranker',
    'CohereReranker',
    'JinaReranker',
    'MockReranker',
    'create_reranker'
]