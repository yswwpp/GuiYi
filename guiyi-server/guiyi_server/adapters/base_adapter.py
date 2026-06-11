"""
数据源适配器抽象基类
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class BaseAdapter(ABC):
    """数据源适配器抽象基类"""

    @abstractmethod
    def fetch_all_for_index(self, account: Optional[str] = None) -> List[Dict]:
        """
        获取所有文档用于索引

        Args:
            account: 指定账号名称（可选）

        Returns:
            文档列表，每个文档包含:
            - id: 文档唯一标识
            - title: 文档标题
            - content: 文档内容
            - url: 原文链接（如有）
            - source: 数据源标识
            - account: 账号标识
            - doc_type: 文档类型
            - updated_at: 更新时间戳
        """
        pass

    @abstractmethod
    def get_document_content(self, doc_id: str, **kwargs) -> Optional[str]:
        """
        获取文档内容

        Args:
            doc_id: 文档 ID
            **kwargs: 额外参数（如 file_path, doc_token 等）

        Returns:
            文档内容字符串
        """
        pass

    def supports_write(self) -> bool:
        """
        是否支持写入操作

        Returns:
            默认返回 False，只读适配器不需要重写此方法
        """
        return False
