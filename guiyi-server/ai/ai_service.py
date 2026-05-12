"""
AI 文档总结服务

使用 OpenAI 兼容 API 生成文档摘要和标签
支持大文件分段处理
支持超时重试机制（参考 Claude Code CLI）
"""

import os
import json
import logging
import time
import random
from typing import Optional, Dict, List
import hashlib

from .config_store import AIConfigStore

logger = logging.getLogger(__name__)


class AIService:
    """AI 文档总结服务"""

    # 重试配置（参考 Claude Code CLI）
    # Claude Code: 最大 10 次重试，延迟约 30-40 秒
    DEFAULT_MAX_RETRIES = 10
    INITIAL_RETRY_DELAY = 1.0   # 初始延迟（秒）
    MAX_RETRY_DELAY = 60.0     # 最大延迟 60 秒
    DEFAULT_TIMEOUT = 600.0    # 默认超时 10 分钟

    def __init__(self, config_store: AIConfigStore = None):
        """
        初始化 AI 服务

        Args:
            config_store: 配置存储实例
        """
        self.config_store = config_store or AIConfigStore()

    def _calculate_retry_delay(self, attempt: int) -> float:
        """
        计算重试延迟（指数退避 + 抖动）

        参考 Claude Code CLI 的重试策略：
        - 指数退避
        - 随机抖动避免同时重试
        - 最大延迟约 60 秒

        Args:
            attempt: 当前重试次数（从 0 开始）

        Returns:
            等待时间（秒）
        """
        # 指数退避：1s, 2s, 4s, 8s, 16s, 32s, 60s...
        delay = min(self.INITIAL_RETRY_DELAY * (2 ** attempt), self.MAX_RETRY_DELAY)

        # 添加随机抖动（±25%）
        jitter = 1.0 + (random.random() - 0.5) * 0.5
        return delay * jitter

    def _call_api(
        self,
        messages: List[Dict],
        max_tokens: int = None,
        timeout: float = None,
        max_retries: int = None
    ) -> Optional[str]:
        """
        调用 AI API（带重试机制）

        参考 Claude Code CLI 的重试策略：
        - 最多重试 10 次
        - 指数退避：1s -> 2s -> 4s -> ... -> 60s
        - 随机抖动
        - 10 分钟超时

        Args:
            messages: 消息列表
            max_tokens: 最大 token 数
            timeout: 超时时间（秒），默认 10 分钟
            max_retries: 最大重试次数，默认 10

        Returns:
            AI 响应内容
        """
        config = self.config_store.get_config()

        if not config.api_key:
            logger.warning("AI API Key 未配置")
            return None

        max_retries = max_retries if max_retries is not None else self.DEFAULT_MAX_RETRIES
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                import httpx

                headers = {
                    "Authorization": f"Bearer {config.api_key}",
                    "Content-Type": "application/json"
                }

                payload = {
                    "model": config.model,
                    "messages": messages,
                    "max_tokens": max_tokens or config.max_tokens,
                    "temperature": 0.3
                }

                with httpx.Client(timeout=timeout) as client:
                    response = client.post(
                        f"{config.api_base.rstrip('/')}/chat/completions",
                        headers=headers,
                        json=payload
                    )

                    if response.status_code == 200:
                        result = response.json()
                        return result["choices"][0]["message"]["content"]

                    elif response.status_code == 429:
                        # 速率限制，读取 retry-after 头
                        retry_after = self._parse_retry_after_header(response.headers)
                        if retry_after and 0 < retry_after <= 60:
                            logger.warning(f"API 速率限制，等待 {retry_after:.1f} 秒后重试 (attempt {attempt + 1}/{max_retries + 1})...")
                            time.sleep(retry_after)
                        else:
                            delay = self._calculate_retry_delay(attempt)
                            logger.warning(f"API 速率限制，等待 {delay:.1f} 秒后重试 (attempt {attempt + 1}/{max_retries + 1})...")
                            time.sleep(delay)
                        continue

                    elif response.status_code >= 500:
                        # 服务器错误，重试
                        last_error = f"服务器错误: {response.status_code}"
                        logger.warning(f"AI API 服务器错误 (attempt {attempt + 1}/{max_retries + 1}): {response.status_code}")

                    else:
                        # 其他错误，不重试
                        logger.error(f"AI API 调用失败: {response.status_code} - {response.text[:200]}")
                        return None

            except httpx.TimeoutException as e:
                last_error = "请求超时"
                logger.warning(f"AI API 请求超时 (attempt {attempt + 1}/{max_retries + 1})")

            except httpx.ConnectError as e:
                last_error = "连接失败"
                logger.warning(f"AI API 连接失败 (attempt {attempt + 1}/{max_retries + 1}): {e}")

            except Exception as e:
                last_error = str(e)
                logger.error(f"AI API 调用异常 (attempt {attempt + 1}/{max_retries + 1}): {e}")

            # 计算等待时间并重试
            if attempt < max_retries:
                delay = self._calculate_retry_delay(attempt)
                logger.info(f"等待 {delay:.1f} 秒后重试...")
                time.sleep(delay)

        logger.error(f"AI API 调用失败，已重试 {max_retries} 次: {last_error}")
        return None

    def _parse_retry_after_header(self, headers) -> Optional[float]:
        """
        解析 Retry-After 头

        Args:
            headers: HTTP 响应头

        Returns:
            等待时间（秒）
        """
        # 先尝试 retry-after-ms
        retry_ms = headers.get("retry-after-ms")
        if retry_ms:
            try:
                return float(retry_ms) / 1000.0
            except ValueError:
                pass

        # 再尝试 retry-after
        retry_after = headers.get("retry-after")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                # 可能是日期格式
                import email.utils
                retry_date_tuple = email.utils.parsedate_tz(retry_after)
                if retry_date_tuple:
                    retry_date = email.utils.mktime_tz(retry_date_tuple)
                    return max(0.0, retry_date - time.time())

        return None

    def _parse_json_response(self, response: str) -> Optional[Dict]:
        """
        解析 JSON 响应

        Args:
            response: AI 响应文本

        Returns:
            解析后的字典
        """
        if not response:
            return None

        try:
            # 尝试直接解析
            return json.loads(response)
        except json.JSONDecodeError:
            # 尝试提取 JSON 块
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

        logger.warning(f"无法解析 AI 响应为 JSON: {response[:200]}")
        return None

    def summarize_chunk(self, content: str, title: str, file_type: str, position: str = "中间") -> Optional[str]:
        """
        总结文档片段

        Args:
            content: 片段内容
            title: 文档标题
            file_type: 文件类型
            position: 片段位置（开头/中间/结尾）

        Returns:
            片段摘要
        """
        config = self.config_store.get_config()
        prompt_template = config.get_partial_prompt()

        prompt = prompt_template.format(
            title=title,
            file_type=file_type,
            position=position,
            content=content[:3000]  # 限制片段长度
        )

        messages = [{"role": "user", "content": prompt}]
        return self._call_api(messages, max_tokens=300)

    def merge_summaries(self, summaries: List[str], title: str) -> Optional[Dict]:
        """
        合并多个片段摘要

        Args:
            summaries: 片段摘要列表
            title: 文档标题

        Returns:
            合并后的分析结果
        """
        config = self.config_store.get_config()
        prompt_template = config.get_merge_prompt()

        prompt = prompt_template.format(
            title=title,
            summaries="\n\n".join([f"片段{i+1}: {s}" for i, s in enumerate(summaries)])
        )

        messages = [{"role": "user", "content": prompt}]
        response = self._call_api(messages, max_tokens=config.max_tokens)

        return self._parse_json_response(response)

    def summarize_document(
        self,
        content: str,
        title: str = "",
        file_type: str = ""
    ) -> Optional[Dict]:
        """
        总结文档内容

        对于大文档，采用分段策略：
        1. 内容较小：直接总结
        2. 内容较大：分段总结后合并

        Args:
            content: 文档内容
            title: 文档标题
            file_type: 文件类型

        Returns:
            {
                "summary": "文档摘要",
                "tags": ["标签1", "标签2", ...],
                "key_info": ["要点1", "要点2", ...]
            }
        """
        if not self.config_store.is_enabled():
            logger.debug("AI 服务未启用，跳过总结")
            return None

        content_length = len(content)
        config = self.config_store.get_config()

        # 判断是否需要分段
        if self.config_store.needs_chunking(content_length):
            logger.info(f"大文件分段处理: {title} ({content_length} 字符)")
            return self._summarize_large_document(content, title, file_type)

        # 直接总结
        prompt_template = config.get_summary_prompt()
        prompt = prompt_template.format(
            title=title or "无标题",
            file_type=file_type or "未知",
            content=content[:10000]  # 限制内容长度
        )

        messages = [{"role": "user", "content": prompt}]
        response = self._call_api(messages, max_tokens=config.max_tokens)

        result = self._parse_json_response(response)
        if result:
            # 规范化返回格式
            return {
                "summary": result.get("summary", ""),
                "tags": result.get("tags", []),
                "key_info": result.get("key_info", [])
            }
        return None

    def _summarize_large_document(self, content: str, title: str, file_type: str) -> Optional[Dict]:
        """
        分段总结大文档

        策略：取开头、中间、结尾三部分，分别总结后合并

        Args:
            content: 文档内容
            title: 文档标题
            file_type: 文件类型

        Returns:
            合并后的分析结果
        """
        chunk_size = self.config_store.get_chunk_size_chars()
        total_length = len(content)

        # 取三个关键片段
        chunks = []
        positions = []

        # 开头
        chunks.append(content[:chunk_size])
        positions.append("开头")

        # 中间
        mid_start = (total_length - chunk_size) // 2
        if mid_start > chunk_size:
            chunks.append(content[mid_start:mid_start + chunk_size])
            positions.append("中间")

        # 结尾
        if total_length > chunk_size * 2:
            chunks.append(content[-chunk_size:])
            positions.append("结尾")

        # 分段总结
        partial_summaries = []
        for i, (chunk, pos) in enumerate(zip(chunks, positions)):
            logger.debug(f"处理片段 {i+1}/{len(chunks)} ({pos})")
            summary = self.summarize_chunk(chunk, title, file_type, pos)
            if summary:
                partial_summaries.append(summary)

        if not partial_summaries:
            logger.warning(f"所有片段总结失败: {title}")
            return None

        # 合并摘要
        if len(partial_summaries) == 1:
            # 只有一个片段，尝试解析为最终结果
            result = self._parse_json_response(partial_summaries[0])
            if result:
                return {
                    "summary": result.get("summary", ""),
                    "tags": result.get("tags", []),
                    "key_info": result.get("key_info", [])
                }

        # 多个片段需要合并
        logger.debug(f"合并 {len(partial_summaries)} 个片段摘要")
        return self.merge_summaries(partial_summaries, title)

    def test_connection(self, api_base: str = None, api_key: str = None, model: str = None) -> bool:
        """
        测试 API 连接

        Args:
            api_base: API 地址
            api_key: API Key
            model: 模型名称

        Returns:
            是否连接成功
        """
        try:
            import httpx

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": model,
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 10
            }

            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{api_base.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=payload
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"AI API 连接测试失败: {e}")
            return False

    @staticmethod
    def calculate_file_hash(file_path: str) -> str:
        """
        计算文件内容哈希

        Args:
            file_path: 文件路径

        Returns:
            MD5 哈希值
        """
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"计算文件哈希失败: {file_path} - {e}")
            return ""

    @staticmethod
    def get_file_info(file_path: str) -> Dict:
        """
        获取文件信息（用于增量检测）

        Args:
            file_path: 文件路径

        Returns:
            {
                "size": 文件大小,
                "mtime": 修改时间
            }
        """
        try:
            stat_info = os.stat(file_path)
            return {
                "size": stat_info.st_size,
                "mtime": stat_info.st_mtime
            }
        except Exception as e:
            logger.error(f"获取文件信息失败: {file_path} - {e}")
            return {"size": 0, "mtime": 0}
