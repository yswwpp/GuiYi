"""
本地目录配置存储 - 使用 SQLite 存储目录配置
"""

import os
import json
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, asdict
import logging
from sqlalchemy import create_engine, Column, String, Boolean, Text, DateTime, Integer
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

Base = declarative_base()


class LocalDirectoryModel(Base):
    """本地目录配置数据模型"""
    __tablename__ = 'local_directories'

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    path = Column(String, nullable=False, unique=True)
    file_types = Column(Text, default='[]')  # JSON 数组存储文件类型
    exclude_patterns = Column(Text, default='[]')  # JSON 数组存储排除模式
    enabled = Column(Boolean, default=True)
    max_depth = Column(Integer, default=10)
    max_file_size_mb = Column(Integer, default=10)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


@dataclass
class LocalDirectory:
    """本地目录配置"""
    id: str
    name: str
    path: str
    file_types: List[str]  # 如 ['.md', '.txt', '.py']
    exclude_patterns: List[str]  # 如 ['node_modules', '.git']
    enabled: bool = True
    max_depth: int = 10
    max_file_size_mb: int = 10
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'path': self.path,
            'file_types': self.file_types,
            'exclude_patterns': self.exclude_patterns,
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

    # 默认支持的文件类型（文档类型，不含代码）
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

    # 禁止索引的敏感路径
    FORBIDDEN_PATHS = [
        '~/.ssh', '~/.gnupg', '~/.password-store',
        '/etc', '/var', '/usr', '/bin', '/sbin',
        '/System', '/Library', '/Applications'
    ]

    def __init__(self, db_path: str = None):
        """
        初始化存储

        Args:
            db_path: 数据库路径，默认为 data/local_directories.sqlite
        """
        if db_path is None:
            data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, 'local_directories.sqlite')

        self.db_path = db_path
        self.engine = create_engine(f'sqlite:///{db_path}', connect_args={'timeout': 30})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        logger.info(f"本地目录配置存储初始化完成: {db_path}")

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
            session = self.Session()
            model = LocalDirectoryModel(
                id=directory.id,
                name=directory.name,
                path=directory.path,
                file_types=json.dumps(directory.file_types),
                exclude_patterns=json.dumps(directory.exclude_patterns),
                enabled=directory.enabled,
                max_depth=directory.max_depth,
                max_file_size_mb=directory.max_file_size_mb
            )
            session.add(model)
            session.commit()
            logger.info(f"添加目录配置: {directory.name} -> {directory.path}")
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"添加目录配置失败: {e}")
            return False
        finally:
            session.close()

    def get_directory(self, dir_id: str) -> Optional[LocalDirectory]:
        """
        获取目录配置

        Args:
            dir_id: 目录 ID

        Returns:
            目录配置，不存在返回 None
        """
        try:
            session = self.Session()
            model = session.query(LocalDirectoryModel).filter_by(id=dir_id).first()
            if model:
                return self._model_to_directory(model)
            return None
        except SQLAlchemyError as e:
            logger.error(f"获取目录配置失败: {e}")
            return None
        finally:
            session.close()

    def list_directories(self, enabled_only: bool = False) -> List[LocalDirectory]:
        """
        列出所有目录配置

        Args:
            enabled_only: 是否只返回启用的目录

        Returns:
            目录配置列表
        """
        try:
            session = self.Session()
            query = session.query(LocalDirectoryModel)
            if enabled_only:
                query = query.filter_by(enabled=True)
            models = query.all()
            return [self._model_to_directory(m) for m in models]
        except SQLAlchemyError as e:
            logger.error(f"列出目录配置失败: {e}")
            return []
        finally:
            session.close()

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
            session = self.Session()
            model = session.query(LocalDirectoryModel).filter_by(id=dir_id).first()
            if not model:
                logger.error(f"目录配置不存在: {dir_id}")
                return False

            for key, value in kwargs.items():
                if key == 'file_types' and isinstance(value, list):
                    model.file_types = json.dumps(value)
                elif key == 'exclude_patterns' and isinstance(value, list):
                    model.exclude_patterns = json.dumps(value)
                elif hasattr(model, key):
                    setattr(model, key, value)

            model.updated_at = datetime.now()
            session.commit()
            logger.info(f"更新目录配置: {dir_id}")
            return True
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"更新目录配置失败: {e}")
            return False
        finally:
            session.close()

    def delete_directory(self, dir_id: str) -> bool:
        """
        删除目录配置

        Args:
            dir_id: 目录 ID

        Returns:
            是否删除成功
        """
        try:
            session = self.Session()
            model = session.query(LocalDirectoryModel).filter_by(id=dir_id).first()
            if model:
                session.delete(model)
                session.commit()
                logger.info(f"删除目录配置: {dir_id}")
                return True
            return False
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"删除目录配置失败: {e}")
            return False
        finally:
            session.close()

    def _model_to_directory(self, model: LocalDirectoryModel) -> LocalDirectory:
        """将数据库模型转换为 LocalDirectory 对象"""
        return LocalDirectory(
            id=model.id,
            name=model.name,
            path=model.path,
            file_types=json.loads(model.file_types),
            exclude_patterns=json.loads(model.exclude_patterns),
            enabled=model.enabled,
            max_depth=model.max_depth,
            max_file_size_mb=model.max_file_size_mb,
            created_at=model.created_at,
            updated_at=model.updated_at
        )

    @staticmethod
    def get_supported_file_types() -> List[str]:
        """获取支持的文件类型列表"""
        return LocalDirectoryStore.DEFAULT_FILE_TYPES.copy()

    @staticmethod
    def get_default_exclude_patterns() -> List[str]:
        """获取默认排除模式列表"""
        return LocalDirectoryStore.DEFAULT_EXCLUDE_PATTERNS.copy()
