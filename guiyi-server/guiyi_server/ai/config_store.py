"""
AI 服务配置存储
"""

import os
import json
from typing import Optional
from dataclasses import dataclass, asdict
import logging

from guiyi_server.config import settings

logger = logging.getLogger(__name__)

# 默认提示词模板
DEFAULT_SUMMARY_PROMPT = """你是一个文档分析助手。请分析以下文档内容，生成：
1. 简洁的摘要（不超过200字）
2. 3-5个关键词标签
3. 核心要点（2-3条）

文档标题：{title}
文档类型：{file_type}

文档内容：
{content}

请以 JSON 格式返回：
{{
    "summary": "摘要内容",
    "tags": ["标签1", "标签2", "标签3"],
    "key_info": ["要点1", "要点2"]
}}"""

DEFAULT_PARTIAL_PROMPT = """你是一个文档分析助手。这是大文档的片段摘要任务。

文档标题：{title}
文档类型：{file_type}
片段位置：{position}

片段内容：
{content}

请简要总结这个片段的关键内容（不超过100字）："""

DEFAULT_MERGE_PROMPT = """你是一个文档分析助手。请合并以下片段摘要，生成完整文档的分析：

文档标题：{title}

片段摘要列表：
{summaries}

请生成：
1. 完整摘要（不超过300字）
2. 5-8个关键词标签
3. 核心要点（3-5条）

以 JSON 格式返回：
{{
    "summary": "摘要内容",
    "tags": ["标签1", "标签2"],
    "key_info": ["要点1", "要点2"]
}}"""


@dataclass
class AIConfig:
    """AI 服务配置"""
    # === AI 总结服务配置（现有）===
    enabled: bool = False
    api_base: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    summary_threshold_kb: int = 10  # 超过 10KB 触发 AI 总结
    max_tokens: int = 1000  # AI 响应最大 token 数
    chunk_size_kb: int = 8  # 大文件分段大小（KB）
    max_content_kb: int = 50  # 最大处理内容大小（KB），超过则分段
    summary_prompt: str = ""  # 完整内容提示词模板
    partial_prompt: str = ""  # 片段提示词模板
    merge_prompt: str = ""  # 合并提示词模板

    # === AI 搜索增强配置（新增）===
    # 总开关和子开关
    ai_search_enabled: bool = False  # 总开关：AI 搜索增强
    keyword_extraction_enabled: bool = True  # 子开关：关键词提取
    rerank_enabled: bool = True  # 子开关：智能重排

    # 关键词提取配置（可插拔）
    keyword_extractor_type: str = "ollama"  # "ollama" | "openai" | "mock"
    keyword_ollama_url: str = "http://localhost:11434"
    keyword_ollama_model: str = "qwen2.5:9b"
    keyword_api_url: str = ""  # OpenAI 格式 API 地址
    keyword_api_key: str = ""
    keyword_api_model: str = ""
    keyword_prompt: str = ""  # 自定义提示词

    # Rerank 配置（可插拔）
    reranker_type: str = "bge"  # "bge" | "cohere" | "jina" | "mock"
    reranker_bge_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_cohere_url: str = "https://api.cohere.ai/v1"
    reranker_cohere_key: str = ""
    reranker_cohere_model: str = "rerank-v3.5"
    reranker_jina_url: str = "https://api.jina.ai/v1/rerank"
    reranker_jina_key: str = ""
    reranker_jina_model: str = "jina-reranker-v2-base-multilingual"
    rerank_top_n: int = 20

    def to_dict(self) -> dict:
        d = asdict(self)
        # 不返回敏感信息
        d['api_key'] = '******' if self.api_key else ''
        d['keyword_api_key'] = '******' if self.keyword_api_key else ''
        d['reranker_cohere_key'] = '******' if self.reranker_cohere_key else ''
        d['reranker_jina_key'] = '******' if self.reranker_jina_key else ''
        return d

    def get_summary_prompt(self) -> str:
        """获取完整提示词模板"""
        return self.summary_prompt or DEFAULT_SUMMARY_PROMPT

    def get_partial_prompt(self) -> str:
        """获取片段提示词模板"""
        return self.partial_prompt or DEFAULT_PARTIAL_PROMPT

    def get_merge_prompt(self) -> str:
        """获取合并提示词模板"""
        return self.merge_prompt or DEFAULT_MERGE_PROMPT

    @classmethod
    def from_dict(cls, data: dict) -> 'AIConfig':
        # 过滤掉不属于该类的字段，使用默认值填充缺失字段
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


class AIConfigStore:
    """AI 配置存储管理"""

    def __init__(self, config_path: str = None):
        """
        初始化配置存储

        Args:
            config_path: 配置文件路径
        """
        if config_path is None:
            config_path = settings.AI_CONFIG_PATH

        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        self.config_path = config_path
        self._config = self._load_config()
        logger.info(f"AI 配置存储初始化完成: {config_path}")

    def _load_config(self) -> AIConfig:
        """加载配置"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return AIConfig.from_dict(data)
            except Exception as e:
                logger.warning(f"加载 AI 配置失败: {e}")
        return AIConfig()

    def _save_config(self):
        """保存配置"""
        import tempfile
        save_data = asdict(self._config)
        # 原子写入：先写临时文件，再重命名
        fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(self.config_path))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, self.config_path)
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def get_config(self) -> AIConfig:
        """获取配置"""
        return self._config

    def update_config(self, **kwargs) -> bool:
        """
        更新配置

        Args:
            **kwargs: 要更新的配置项

        Returns:
            是否更新成功
        """
        try:
            changed = False
            for key, value in kwargs.items():
                if hasattr(self._config, key):
                    current = getattr(self._config, key)
                    if current != value:
                        setattr(self._config, key, value)
                        changed = True
            if changed:
                self._save_config()
                logger.info(f"AI 配置已更新: {list(kwargs.keys())}")
            return True
        except Exception as e:
            logger.error(f"更新 AI 配置失败: {e}")
            return False

    def is_enabled(self) -> bool:
        """AI 服务是否启用"""
        return self._config.enabled and bool(self._config.api_key)

    def should_summarize(self, file_size_bytes: int) -> bool:
        """
        判断是否需要 AI 总结

        Args:
            file_size_bytes: 文件大小（字节）

        Returns:
            是否需要总结
        """
        if not self.is_enabled():
            return False

        threshold_bytes = self._config.summary_threshold_kb * 1024
        return file_size_bytes > threshold_bytes

    def needs_chunking(self, content_length: int) -> bool:
        """
        判断内容是否需要分段处理

        Args:
            content_length: 内容长度（字符数）

        Returns:
            是否需要分段
        """
        # 估算：1KB 约等于 500 个中文字符
        max_chars = self._config.max_content_kb * 500
        return content_length > max_chars

    def get_chunk_size_chars(self) -> int:
        """获取分段大小（字符数）"""
        return self._config.chunk_size_kb * 500
