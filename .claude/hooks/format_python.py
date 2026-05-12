#!/usr/bin/env python3
"""
Hook: 格式化 Python 代码
在保存 Python 文件后自动运行 black 和 isort
"""
import sys
import subprocess
from pathlib import Path

def main(file_path):
    """格式化指定的 Python 文件"""
    if not file_path.endswith('.py'):
        return

    try:
        # 运行 black 格式化
        subprocess.run(['black', file_path], check=True, capture_output=True)
        # 运行 isort 整理导入
        subprocess.run(['isort', file_path], check=True, capture_output=True)
        print(f"✓ Formatted: {file_path}")
    except subprocess.CalledProcessError as e:
        print(f"✗ Format failed: {file_path}")
        print(e.stderr.decode())
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python format_python.py <file_path>")
        sys.exit(1)

    main(sys.argv[1])
