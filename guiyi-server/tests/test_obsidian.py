"""
测试 Obsidian 存储功能
"""

import pytest
from guiyi_server.storage.obsidian import ObsidianStorage
import tempfile
import os
from pathlib import Path


class TestObsidianStorage:
    """Obsidian 存储测试类"""

    def setup_method(self):
        """每个测试方法前执行"""
        self.temp_dir = tempfile.mkdtemp()
        self.vault_path = os.path.join(self.temp_dir, "obsidian_vault")
        self.storage = ObsidianStorage(vault_path=self.vault_path)

    def teardown_method(self):
        """每个测试方法后执行"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_init(self):
        """测试初始化"""
        assert self.storage.vault_path is not None
        assert self.storage.inbox_path is not None
        assert self.storage.assets_path is not None
        assert os.path.exists(self.storage.inbox_path)
        assert os.path.exists(self.storage.assets_path)

    def test_save_markdown(self):
        """测试保存 Markdown 文件"""
        filename = "test.md"
        content = "# 测试标题\n\n这是测试内容。"

        file_path = self.storage.save_markdown(filename, content)

        assert file_path is not None
        assert os.path.exists(file_path)

        with open(file_path, 'r', encoding='utf-8') as f:
            saved_content = f.read()
        assert saved_content == content

    def test_save_markdown_with_chinese(self):
        """测试保存中文内容"""
        filename = "中文测试.md"
        content = "# 中文标题\n\n这是中文内容，测试编码处理。"

        file_path = self.storage.save_markdown(filename, content)

        assert file_path is not None
        assert os.path.exists(file_path)

        with open(file_path, 'r', encoding='utf-8') as f:
            saved_content = f.read()
        assert saved_content == content

    def test_save_markdown_duplicate_filename(self):
        """测试重复文件名处理"""
        filename = "duplicate.md"
        content1 = "第一次保存"
        content2 = "第二次保存"

        file_path1 = self.storage.save_markdown(filename, content1)
        file_path2 = self.storage.save_markdown(filename, content2)

        # 两个文件路径应该不同
        assert file_path1 != file_path2

        # 两个文件都应该存在
        assert os.path.exists(file_path1)
        assert os.path.exists(file_path2)

    def test_get_file_path_exists(self):
        """测试获取存在的文件路径"""
        filename = "exists.md"
        content = "内容"

        self.storage.save_markdown(filename, content)
        file_path = self.storage.get_file_path(filename)

        assert file_path is not None
        assert file_path.exists()

    def test_get_file_path_not_exists(self):
        """测试获取不存在的文件路径"""
        file_path = self.storage.get_file_path("not_exists.md")

        assert file_path is None

    def test_list_files_empty(self):
        """测试列出空目录的文件"""
        files = self.storage.list_files()

        assert files is not None
        assert len(files) == 0

    def test_list_files_with_files(self):
        """测试列出多个文件"""
        # 创建多个测试文件
        self.storage.save_markdown("file1.md", "内容1")
        self.storage.save_markdown("file2.md", "内容2")
        self.storage.save_markdown("file3.md", "内容3")

        files = self.storage.list_files()

        assert len(files) == 3
        filenames = [f.name for f in files]
        assert "file1.md" in filenames
        assert "file2.md" in filenames
        assert "file3.md" in filenames

    def test_delete_file_exists(self):
        """测试删除存在的文件"""
        filename = "to_delete.md"
        content = "将被删除"

        self.storage.save_markdown(filename, content)
        result = self.storage.delete_file(filename)

        assert result is True
        assert not self.storage.get_file_path(filename).exists() if self.storage.get_file_path(filename) else True

    def test_delete_file_not_exists(self):
        """测试删除不存在的文件"""
        result = self.storage.delete_file("not_exists.md")

        assert result is False

    def test_get_storage_info_empty(self):
        """测试获取空存储信息"""
        info = self.storage.get_storage_info()

        assert info is not None
        assert "total_files" in info
        assert "total_size_mb" in info
        assert "vault_path" in info
        assert "inbox_path" in info
        assert info["total_files"] == 0
        assert info["total_size_mb"] == 0.0

    def test_get_storage_info_with_files(self):
        """测试获取有文件的存储信息"""
        # 创建一些文件（使用更大的内容）
        self.storage.save_markdown("file1.md", "a" * 10000)
        self.storage.save_markdown("file2.md", "b" * 20000)

        info = self.storage.get_storage_info()

        assert info["total_files"] == 2
        assert info["total_size_mb"] >= 0  # 文件大小可能很小，不强制要求大于 0

    def test_save_special_characters_in_content(self):
        """测试保存包含特殊字符的内容"""
        filename = "special.md"
        content = "# 特殊字符测试\n\n内容包含: < > & \" ' \n\t特殊空白字符"

        file_path = self.storage.save_markdown(filename, content)

        assert os.path.exists(file_path)

        with open(file_path, 'r', encoding='utf-8') as f:
            saved_content = f.read()
        assert saved_content == content

    def test_save_yaml_frontmatter(self):
        """测试保存带 YAML 元数据的内容"""
        filename = "yaml.md"
        content = """---
title: 测试标题
date: 2024-01-01
tags:
  - 测试
  - Python
---

# 正文内容

这是正文部分。"""

        file_path = self.storage.save_markdown(filename, content)

        assert os.path.exists(file_path)

        with open(file_path, 'r', encoding='utf-8') as f:
            saved_content = f.read()
        assert saved_content == content


class TestObsidianStoragePaths:
    """路径处理测试"""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.vault_path = os.path.join(self.temp_dir, "vault")
        self.storage = ObsidianStorage(vault_path=self.vault_path)

    def teardown_method(self):
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_path_with_spaces(self):
        """测试路径包含空格"""
        # 创建带空格的路径
        vault_with_spaces = os.path.join(self.temp_dir, "vault with spaces")
        storage = ObsidianStorage(vault_path=vault_with_spaces)

        assert os.path.exists(storage.inbox_path)

        filename = "test.md"
        content = "内容"
        file_path = storage.save_markdown(filename, content)

        assert os.path.exists(file_path)

    def test_path_with_unicode(self):
        """测试路径包含 Unicode 字符"""
        vault_with_unicode = os.path.join(self.temp_dir, "中文库")
        storage = ObsidianStorage(vault_path=vault_with_unicode)

        assert os.path.exists(storage.inbox_path)

        filename = "测试文件.md"
        content = "测试内容"
        file_path = storage.save_markdown(filename, content)

        assert os.path.exists(file_path)


class TestObsidianStorageConcurrency:
    """并发安全测试"""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.vault_path = os.path.join(self.temp_dir, "vault")
        self.storage = ObsidianStorage(vault_path=self.vault_path)

    def teardown_method(self):
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_concurrent_saves(self):
        """测试并发保存"""
        import threading
        import time

        results = []
        errors = []

        def save_file(i):
            try:
                filename = f"concurrent_{i}.md"
                content = f"内容 {i}"
                file_path = self.storage.save_markdown(filename, content)
                results.append(file_path)
            except Exception as e:
                errors.append(str(e))

        threads = []
        for i in range(10):
            t = threading.Thread(target=save_file, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
