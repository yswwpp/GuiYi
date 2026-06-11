"""
测试语义索引功能
"""

import pytest
from guiyi_server.index.txtai_index import IndexManager
import tempfile
import os
import shutil


class TestIndexManager:
    """索引管理器测试类"""

    def setup_method(self):
        """每个测试方法前执行"""
        self.temp_dir = tempfile.mkdtemp()
        self.index_path = os.path.join(self.temp_dir, "index")
        self.index = IndexManager(index_path=self.index_path)

    def teardown_method(self):
        """每个测试方法后执行"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_init(self):
        """测试初始化"""
        assert self.index.index_path is not None
        assert os.path.exists(self.index.index_path)
        assert self.index.embeddings is not None

    def test_index_document(self):
        """测试索引单个文档"""
        doc = {
            "id": "test_001",
            "title": "测试文档",
            "content": "这是一个测试文档的内容。",
            "url": "https://example.com/test",
            "source": "web",
            "saved_at": "2024-01-01T12:00:00"
        }

        self.index.index_document(doc)

        assert self.index.embeddings.count() == 1
        assert "test_001" in self.index.metadata

    def test_index_documents_batch(self):
        """测试批量索引文档"""
        docs = [
            {
                "id": "batch_001",
                "title": "批量文档 1",
                "content": "第一个批量文档内容",
                "url": "https://example.com/batch1",
                "source": "web"
            },
            {
                "id": "batch_002",
                "title": "批量文档 2",
                "content": "第二个批量文档内容",
                "url": "https://example.com/batch2",
                "source": "web"
            },
            {
                "id": "batch_003",
                "title": "批量文档 3",
                "content": "第三个批量文档内容",
                "url": "https://example.com/batch3",
                "source": "web"
            }
        ]

        self.index.index_documents(docs)

        assert self.index.embeddings.count() == 3
        for doc in docs:
            assert doc["id"] in self.index.metadata

    def test_search_basic(self):
        """测试基本搜索功能"""
        docs = [
            {
                "id": "search_001",
                "title": "Python 编程教程",
                "content": "学习 Python 编程的基础知识和进阶技巧。",
                "url": "https://example.com/python",
                "source": "web"
            },
            {
                "id": "search_002",
                "title": "Java 开发指南",
                "content": "Java 开发的最佳实践和设计模式。",
                "url": "https://example.com/java",
                "source": "web"
            }
        ]

        self.index.index_documents(docs)

        results = self.index.search("Python 编程", limit=5)

        assert len(results) > 0
        # Python 相关文档应该排在前面
        assert results[0]["id"] == "search_001"

    def test_search_with_filter(self):
        """测试带过滤条件的搜索"""
        docs = [
            {
                "id": "filter_001",
                "title": "飞书文档",
                "content": "这是飞书文档的内容",
                "url": "https://feishu.cn/doc1",
                "source": "feishu",
                "account": "work"
            },
            {
                "id": "filter_002",
                "title": "网页文档",
                "content": "这是网页文档的内容",
                "url": "https://example.com/doc2",
                "source": "web"
            }
        ]

        self.index.index_documents(docs)

        # 按来源过滤
        results = self.index.search("文档", source="feishu", limit=5)

        assert len(results) > 0
        for result in results:
            assert result["source"] == "feishu"

    def test_search_with_account_filter(self):
        """测试按账号过滤搜索"""
        docs = [
            {
                "id": "account_001",
                "title": "工作账号文档",
                "content": "工作相关内容",
                "url": "https://example.com/work",
                "source": "feishu",
                "account": "work"
            },
            {
                "id": "account_002",
                "title": "个人账号文档",
                "content": "个人相关内容",
                "url": "https://example.com/personal",
                "source": "feishu",
                "account": "personal"
            }
        ]

        self.index.index_documents(docs)

        results = self.index.search("内容", account="work", limit=5)

        assert len(results) > 0
        for result in results:
            assert result["account"] == "work"

    def test_search_limit(self):
        """测试搜索结果限制"""
        docs = [
            {
                "id": f"limit_{i:03d}",
                "title": f"文档 {i}",
                "content": f"这是第 {i} 个文档的内容",
                "url": f"https://example.com/doc{i}",
                "source": "web"
            }
            for i in range(20)
        ]

        self.index.index_documents(docs)

        results = self.index.search("文档", limit=5)

        assert len(results) == 5

    def test_delete_document(self):
        """测试删除文档"""
        doc = {
            "id": "delete_001",
            "title": "将被删除的文档",
            "content": "这个文档将被删除",
            "url": "https://example.com/delete",
            "source": "web"
        }

        self.index.index_document(doc)
        assert self.index.embeddings.count() == 1

        self.index.delete_document("delete_001")

        # 注意：txtai 删除后 count 可能不会立即减少，取决于实现
        # 但元数据应该被删除
        assert "delete_001" not in self.index.metadata

    def test_get_stats(self):
        """测试获取统计信息"""
        docs = [
            {
                "id": f"stats_{i:03d}",
                "title": f"统计文档 {i}",
                "content": f"内容 {i}",
                "url": f"https://example.com/stats{i}",
                "source": "web"
            }
            for i in range(5)
        ]

        self.index.index_documents(docs)
        stats = self.index.get_stats()

        assert stats is not None
        assert "total_documents" in stats
        assert "index_path" in stats
        assert "model" in stats
        assert stats["total_documents"] == 5

    def test_persistence(self):
        """测试索引持久化"""
        # 创建第一个索引管理器并添加文档
        index1 = IndexManager(index_path=self.index_path)
        doc = {
            "id": "persist_001",
            "title": "持久化测试",
            "content": "测试索引是否能正确保存和加载",
            "url": "https://example.com/persist",
            "source": "web"
        }
        index1.index_document(doc)

        # 创建第二个索引管理器（从磁盘加载）
        index2 = IndexManager(index_path=self.index_path)
        index2.load_index()

        # 验证数据是否持久化
        assert "persist_001" in index2.metadata

    def test_update_document(self):
        """测试更新文档（使用 upsert）"""
        doc_v1 = {
            "id": "update_001",
            "title": "原始标题",
            "content": "原始内容",
            "url": "https://example.com/update",
            "source": "web"
        }

        self.index.index_document(doc_v1)

        # 更新文档
        doc_v2 = {
            "id": "update_001",
            "title": "更新后的标题",
            "content": "更新后的内容",
            "url": "https://example.com/update",
            "source": "web"
        }

        self.index.index_document(doc_v2)

        # 验证更新
        assert self.index.metadata["update_001"]["title"] == "更新后的标题"

    def test_chinese_content(self):
        """测试中文内容索引"""
        docs = [
            {
                "id": "chinese_001",
                "title": "中文标题测试",
                "content": "这是一段中文内容，用于测试语义搜索功能。包含关键词：机器学习、深度学习、自然语言处理。",
                "url": "https://example.com/chinese",
                "source": "web"
            }
        ]

        self.index.index_documents(docs)

        results = self.index.search("机器学习", limit=5)

        assert len(results) > 0


class TestIndexManagerEdgeCases:
    """边缘情况测试"""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.index_path = os.path.join(self.temp_dir, "index")
        self.index = IndexManager(index_path=self.index_path)

    def teardown_method(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_search_empty_index(self):
        """测试在空索引中搜索"""
        results = self.index.search("测试查询", limit=5)

        assert results is not None
        assert len(results) == 0

    def test_index_empty_content(self):
        """测试索引空内容文档"""
        doc = {
            "id": "empty_001",
            "title": "空内容文档",
            "content": "",
            "url": "https://example.com/empty",
            "source": "web"
        }

        # 应该不会抛出异常
        self.index.index_document(doc)

        assert "empty_001" in self.index.metadata

    def test_index_special_characters(self):
        """测试包含特殊字符的内容"""
        doc = {
            "id": "special_001",
            "title": "特殊字符 <>&\"'",
            "content": "内容包含特殊字符: <>&\"'以及\n换行\t制表符",
            "url": "https://example.com/special",
            "source": "web"
        }

        self.index.index_document(doc)

        assert "special_001" in self.index.metadata
        assert "<>&\"'" in self.index.metadata["special_001"]["title"]

    def test_long_content(self):
        """测试长内容索引"""
        long_content = "这是一段很长的内容。" * 10000

        doc = {
            "id": "long_001",
            "title": "长内容文档",
            "content": long_content,
            "url": "https://example.com/long",
            "source": "web"
        }

        self.index.index_document(doc)

        assert "long_001" in self.index.metadata


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
