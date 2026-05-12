"""
PowerPoint 文档解析器
"""

import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class PowerPointParser:
    """PowerPoint 文档解析器"""

    SUPPORTED_EXTENSIONS = ['.pptx', '.ppt']

    @staticmethod
    def parse(file_path: str, max_length: int = 10000) -> Optional[str]:
        """
        解析 PowerPoint 文档

        Args:
            file_path: 文件路径
            max_length: 最大内容长度（默认 10000 字符）

        Returns:
            文档内容（只读操作）
        """
        try:
            from pptx import Presentation

            # 只读模式打开
            prs = Presentation(file_path)

            # 提取所有幻灯片文本
            all_content = []

            for i, slide in enumerate(prs.slides):
                slide_content = []
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        slide_content.append(shape.text.strip())

                if slide_content:
                    all_content.append(f"--- 幻灯片 {i+1} ---\n" + "\n".join(slide_content))

            content = "\n\n".join(all_content)
            return content[:max_length] if len(content) > max_length else content

        except Exception as e:
            logger.error(f"解析 PowerPoint 文档失败: {file_path} - {e}")
            return None
