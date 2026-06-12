"""
本地文件适配器 - 支持索引本地文件目录
"""

import os
import hashlib
from datetime import datetime
from typing import Dict, List, Optional
import logging
import uuid

from .base_adapter import BaseAdapter
from guiyi_server.storage.local_directory_store import LocalDirectoryStore, LocalDirectory
from guiyi_server.parsers.markdown_parser import MarkdownParser
from guiyi_server.parsers.txt_parser import TxtParser
from guiyi_server.parsers.word_parser import WordParser
from guiyi_server.parsers.excel_parser import ExcelParser
from guiyi_server.parsers.pdf_parser import PDFParser
from guiyi_server.parsers.powerpoint_parser import PowerPointParser
from guiyi_server.parsers.image_parser import ImageParser

logger = logging.getLogger(__name__)


class LocalFileAdapter(BaseAdapter):
    """
    本地文件适配器

    **安全设计：所有操作都是只读的**
    - 文件读取使用 'r' 模式（只读）
    - 不调用任何写入、删除、修改函数
    - 不创建、移动或重命名文件
    """

    # 解析器映射
    PARSERS = {
        # 文本文档
        '.md': MarkdownParser,
        '.markdown': MarkdownParser,
        '.txt': TxtParser,

        # Word
        '.docx': WordParser,
        '.doc': WordParser,

        # Excel
        '.xlsx': ExcelParser,
        '.xls': ExcelParser,

        # PDF
        '.pdf': PDFParser,

        # PowerPoint
        '.pptx': PowerPointParser,
        '.ppt': PowerPointParser,

        # 图片
        '.jpg': ImageParser,
        '.jpeg': ImageParser,
        '.png': ImageParser,
        '.webp': ImageParser,
        '.bmp': ImageParser,
    }

    def __init__(self):
        self.store = LocalDirectoryStore()

    def fetch_all_for_index(self, account: Optional[str] = None) -> List[Dict]:
        """
        扫描所有配置的目录，返回文档列表

        注意：此方法只执行只读操作

        Args:
            account: 可选的目录 ID

        Returns:
            文档列表
        """
        all_docs = []

        if account:
            # 指定单个目录
            directory = self.store.get_directory(account)
            if directory and directory.enabled:
                docs = self._scan_directory(directory)
                all_docs.extend(docs)
        else:
            # 扫描所有启用的目录
            directories = self.store.list_directories(enabled_only=True)
            for directory in directories:
                try:
                    docs = self._scan_directory(directory)
                    all_docs.extend(docs)
                    logger.info(f"目录 [{directory.name}] 扫描完成: {len(docs)} 个文件")
                except Exception as e:
                    logger.error(f"目录 [{directory.name}] 扫描失败: {e}")

        return all_docs

    def _scan_directory(self, directory: LocalDirectory) -> List[Dict]:
        """
        扫描单个目录

        注意：此方法只执行只读操作

        Args:
            directory: 目录配置

        Returns:
            文档列表
        """
        docs = []
        expanded_path = os.path.expanduser(directory.path)

        if not os.path.isdir(expanded_path):
            logger.error(f"目录不存在或不是目录: {directory.path}")
            return docs

        # 构建文件类型集合
        file_types = set()
        for ft in directory.file_types:
            ft = ft.lower()
            if not ft.startswith('.'):
                ft = '.' + ft
            file_types.add(ft)

        # 构建排除模式集合
        exclude_patterns = set(directory.exclude_patterns)

        # 构建排除路径集合（相对路径，归一化）
        exclude_path_set = set()
        for ep in (directory.exclude_paths or []):
            ep = ep.strip('/')
            if ep:
                exclude_path_set.add(ep)

        # 跟踪 git 仓库根目录，用于自动跳过 git 管理的图片
        git_roots = set()
        git_image_skipped = 0

        # 遍历目录（只读）
        for root, dirs, files in self._walk_directory(
            expanded_path,
            exclude_patterns,
            directory.max_depth,
            exclude_path_set
        ):
            # 检测 git 仓库
            if os.path.isdir(os.path.join(root, '.git')):
                git_roots.add(root)

            in_git_repo = any(root == gr or root.startswith(gr + os.sep) for gr in git_roots)

            for filename in files:
                try:
                    file_path = os.path.join(root, filename)
                    file_ext = os.path.splitext(filename)[1].lower()

                    # 检查文件类型
                    if file_types and file_ext not in file_types:
                        continue

                    # 自动跳过 git 仓库内的图片
                    if in_git_repo and file_ext in ImageParser.SUPPORTED_EXTENSIONS:
                        git_image_skipped += 1
                        continue

                    # 跳过压缩文件（单行文件，通常很大）
                    if '.min.' in filename or filename.endswith('.min.js') or filename.endswith('.min.css'):
                        continue
                    if 'bundle' in filename.lower() and file_ext in ['.js', '.css']:
                        continue

                    # 检查文件大小
                    file_size = os.path.getsize(file_path)
                    max_size_bytes = directory.max_file_size_mb * 1024 * 1024
                    if file_size > max_size_bytes:
                        logger.debug(f"文件过大，跳过: {file_path} ({file_size / 1024 / 1024:.2f} MB)")
                        continue

                    # 创建文档记录（不读取内容，内容稍后按需获取）
                    doc = self._create_document_record(
                        file_path=file_path,
                        directory=directory,
                        file_ext=file_ext
                    )
                    if doc:
                        docs.append(doc)

                except Exception as e:
                    logger.warning(f"处理文件失败: {filename} - {e}")
                    continue

        if git_image_skipped > 0:
            logger.info(f"目录 [{directory.name}] 自动跳过 {git_image_skipped} 张 git 仓库内的图片")

        return docs

    def _walk_directory(self, root_path: str, exclude_patterns: set, max_depth: int, exclude_paths: set = None):
        """
        安全遍历目录（只读）

        注意：此方法修改 dirs 列表是为了控制遍历深度和排除目录，
        但不修改文件系统中的任何内容。

        Args:
            root_path: 根目录路径
            exclude_patterns: 按目录名排除的模式
            max_depth: 最大深度
            exclude_paths: 按相对路径排除的子目录集合

        Yields:
            (root, dirs, files) 元组
        """
        exclude_paths = exclude_paths or set()

        for root, dirs, files in os.walk(root_path, followlinks=False):
            # 计算当前深度和相对路径
            rel_path = os.path.relpath(root, root_path)
            current_depth = 0 if rel_path == '.' else rel_path.count(os.sep) + 1

            # 深度限制
            if current_depth > max_depth:
                dirs[:] = []
                continue

            # 检查当前目录本身是否被 exclude_paths 排除
            if rel_path != '.' and rel_path in exclude_paths:
                dirs[:] = []
                continue

            # 过滤排除的目录
            new_dirs = []
            for d in dirs:
                # 按目录名排除
                if d in exclude_patterns or d.startswith('.'):
                    continue

                # 按 exclude_paths 排除特定子目录
                if exclude_paths:
                    child_rel = os.path.join(rel_path, d) if rel_path != '.' else d
                    if child_rel in exclude_paths:
                        continue

                new_dirs.append(d)

            dirs[:] = new_dirs

            yield root, dirs, files

    def _create_document_record(
        self,
        file_path: str,
        directory: LocalDirectory,
        file_ext: str
    ) -> Optional[Dict]:
        """
        创建文档记录（不读取文件内容）

        注意：此方法只执行只读操作

        Args:
            file_path: 文件路径
            directory: 目录配置
            file_ext: 文件扩展名

        Returns:
            文档记录字典
        """
        try:
            # 获取文件信息（只读操作）
            stat_info = os.stat(file_path)

            # 生成文档 ID
            doc_id = f"local_{directory.id}_{hashlib.md5(file_path.encode()).hexdigest()[:12]}"

            # 获取相对路径用于标题
            expanded_path = os.path.expanduser(directory.path)
            rel_path = os.path.relpath(file_path, expanded_path)

            return {
                "id": doc_id,
                "title": os.path.basename(file_path),
                "content": "",  # 内容稍后按需获取
                "url": f"file://{file_path}",
                "source": "local",
                "account": directory.id,
                "doc_type": "file",
                "obj_type": file_ext[1:] if file_ext else "unknown",
                "file_path": file_path,
                "directory_name": directory.name,
                "relative_path": rel_path,
                "updated_at": stat_info.st_mtime,
                "store_locally": False  # 本地文件不需要额外存储
            }

        except Exception as e:
            logger.error(f"创建文档记录失败: {file_path} - {e}")
            return None

    def get_document_content(self, doc_id: str, file_path: str = None, **kwargs) -> Optional[str]:
        """
        获取文档内容

        注意：此方法只执行只读操作

        Args:
            doc_id: 文档 ID
            file_path: 文件路径（必须提供）
            **kwargs: 额外参数

        Returns:
            文档内容字符串
        """
        if not file_path:
            logger.error(f"缺少 file_path 参数: {doc_id}")
            return None

        # 安全检查：确保文件路径存在且可读
        if not os.path.isfile(file_path):
            logger.error(f"文件不存在: {file_path}")
            return None

        if not os.access(file_path, os.R_OK):
            logger.error(f"文件不可读: {file_path}")
            return None

        # 根据文件扩展名选择解析器
        file_ext = os.path.splitext(file_path)[1].lower()

        # 选择解析器
        parser = None
        if file_ext in self.PARSERS:
            parser = self.PARSERS[file_ext]
        else:
            # 默认尝试以文本方式读取
            parser = TxtParser

        # 解析文件（只读）
        content = parser.parse(file_path)

        return content

    def get_document_content_with_metadata(self, doc_id: str, file_path: str = None, **kwargs) -> Dict:
        """
        获取文档内容和元数据

        对于图片文件，返回 ai_summary 和 ai_tags

        Args:
            doc_id: 文档 ID
            file_path: 文件路径（必须提供）
            **kwargs: 额外参数

        Returns:
            包含 content 和可能的 ai_summary、ai_tags 的字典
        """
        result = {
            "content": None,
            "ai_summary": None,
            "ai_tags": None
        }

        if not file_path:
            logger.error(f"缺少 file_path 参数: {doc_id}")
            return result

        # 安全检查
        if not os.path.isfile(file_path):
            logger.error(f"文件不存在: {file_path}")
            return result

        if not os.access(file_path, os.R_OK):
            logger.error(f"文件不可读: {file_path}")
            return result

        # 根据文件扩展名选择解析器
        file_ext = os.path.splitext(file_path)[1].lower()

        # 检查是否是图片文件
        if file_ext in ImageParser.SUPPORTED_EXTENSIONS:
            # 图片文件：使用 ImageParser 获取内容和元数据
            content = ImageParser.parse(file_path)
            caption_data = ImageParser.get_caption_data(file_path)

            result["content"] = content
            if caption_data:
                result["ai_summary"] = caption_data.get("description")
                result["ai_tags"] = caption_data.get("tags")
        else:
            # 其他文件类型
            parser = self.PARSERS.get(file_ext, TxtParser)
            result["content"] = parser.parse(file_path)

        return result

    @staticmethod
    def is_image_file(file_path: str) -> bool:
        """检查是否是图片文件"""
        file_ext = os.path.splitext(file_path)[1].lower()
        return file_ext in ImageParser.SUPPORTED_EXTENSIONS

    def supports_write(self) -> bool:
        """
        本地文件适配器不支持写入操作

        Returns:
            始终返回 False
        """
        return False

    def count_files(self, directory_id: str) -> int:
        """
        统计目录中的文件数量

        注意：此方法只执行只读操作

        Args:
            directory_id: 目录 ID

        Returns:
            文件数量
        """
        directory = self.store.get_directory(directory_id)
        if not directory or not directory.enabled:
            return 0

        docs = self._scan_directory(directory)
        return len(docs)
