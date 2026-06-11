"""
关键词提取服务 - 可插拔设计

支持多种实现：
- OllamaKeywordExtractor: 本地 Ollama（HTTP API）
- OpenAIKeywordExtractor: OpenAI 格式 API（兼容百度千帆、DeepSeek等）
- MockKeywordExtractor: 用于测试
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 预编译正则表达式（避免每次调用重新编译）
_KEYWORD_JSON_PATTERNS = [
    re.compile(r'\{[^{}]*"keywords"[^{}]*\[[^\]]*\][^{}]*\}'),
    re.compile(r'\{"keywords"\s*:\s*\[[^\]]*\]\s*,?\s*"intent"[^}]*\}'),
    re.compile(r'\{"intent"[^}]*,?\s*"keywords"\s*:\s*\[[^\]]*\][^}]*\}'),
]
_FALLBACK_JSON_PATTERN = re.compile(r'\{[\s\S]*\}')


@dataclass
class KeywordExtractorConfig:
    """关键词提取器配置"""
    enabled: bool = True
    extractor_type: str = "ollama"  # "ollama" | "openai" | "mock"

    # Ollama 配置
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:9b"

    # OpenAI 格式 API 配置（兼容百度千帆、DeepSeek等）
    api_url: str = ""
    api_key: str = ""
    api_model: str = ""

    # 提示词配置
    custom_prompt: str = ""  # 空则使用默认


# 默认提示词
DEFAULT_KEYWORD_PROMPT = """从查询中提取关键词用于搜索。

查询：{query}

直接返回 JSON 格式（不要其他内容）：
{{"keywords": ["关键词列表"], "intent": "搜索意图"}}"""


class KeywordExtractorBase(ABC):
    """关键词提取器基类 - 所有实现必须继承"""

    @abstractmethod
    def extract(self, query: str, prompt_template: str = None) -> Optional[Dict]:
        """
        提取关键词

        Args:
            query: 用户原始查询
            prompt_template: 自定义提示词模板（可选）

        Returns:
            {
                "keywords": ["关键词列表"],
                "intent": "搜索意图",
                "enhanced_query": "增强后的查询"
            }
            或 None 表示失败
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """检查服务是否可用"""
        pass

    def _parse_response(self, text: str) -> Optional[Dict]:
        """解析 JSON 响应"""
        try:
            # 尝试直接解析
            result = json.loads(text)
            return result
        except json.JSONDecodeError:
            # 使用预编译的正则表达式
            for pattern in _KEYWORD_JSON_PATTERNS:
                json_match = pattern.search(text)
                if json_match:
                    try:
                        return json.loads(json_match.group())
                    except json.JSONDecodeError:
                        continue

            # 回退：找最后一个完整的 JSON 对象
            json_match = _FALLBACK_JSON_PATTERN.search(text)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            logger.warning(f"无法解析 JSON 响应: {text[:200]}")
            return None

    def _build_enhanced_query(self, original_query: str, keywords: List[str]) -> str:
        """构建增强查询"""
        if not keywords:
            return original_query

        # 预计算小写形式，避免循环内重复计算
        query_lower = original_query.lower()
        new_keywords = [k for k in keywords if k.lower() not in query_lower]

        if new_keywords:
            return f"{original_query} {' '.join(new_keywords)}"

        return original_query


