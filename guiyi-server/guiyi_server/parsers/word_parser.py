"""
Word 文档解析器
"""

import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class WordParser:
    """Word 文档解析器"""

    SUPPORTED_EXTENSIONS = ['.docx', '.doc']

    @staticmethod
    def parse(file_path: str, max_length: int = 50000) -> Optional[str]:
        """
        解析 Word 文档

        Args:
            file_path: 文件路径
            max_length: 最大内容长度

        Returns:
            文档内容（只读操作）
        """
        try:
            from docx import Document

            # 只读模式打开
            doc = Document(file_path)

            # 提取所有段落文本
            paragraphs = []
            for para in doc.paragraphs:
                if para.text.strip():
                    paragraphs.append(para.text)

            # 提取表格文本
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join([cell.text.strip() for cell in row.cells if cell.text.strip()])
                    if row_text:
                        paragraphs.append(row_text)

            content = "\n".join(paragraphs)
            return content[:max_length] if len(content) > max_length else content

        except Exception as e:
            logger.error(f"解析 Word 文档失败: {file_path} - {e}")
            return None
