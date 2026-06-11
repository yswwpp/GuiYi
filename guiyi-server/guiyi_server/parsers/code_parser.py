"""
代码文件解析器 - 支持多种编程语言
"""

import os
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class CodeParser:
    """代码文件解析器"""

    # 支持的代码文件扩展名及其语言标识
    SUPPORTED_EXTENSIONS = {
        # Python
        '.py': 'python',
        '.pyw': 'python',

        # JavaScript / TypeScript
        '.js': 'javascript',
        '.mjs': 'javascript',
        '.cjs': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.jsx': 'javascript',

        # Java
        '.java': 'java',

        # Go
        '.go': 'go',

        # Rust
        '.rs': 'rust',

        # C / C++
        '.c': 'c',
        '.h': 'c',
        '.cpp': 'cpp',
        '.hpp': 'cpp',
        '.cc': 'cpp',

        # Ruby
        '.rb': 'ruby',
        '.rake': 'ruby',

        # PHP
        '.php': 'php',

        # Swift
        '.swift': 'swift',

        # Kotlin
        '.kt': 'kotlin',
        '.kts': 'kotlin',

        # Scala
        '.scala': 'scala',
        '.sc': 'scala',

        # Shell
        '.sh': 'shell',
        '.bash': 'shell',
        '.zsh': 'shell',

        # Config / Data
        '.json': 'json',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.xml': 'xml',
        '.toml': 'toml',
        '.ini': 'ini',

        # Markup
        '.html': 'html',
        '.htm': 'html',
        '.css': 'css',
        '.scss': 'scss',
        '.less': 'less',

        # SQL
        '.sql': 'sql',

        # Other
        '.lua': 'lua',
        '.r': 'r',
        '.vim': 'vim',
        '.dockerfile': 'dockerfile',
    }

    @staticmethod
    def parse(file_path: str, max_length: int = 50000) -> Optional[str]:
        """
        解析代码文件

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
            # 代码文件通常都是 UTF-8，如果不是则可能不是源代码
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    content = f.read(max_length)
                return content
            except Exception as e:
                logger.warning(f"无法解析代码文件 (编码问题): {file_path} - {e}")
                return None
        except Exception as e:
            logger.error(f"解析代码文件失败: {file_path} - {e}")
            return None

    @staticmethod
    def get_language(file_path: str) -> Optional[str]:
        """
        获取文件对应的编程语言

        Args:
            file_path: 文件路径

        Returns:
            语言标识
        """
        ext = os.path.splitext(file_path)[1].lower()
        return CodeParser.SUPPORTED_EXTENSIONS.get(ext)

    @staticmethod
    def is_code_file(file_path: str) -> bool:
        """
        判断是否为支持的代码文件

        Args:
            file_path: 文件路径

        Returns:
            是否为代码文件
        """
        ext = os.path.splitext(file_path)[1].lower()
        return ext in CodeParser.SUPPORTED_EXTENSIONS
