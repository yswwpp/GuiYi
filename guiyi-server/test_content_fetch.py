#!/usr/bin/env python3
"""测试同步飞书知识库文档"""

import requests
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

USER_ACCESS_TOKEN = "u-4_Td8dAD52TrfKD4SutLG7h024r5h5UhpO0a7Bu82DOs"

def get_docx_content(doc_token: str, headers: dict) -> str:
    """获取docx文档内容"""
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{doc_token}/children"
    response = requests.get(url, headers=headers)
    data = response.json()

    if data.get('code') == 0:
        items = data.get('data', {}).get('items', [])
        all_text = []

        for item in items:
            if 'text' in item and 'elements' in item['text']:
                for elem in item['text']['elements']:
                    if 'text_run' in elem and 'content' in elem['text_run']:
                        all_text.append(elem['text_run']['content'])

        return "\n".join(all_text)[:500]

    return f"错误: {data.get('msg')}"

def get_sheet_content(doc_token: str, headers: dict) -> str:
    """获取电子表格内容"""
    sheets_url = f"https://open.feishu.cn/open-apis/sheets/v3/spreadsheets/{doc_token}/sheets/query"
    response = requests.get(sheets_url, headers=headers)
    data = response.json()

    if data.get('code') == 0:
        sheets = data.get('data', {}).get('sheets', [])
        if sheets:
            return f"电子表格，共 {len(sheets)} 个工作表"

    return f"错误: {data.get('msg')}"

def test_content_fetch():
    """测试获取不同类型文档的内容"""
    headers = {
        "Authorization": f"Bearer {USER_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    # 测试几个不同类型的文档
    test_docs = [
        # docx 类型
        ("FVDIdHCRoasAYkxPYGcLJdLYnhc", "docx", "首页"),
        # sheet 类型
        ("FVDIdHCRoasAYkxPYGcLJdLYnhc", "sheet", "账号密码"),
    ]

    # 从知识库获取一些真实文档
    spaces_url = "https://open.feishu.cn/open-apis/wiki/v2/spaces?page_size=1"
    response = requests.get(spaces_url, headers=headers)
    data = response.json()

    if data.get('code') == 0:
        spaces = data.get('data', {}).get('items', [])
        if spaces:
            space_id = spaces[0].get('space_id')
            nodes_url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/{space_id}/nodes?page_size=10"
            response = requests.get(nodes_url, headers=headers)
            data = response.json()

            if data.get('code') == 0:
                items = data.get('data', {}).get('items', [])
                logger.info(f"\n=== 测试获取文档内容 ===\n")

                for item in items[:5]:
                    obj_token = item.get('obj_token')
                    title = item.get('title')
                    obj_type = item.get('obj_type')

                    logger.info(f"📄 {title} ({obj_type})")

                    if obj_type == "docx":
                        content = get_docx_content(obj_token, headers)
                        logger.info(f"   内容: {content[:200]}...")
                    elif obj_type == "sheet":
                        content = get_sheet_content(obj_token, headers)
                        logger.info(f"   内容: {content}")
                    else:
                        logger.info(f"   类型: {obj_type}")

                    logger.info("")

if __name__ == "__main__":
    test_content_fetch()
