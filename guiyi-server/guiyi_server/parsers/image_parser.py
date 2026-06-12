"""
图片解析器 - 将图片转换为可搜索的文本描述
"""

import os
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)


class ImageParser:
    """
    图片解析器

    将图片通过 VLM 转换为结构化文本，包括：
    - 图片描述
    - 关键词标签
    - OCR 文字（如有）
    """

    SUPPORTED_EXTENSIONS = [
        '.jpg', '.jpeg', '.png', '.webp', '.bmp'
    ]

    @staticmethod
    def parse(file_path: str, max_length: int = 50000) -> Optional[str]:
        """
        解析图片文件

        Args:
            file_path: 图片文件路径
            max_length: 最大输出长度（预留，暂未使用）

        Returns:
            结构化的图片描述文本，失败返回 None
        """
        if not os.path.exists(file_path):
            logger.error(f"图片文件不存在: {file_path}")
            return None

        # 检查扩展名
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext not in ImageParser.SUPPORTED_EXTENSIONS:
            logger.warning(f"不支持的图片格式: {file_ext}")
            return None

        try:
            # 懒加载 ImageCaptioner
            from guiyi_server.ai.image_captioner import get_image_captioner

            captioner = get_image_captioner()

            # 检查是否启用
            if not captioner.enabled:
                logger.debug(f"图片索引未启用，跳过: {file_path}")
                return None

            # 检查是否可用
            if not captioner.is_available():
                logger.warning(f"图片描述服务不可用，跳过: {file_path}")
                return None

            # 生成描述和标签
            result = captioner.describe_and_tag(file_path)

            # 检查是否被跳过
            if result.get("skipped"):
                logger.debug(f"图片被跳过: {file_path}, 原因: {result.get('skip_reason')}")
                return None

            # 构建结构化文本
            text = ImageParser._build_text(
                file_path=file_path,
                description=result.get("description", ""),
                tags=result.get("tags", []),
                ocr_text=result.get("ocr_text", "")
            )

            return text

        except Exception as e:
            logger.error(f"图片解析失败: {file_path} - {e}")
            return None

    @staticmethod
    def _build_text(file_path: str, description: str, tags: List[str], ocr_text: str) -> str:
        """
        构建索引文本

        Args:
            file_path: 文件路径
            description: 图片描述
            tags: 标签列表
            ocr_text: OCR 文字

        Returns:
            结构化的文本内容
        """
        parts = []

        # 图片描述
        if description:
            parts.append("[图片描述]")
            parts.append(description)
            parts.append("")

        # 图片标签
        if tags:
            parts.append("[图片标签]")
            parts.append(", ".join(tags))
            parts.append("")

        # 图片文字
        if ocr_text:
            parts.append("[图片文字]")
            parts.append(ocr_text)
            parts.append("")

        # 文件信息
        filename = os.path.basename(file_path)
        file_ext = os.path.splitext(filename)[1][1:]  # 去掉点

        parts.append("[图片文件信息]")
        parts.append(f"文件名: {filename}")
        parts.append(f"扩展名: {file_ext}")

        return "\n".join(parts)

    @staticmethod
    def get_caption_data(file_path: str) -> Optional[dict]:
        """
        获取图片描述数据（用于元数据存储）

        Args:
            file_path: 图片文件路径

        Returns:
            包含 description, tags, ocr_text 的字典
        """
        if not os.path.exists(file_path):
            return None

        try:
            from guiyi_server.ai.image_captioner import get_image_captioner

            captioner = get_image_captioner()

            if not captioner.enabled or not captioner.is_available():
                return None

            result = captioner.describe_and_tag(file_path)

            if result.get("skipped"):
                return None

            return {
                "description": result.get("description", ""),
                "tags": result.get("tags", []),
                "ocr_text": result.get("ocr_text", "")
            }

        except Exception as e:
            logger.error(f"获取图片描述失败: {file_path} - {e}")
            return None
