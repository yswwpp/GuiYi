"""
Obsidian 存储管理
"""

from pathlib import Path
from typing import Optional, List
import shutil
from datetime import datetime
import logging

# 配置日志
logger = logging.getLogger(__name__)


class ObsidianStorage:
    """Obsidian 存储管理器"""

    def __init__(self, vault_path: str = "data/obsidian_vault"):
        """
        初始化存储管理器

        Args:
            vault_path: Obsidian 库路径
        """
        self.vault_path = Path(vault_path)
        self.inbox_path = self.vault_path / "inbox"
        self.assets_path = self.inbox_path / "assets"

        # 创建目录
        self.inbox_path.mkdir(parents=True, exist_ok=True)
        self.assets_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Obsidian 存储初始化完成: {self.vault_path}")

    def save_markdown(self, filename: str, content: str) -> str:
        """
        保存 Markdown 文件

        Args:
            filename: 文件名
            content: 文件内容

        Returns:
            保存的文件路径
        """
        logger.debug(f"保存文件: {filename}")
        file_path = self.inbox_path / filename

        # 如果文件已存在，添加时间戳
        if file_path.exists():
            stem = file_path.stem
            suffix = file_path.suffix
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"{stem}_{timestamp}{suffix}"
            file_path = self.inbox_path / filename
            logger.debug(f"文件已存在，重命名为: {filename}")

        # 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"文件保存成功: {file_path}")
        return str(file_path)

    def get_file_path(self, filename: str) -> Optional[Path]:
        """
        获取文件路径

        Args:
            filename: 文件名

        Returns:
            文件路径（如果存在）
        """
        file_path = self.inbox_path / filename
        return file_path if file_path.exists() else None

    def list_files(self) -> List[Path]:
        """
        列出所有 Markdown 文件

        Returns:
            文件路径列表
        """
        files = list(self.inbox_path.glob("*.md"))
        logger.debug(f"列出文件，共 {len(files)} 个")
        return files

    def delete_file(self, filename: str) -> bool:
        """
        删除文件

        Args:
            filename: 文件名

        Returns:
            是否成功
        """
        logger.debug(f"删除文件: {filename}")
        file_path = self.inbox_path / filename
        if file_path.exists():
            file_path.unlink()
            logger.info(f"文件删除成功: {filename}")
            return True
        logger.warning(f"文件不存在，无法删除: {filename}")
        return False

    def get_storage_info(self) -> dict:
        """
        获取存储信息

        Returns:
            存储统计信息
        """
        files = self.list_files()
        total_size = sum(f.stat().st_size for f in files if f.is_file())

        return {
            "total_files": len(files),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "vault_path": str(self.vault_path),
            "inbox_path": str(self.inbox_path)
        }
