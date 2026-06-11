"""
纯文本文件解析器
"""

import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class TxtParser:
    """纯文本文件解析器"""

    SUPPORTED_EXTENSIONS = ['.txt']

    @staticmethod
    def parse(file_path: str, max_length: int = 50000) -> Optional[str]:
        """
        解析纯文本文件

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
            logger.error(f"解析文本文件失败: {file_path} - {e}")
            return None
