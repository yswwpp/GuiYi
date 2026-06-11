"""
PDF 文档解析器
"""

import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class PDFParser:
    """PDF 文档解析器"""

    SUPPORTED_EXTENSIONS = ['.pdf']

    @staticmethod
    def parse(file_path: str, max_length: int = 10000) -> Optional[str]:
        """
        解析 PDF 文档

        Args:
            file_path: 文件路径
            max_length: 最大内容长度（默认 10000 字符）

        Returns:
            文档内容（只读操作）
        """
        try:
            from PyPDF2 import PdfReader

            # 只读模式打开
            reader = PdfReader(file_path)

            # 提取文本（最多前 20 页）
            pages = []
            for i, page in enumerate(reader.pages[:20]):
                text = page.extract_text()
                if text and text.strip():
                    pages.append(text.strip())

            content = "\n\n".join(pages)
            return content[:max_length] if len(content) > max_length else content

        except Exception as e:
            logger.error(f"解析 PDF 文档失败: {file_path} - {e}")
            return None
