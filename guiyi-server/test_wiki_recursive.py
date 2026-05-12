#!/usr/bin/env python3
"""测试递归获取知识库文档"""

import requests
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

USER_ACCESS_TOKEN = "u-4_Td8dAD52TrfKD4SutLG7h024r5h5UhpO0a7Bu82DOs"

def fetch_wiki_docs_recursive():
    """递归获取知识库文档"""
    headers = {
        "Authorization": f"Bearer {USER_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    all_docs = []

    # 1. 获取知识库列表
    spaces_url = "https://open.feishu.cn/open-apis/wiki/v2/spaces?page_size=50"
    response = requests.get(spaces_url, headers=headers)
    data = response.json()

    if data.get('code') != 0:
        logger.error(f"获取知识库列表失败: {data.get('msg')}")
        return

    spaces = data.get('data', {}).get('items', [])
    logger.info(f"找到 {len(spaces)} 个知识库\n")

    # 2. 递归获取文档
    def fetch_nodes(space_id, space_name, parent_node_token=None, depth=0):
        indent = "  " * depth

        if parent_node_token:
            url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/{space_id}/nodes?page_size=50&parent_node_token={parent_node_token}"
        else:
            url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/{space_id}/nodes?page_size=50"

        response = requests.get(url, headers=headers)
        data = response.json()

        if data.get('code') != 0:
            return

        items = data.get('data', {}).get('items', [])

        for item in items:
            node_token = item.get('node_token')
            obj_token = item.get('obj_token')
            title = item.get('title', 'unnamed')
            obj_type = item.get('obj_type', '')
            has_child = item.get('has_child', False)

            if obj_type in ['docx', 'doc', 'sheet', 'bitable', 'mindnote']:
                all_docs.append({
                    'title': title,
                    'obj_type': obj_type,
                    'has_child': has_child,
                    'space_name': space_name,
                    'node_token': node_token,
                    'obj_token': obj_token
                })

                if has_child:
                    logger.info(f"{indent}📁 {title} ({obj_type})")
                    fetch_nodes(space_id, space_name, node_token, depth + 1)
                else:
                    logger.info(f"{indent}  📄 {title} ({obj_type})")

    for space in spaces:
        space_id = space.get('space_id')
        space_name = space.get('name', 'unnamed')
        logger.info(f"=== 知识库: {space_name} ===")
        fetch_nodes(space_id, space_name)

    logger.info(f"\n总计: {len(all_docs)} 个文档")
    return all_docs

if __name__ == "__main__":
    docs = fetch_wiki_docs_recursive()
