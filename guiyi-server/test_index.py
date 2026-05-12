"""
测试语义索引功能
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from index.txtai_index import IndexManager

print("=" * 60)
print("语义索引功能测试")
print("=" * 60)

try:
    print("\n1. 初始化索引管理器...")
    print("   注意：首次运行需要下载向量模型（约 1-2GB），请耐心等待")
    index = IndexManager()
    print("   ✓ 索引管理器初始化成功")

    print("\n2. 测试索引文档...")
    test_doc = {
        "id": "test_001",
        "title": "GuiYi 测试文档",
        "content": "这是一个测试文档，用于验证语义索引功能是否正常工作。GuiYi 是一个本地优先的知识管理系统。",
        "url": "http://localhost:8888/test.html",
        "source": "web",
        "saved_at": "2026-04-04T23:00:00"
    }

    index.index_document(test_doc)
    print("   ✓ 文档索引成功")

    print("\n3. 测试搜索功能...")
    results = index.search("知识管理", limit=5)
    print(f"   ✓ 搜索完成，找到 {len(results)} 个结果")

    if results:
        print("\n   搜索结果:")
        for i, result in enumerate(results, 1):
            print(f"   {i}. {result['title']}")
            print(f"      相关度: {result['score']:.4f}")
            print(f"      摘要: {result['text'][:100]}...")

    print("\n4. 查看索引统计...")
    stats = index.get_stats()
    print(f"   文档总数: {stats['total_documents']}")
    print(f"   模型: {stats['model']}")

    print("\n" + "=" * 60)
    print("✓ 所有测试通过！语义索引功能正常")
    print("=" * 60)

except Exception as e:
    print(f"\n✗ 测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
