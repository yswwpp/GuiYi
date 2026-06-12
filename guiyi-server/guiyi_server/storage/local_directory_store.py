"""
本地目录配置存储 - 使用 MySQL 存储目录配置
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass
import logging
import pymysql
from pymysql.cursors import DictCursor

from guiyi_server.sync.metadata import DatabaseConfig
from guiyi_server.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LocalDirectory:
    """本地目录配置"""
    id: str
    name: str
    path: str
    file_types: List[str]  # 如 ['.md', '.txt', '.py']
    exclude_patterns: List[str]  # 按目录名匹配，如 ['node_modules', '.git']
    exclude_paths: List[str] = None  # 按相对路径排除子目录，如 ['tools', 'a/b/c']
    enabled: bool = True
    max_depth: int = 10
    max_file_size_mb: int = 10
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.exclude_paths is None:
            self.exclude_paths = []

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'path': self.path,
            'file_types': self.file_types,
            'exclude_patterns': self.exclude_patterns,
            'exclude_paths': self.exclude_paths,
            'enabled': self.enabled,
            'max_depth': self.max_depth,
            'max_file_size_mb': self.max_file_size_mb,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class LocalDirectoryStore:
    """本地目录配置存储管理"""

    # 默认排除的模式
    DEFAULT_EXCLUDE_PATTERNS = [
        # 版本控制
        '.git', '.svn', '.hg',
        # 依赖和缓存
        'node_modules', '__pycache__', '.venv', 'venv', 'env',
        # IDE 配置
        '.idea', '.vscode', '.settings',
        # 构建产物
        'dist', 'build', 'target', 'out', 'bin',
        # 系统文件
        '.DS_Store', 'Thumbs.db',
        # 配置文件目录
        'config', 'conf', '.config',
    ]

    # 默认支持的文件类型（文档类型，不含代码和图片）
    DEFAULT_FILE_TYPES = [
        # 文本文档
        '.md', '.txt', '.markdown',
        # Office 文档
        '.docx', '.doc',      # Word
        '.xlsx', '.xls',      # Excel
        '.pptx', '.ppt',      # PowerPoint
        # PDF
        '.pdf',
    ]

    # 图片类型（可选，需显式启用）
    IMAGE_FILE_TYPES = [
        '.jpg', '.jpeg', '.png', '.webp', '.bmp'
    ]

    # 禁止索引的敏感路径
    FORBIDDEN_PATHS = [
        '~/.ssh', '~/.gnupg', '~/.password-store',
        '/etc', '/var', '/usr', '/bin', '/sbin',
        '/System', '/Library', '/Applications'
    ]

    def __init__(self):
        self.db_config = DatabaseConfig()
        self._init_db()
        logger.info("本地目录配置存储初始化完成: MySQL")

    def _get_connection(self):
        """获取数据库连接"""
        return pymysql.connect(**self.db_config.mysql_config)

    def _execute(self, query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False):
        """执行 SQL 语句"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor(DictCursor if fetch_one or fetch_all else None)
            cursor.execute(query, params)

            result = None
            if fetch_one:
                row = cursor.fetchone()
                if row:
                    result = dict(row) if isinstance(row, dict) else dict(row)
            elif fetch_all:
                rows = cursor.fetchall()
                result = [dict(row) if isinstance(row, dict) else dict(row) for row in rows]
            else:
                result = cursor.lastrowid

            conn.commit()
            return result
        finally:
            conn.close()

    def _init_db(self):
        """初始化数据库表"""
        config = self.db_config.mysql_config.copy()
        db_name = config.pop('database')

        conn = pymysql.connect(**config)
        cursor = conn.cursor()

        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` DEFAULT CHARACTER SET utf8mb4")
        cursor.execute(f"USE `{db_name}`")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS local_directories (
                id VARCHAR(255) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                path VARCHAR(512) NOT NULL,
                file_types TEXT,
                exclude_patterns TEXT,
                exclude_paths TEXT,
                enabled TINYINT(1) DEFAULT 1,
                max_depth INT DEFAULT 10,
                max_file_size_mb INT DEFAULT 10,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE INDEX idx_path (path)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # 旧表追加 exclude_paths 列（幂等）
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'local_directories' AND COLUMN_NAME = 'exclude_paths'
        """, (db_name,))
        if cursor.fetchone()[0] == 0:
            cursor.execute("ALTER TABLE local_directories ADD COLUMN exclude_paths TEXT AFTER exclude_patterns")
            logger.info("已为 local_directories 表追加 exclude_paths 列")

        conn.commit()
        conn.close()
        logger.info("MySQL 本地目录表初始化完成")

    def _is_path_forbidden(self, path: str) -> bool:
        """
        检查路径是否在禁止列表中

        Args:
            path: 要检查的路径

        Returns:
            是否禁止
        """
        expanded_path = os.path.expanduser(path)
        abs_path = os.path.abspath(expanded_path)

        for forbidden in self.FORBIDDEN_PATHS:
            forbidden_expanded = os.path.expanduser(forbidden)
            forbidden_abs = os.path.abspath(forbidden_expanded)
            if abs_path.startswith(forbidden_abs):
                return True

        return False

    def add_directory(self, directory: LocalDirectory) -> bool:
        """
        添加目录配置

        Args:
            directory: 目录配置

        Returns:
            是否添加成功
        """
        # 检查路径是否存在
        expanded_path = os.path.expanduser(directory.path)
        if not os.path.isdir(expanded_path):
            logger.error(f"目录不存在: {directory.path}")
            return False

        # 检查是否在禁止列表中
        if self._is_path_forbidden(directory.path):
            logger.error(f"禁止索引的路径: {directory.path}")
            return False

        try:
            self._execute("""
                INSERT INTO local_directories
                (id, name, path, file_types, exclude_patterns, exclude_paths, enabled, max_depth, max_file_size_mb)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                directory.id,
                directory.name,
                directory.path,
                json.dumps(directory.file_types),
                json.dumps(directory.exclude_patterns),
                json.dumps(directory.exclude_paths or []),
                1 if directory.enabled else 0,
                directory.max_depth,
                directory.max_file_size_mb
            ))
            logger.info(f"添加目录配置: {directory.name} -> {directory.path}")
            return True
        except pymysql.IntegrityError as e:
            logger.error(f"目录配置已存在: {e}")
            return False
        except Exception as e:
            logger.error(f"添加目录配置失败: {e}")
            return False

    def get_directory(self, dir_id: str) -> Optional[LocalDirectory]:
        """
        获取目录配置

        Args:
            dir_id: 目录 ID

        Returns:
            目录配置，不存在返回 None
        """
        try:
            row = self._execute(
                "SELECT * FROM local_directories WHERE id = %s",
                (dir_id,),
                fetch_one=True
            )
            if row:
                return self._row_to_directory(row)
            return None
        except Exception as e:
            logger.error(f"获取目录配置失败: {e}")
            return None

    def list_directories(self, enabled_only: bool = False) -> List[LocalDirectory]:
        """
        列出所有目录配置

        Args:
            enabled_only: 是否只返回启用的目录

        Returns:
            目录配置列表
        """
        try:
            if enabled_only:
                rows = self._execute(
                    "SELECT * FROM local_directories WHERE enabled = 1",
                    fetch_all=True
                )
            else:
                rows = self._execute(
                    "SELECT * FROM local_directories",
                    fetch_all=True
                )
            return [self._row_to_directory(r) for r in (rows or [])]
        except Exception as e:
            logger.error(f"列出目录配置失败: {e}")
            return []

    def update_directory(self, dir_id: str, **kwargs) -> bool:
        """
        更新目录配置

        Args:
            dir_id: 目录 ID
            **kwargs: 要更新的字段

        Returns:
            是否更新成功
        """
        try:
            sets = []
            params = []

            for key, value in kwargs.items():
                if key == 'file_types' and isinstance(value, list):
                    sets.append("file_types = %s")
                    params.append(json.dumps(value))
                elif key == 'exclude_patterns' and isinstance(value, list):
                    sets.append("exclude_patterns = %s")
                    params.append(json.dumps(value))
                elif key == 'exclude_paths' and isinstance(value, list):
                    sets.append("exclude_paths = %s")
                    params.append(json.dumps(value))
                elif key == 'enabled':
                    sets.append("enabled = %s")
                    params.append(1 if value else 0)
                elif key in ('name', 'path', 'max_depth', 'max_file_size_mb'):
                    sets.append(f"{key} = %s")
                    params.append(value)

            if not sets:
                return False

            sets.append("updated_at = %s")
            params.append(datetime.now())
            params.append(dir_id)

            self._execute(
                f"UPDATE local_directories SET {', '.join(sets)} WHERE id = %s",
                tuple(params)
            )
            logger.info(f"更新目录配置: {dir_id}")
            return True
        except Exception as e:
            logger.error(f"更新目录配置失败: {e}")
            return False

    def delete_directory(self, dir_id: str) -> bool:
        """
        删除目录配置

        Args:
            dir_id: 目录 ID

        Returns:
            是否删除成功
        """
        try:
            self._execute("DELETE FROM local_directories WHERE id = %s", (dir_id,))
            logger.info(f"删除目录配置: {dir_id}")
            return True
        except Exception as e:
            logger.error(f"删除目录配置失败: {e}")
            return False

    def _row_to_directory(self, row: dict) -> LocalDirectory:
        """将数据库行转换为 LocalDirectory 对象"""
        return LocalDirectory(
            id=row['id'],
            name=row['name'],
            path=row['path'],
            file_types=json.loads(row['file_types']) if row['file_types'] else [],
            exclude_patterns=json.loads(row['exclude_patterns']) if row['exclude_patterns'] else [],
            exclude_paths=json.loads(row['exclude_paths']) if row.get('exclude_paths') else [],
            enabled=bool(row['enabled']),
            max_depth=row['max_depth'],
            max_file_size_mb=row['max_file_size_mb'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

    @staticmethod
    def get_supported_file_types() -> List[str]:
        """
        获取支持的文件类型列表（包含图片类型）

        Returns:
            所有支持的文件类型列表
        """
        return LocalDirectoryStore.DEFAULT_FILE_TYPES.copy() + LocalDirectoryStore.IMAGE_FILE_TYPES.copy()

    @staticmethod
    def get_default_file_types() -> List[str]:
        """
        获取默认文件类型列表（不含图片）

        Returns:
            默认文件类型列表
        """
        return LocalDirectoryStore.DEFAULT_FILE_TYPES.copy()

    @staticmethod
    def get_image_file_types() -> List[str]:
        """
        获取图片文件类型列表

        Returns:
            图片文件类型列表
        """
        return LocalDirectoryStore.IMAGE_FILE_TYPES.copy()

    @staticmethod
    def get_default_exclude_patterns() -> List[str]:
        """获取默认排除模式列表"""
        return LocalDirectoryStore.DEFAULT_EXCLUDE_PATTERNS.copy()