class OllamaKeywordExtractor(KeywordExtractorBase):
    """本地 Ollama 实现

    通过 HTTP API 调用本地部署的模型
    默认地址: http://localhost:11434
    """

    def __init__(self, url: str = "http://localhost:11434", model: str = "qwen2.5:9b"):
        self.url = url.rstrip('/')
        self.model = model
        self._available = None
        self._client = None  # 延迟初始化，复用连接

    def _get_client(self):
        """获取 HTTP 客户端（复用连接）"""
        if self._client is None:
            import httpx
            self._client = httpx.Client(timeout=30.0)
        return self._client

    def is_available(self) -> bool:
        """检查 Ollama 服务是否可用"""
        if self._available is None:
            try:
                client = self._get_client()
                response = client.get(f"{self.url}/api/tags", timeout=5.0)
                self._available = response.status_code == 200
                if self._available:
                    models = response.json().get('models', [])
                    model_names = [m.get('name', '').split(':')[0] for m in models]
                    if self.model.split(':')[0] not in model_names:
                        logger.warning(f"模型 {self.model} 不存在，可用模型: {model_names}")
            except Exception as e:
                logger.warning(f"Ollama 服务不可用: {e}")
                self._available = False

        return self._available

    def extract(self, query: str, prompt_template: str = None) -> Optional[Dict]:
        """调用 Ollama 提取关键词"""
        if not query:
            return None

        if not self.is_available():
            logger.warning("Ollama 服务不可用")
            return None

        template = prompt_template or DEFAULT_KEYWORD_PROMPT
        prompt = template.format(query=query)

        try:
            headers = {"Content-Type": "application/json"}

            # 使用 chat API + think=false 关闭思考模式，响应更快
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,  # 关闭思考模式
                "options": {
                    "temperature": 0.3,
                    "num_predict": 500
                }
            }

            client = self._get_client()
            response = client.post(f"{self.url}/api/chat", headers=headers, json=payload)

            if response.status_code == 200:
                result = response.json()
                # chat API 返回 message.content
                message = result.get("message", {})
                text = message.get("content", "")

                parsed = self._parse_response(text)
                if parsed:
                    keywords = parsed.get("keywords", [])
                    intent = parsed.get("intent", "")

                    return {
                        "keywords": keywords,
                        "intent": intent,
                        "enhanced_query": self._build_enhanced_query(query, keywords)
                    }
            else:
                logger.error(f"Ollama API 调用失败: {response.status_code}")

        except Exception as e:
            logger.error(f"Ollama 关键词提取失败: {e}")

        return None


class OpenAIKeywordExtractor(KeywordExtractorBase):
    """OpenAI 格式 API 实现

    兼容:
    - OpenAI API
    - 百度千帆（OpenAI兼容模式）
    - DeepSeek
    - 其他兼容 OpenAI 格式的服务
    """

    def __init__(self, url: str, api_key: str, model: str):
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
        return bool(self.api_key and self.url)

    def extract(self, query: str, prompt_template: str = None) -> Optional[Dict]:
        """调用 API 提取关键词"""
        if not query or not self.api_key:
            return None

        template = prompt_template or DEFAULT_KEYWORD_PROMPT
        prompt = template.format(query=query)

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 200
            }

            client = self._get_client()
            response = client.post(f"{self.url}/chat/completions", headers=headers, json=payload)

            if response.status_code == 200:
                result = response.json()
                choices = result.get("choices", [])
                if choices:
                    text = choices[0].get("message", {}).get("content", "")

                    parsed = self._parse_response(text)
                    if parsed:
                        keywords = parsed.get("keywords", [])
                        intent = parsed.get("intent", "")

                        return {
                            "keywords": keywords,
                            "intent": intent,
                            "enhanced_query": self._build_enhanced_query(query, keywords)
                        }
            else:
                logger.error(f"API 调用失败: {response.status_code} - {response.text[:200]}")

        except Exception as e:
            logger.error(f"API 关键词提取失败: {e}")

        return None


class MockKeywordExtractor(KeywordExtractorBase):
    """Mock 提取器 - 用于测试"""

    def is_available(self) -> bool:
        return True

    def extract(self, query: str, prompt_template: str = None) -> Optional[Dict]:
        """Mock 提取：简单分词"""
        # 简单提取：取查询中的关键词
        words = query.split()
        keywords = [w for w in words if len(w) > 2][:5]

        return {
            "keywords": keywords,
            "intent": "查找文档",
            "enhanced_query": query
        }


# 工厂方法
def create_keyword_extractor(config: KeywordExtractorConfig) -> KeywordExtractorBase:
    """根据配置创建关键词提取器实例"""
    extractor_type = config.extractor_type.lower()

    if extractor_type == "ollama":
        return OllamaKeywordExtractor(config.ollama_url, config.ollama_model)
    elif extractor_type == "openai":
        if not config.api_url or not config.api_key:
            logger.warning("OpenAI API 配置不完整，使用 Mock")
            return MockKeywordExtractor()
        return OpenAIKeywordExtractor(config.api_url, config.api_key, config.api_model)
    elif extractor_type == "mock":
        return MockKeywordExtractor()
    else:
        logger.warning(f"未知的提取器类型: {extractor_type}, 使用 Mock")
        return MockKeywordExtractor()


# 导出
__all__ = [
    'KeywordExtractorConfig',
    'KeywordExtractorBase',
    'OllamaKeywordExtractor',
    'OpenAIKeywordExtractor',
    'MockKeywordExtractor',
    'create_keyword_extractor',
    'DEFAULT_KEYWORD_PROMPT'
]