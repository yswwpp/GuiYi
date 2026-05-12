"""
Markdown 文件解析器
"""

import os
from typing import Optional
import logging
import re

logger = logging.getLogger(__name__)


class MarkdownParser:
    """Markdown 文件解析器"""

    SUPPORTED_EXTENSIONS = ['.md', '.markdown']

    @staticmethod
    def parse(file_path: str, max_length: int = 50000) -> Optional[str]:
        """
        解析 Markdown 文件

        Args:
            file_path: 文件路径
            max_length: 最大内容长度

        Returns:
            文件内容（只读操作）
        """
        try:
            # 只读模式打开文件
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(max_length)

            # 可选：提取标题作为元数据
            # 但不修改原文件，只是提取信息

            return content
        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    content = f.read(max_length)
                return content
            except Exception as e:
                logger.warning(f"无法解析文件 (编码问题): {file_path} - {e}")
                return None
        except Exception as e:
            logger.error(f"解析 Markdown 文件失败: {file_path} - {e}")
            return None

    @staticmethod
    def extract_title(content: str) -> Optional[str]:
        """
        从内容中提取标题（第一个 # 标题）

        Args:
            content: 文件内容

        Returns:
            标题文本（不修改原文件）
        """
        if not content:
            return None

        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()

        return None
