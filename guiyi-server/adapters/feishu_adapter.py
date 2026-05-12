"""
飞书多账号适配器 - 支持应用身份和用户身份访问
"""

import hashlib
from datetime import datetime
from typing import Dict, List, Optional
import logging
import requests

logger = logging.getLogger(__name__)


class FeishuAccount:
    """飞书账号配置"""

    def __init__(self, name: str, app_id: str, app_secret: str, user_access_token: str = None, refresh_token: str = None):
        """
        Args:
            name: 账号名称（如 "company" 或 "personal"）
            app_id: 飞书应用 ID
            app_secret: 飞书应用密钥
            user_access_token: 用户访问令牌（可选，用于用户身份访问）
            refresh_token: 刷新令牌（可选，用于刷新 user_access_token）
        """
        self.name = name
        self.app_id = app_id
        self.app_secret = app_secret
        self.user_access_token = user_access_token
        self.refresh_token = refresh_token
        self.client = None  # 延迟初始化

    def init_client(self):
        """初始化飞书客户端"""
        try:
            from lark_oapi import Client

            self.client = Client.builder() \
                .app_id(self.app_id) \
                .app_secret(self.app_secret) \
                .build()
            logger.info(f"飞书客户端初始化成功: {self.name}")
            return True
        except Exception as e:
            logger.error(f"飞书客户端初始化失败 [{self.name}]: {e}")
            import traceback
            traceback.print_exc()
            return False

    def set_user_access_token(self, token: str, refresh_token: str = None):
        """设置用户访问令牌"""
        self.user_access_token = token
        if refresh_token:
            self.refresh_token = refresh_token
        logger.info(f"已设置用户访问令牌: {self.name}")

    def refresh_user_token(self) -> bool:
        """
        刷新用户访问令牌

        Returns:
            是否刷新成功
        """
        if not self.refresh_token:
            logger.warning(f"没有 refresh_token，无法刷新用户令牌: {self.name}")
            return False

        try:
            import requests

            # 飞书刷新令牌需要使用 app_id 和 app_secret 进行认证
            url = "https://open.feishu.cn/open-apis/authen/v1/refresh_access_token"
            headers = {"Content-Type": "application/json"}
            data = {
                "app_id": self.app_id,
                "app_secret": self.app_secret,
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token
            }

            response = requests.post(url, json=data, headers=headers)
            result = response.json()

            if result.get('code') == 0:
                data = result.get('data', {})
                self.user_access_token = data.get('access_token')
                self.refresh_token = data.get('refresh_token')
                logger.info(f"用户令牌刷新成功: {self.name}")
                return True
            else:
                logger.error(f"用户令牌刷新失败 [{self.name}]: code={result.get('code')}, msg={result.get('msg')}")
                return False

        except Exception as e:
            logger.error(f"刷新用户令牌异常 [{self.name}]: {e}")
            return False


class FeishuAdapter:
    """飞书多账号适配器"""

    def __init__(self):
        self.accounts: Dict[str, FeishuAccount] = {}

    def add_account(self, account: FeishuAccount) -> bool:
        """
        添加飞书账号

        Args:
            account: 飞书账号配置

        Returns:
            是否添加成功
        """
        if account.init_client():
            self.accounts[account.name] = account
            logger.info(f"添加飞书账号: {account.name}")
            return True
        return False

    def fetch_all_for_index(self, account_name: Optional[str] = None) -> List[Dict]:
        """
        从所有账号获取文档用于索引

        Args:
            account_name: 指定账号名称（可选），不指定则获取所有账号

        Returns:
            文档列表
        """
        all_docs = []

        accounts_to_fetch = (
            {account_name: self.accounts[account_name]}
            if account_name and account_name in self.accounts
            else self.accounts
        )

        for acc_name, account in accounts_to_fetch.items():
            try:
                # 优先使用用户身份获取文档
                if account.user_access_token:
                    docs = self._fetch_with_user_token(account)
                else:
                    docs = self._fetch_from_account(account)
                all_docs.extend(docs)
                logger.info(f"从飞书账号 [{acc_name}] 获取 {len(docs)} 个文档")
            except Exception as e:
                logger.error(f"从飞书账号 [{acc_name}] 获取文档失败: {e}")

        return all_docs

    def _fetch_with_user_token(self, account: FeishuAccount) -> List[Dict]:
        """
        使用用户身份获取文档（包括知识库）

        Args:
            account: 飞书账号实例

        Returns:
            文档列表
        """
        docs = []
        headers = {
            "Authorization": f"Bearer {account.user_access_token}",
            "Content-Type": "application/json"
        }

        # 1. 获取云空间文件
        try:
            drive_docs = self._fetch_drive_files(headers, account.name)
            docs.extend(drive_docs)
            logger.info(f"云空间文件: {len(drive_docs)} 个")
        except Exception as e:
            logger.error(f"获取云空间文件失败: {e}")

        # 2. 获取知识库文档
        try:
            wiki_docs = self._fetch_wiki_docs(headers, account.name)
            docs.extend(wiki_docs)
            logger.info(f"知识库文档: {len(wiki_docs)} 个")
        except Exception as e:
            logger.error(f"获取知识库文档失败: {e}")

        return docs

    def _fetch_drive_files(self, headers: dict, account_name: str) -> List[Dict]:
        """获取云空间文件"""
        docs = []
        url = "https://open.feishu.cn/open-apis/drive/v1/files?page_size=50"

        response = requests.get(url, headers=headers)
        data = response.json()

        if data.get('code') == 0:
            files = data.get('data', {}).get('files', [])
            for file in files:
                file_type = file.get('type', '')
                if file_type in ['docx', 'doc', 'sheet', 'bitable', 'mindnote']:
                    docs.append({
                        "id": f"feishu_{account_name}_drive_{file.get('token')}",
                        "title": file.get('name', 'unnamed'),
                        "content": "",  # 内容稍后获取
                        "url": f"https://feishu.cn/docx/{file.get('token')}",
                        "source": "feishu",
                        "account": f"feishu_{account_name}",
                        "doc_type": "drive",
                        "doc_token": file.get('token'),
                        "updated_at": datetime.now().timestamp(),
                        "store_locally": False
                    })

        return docs

    def _fetch_wiki_docs(self, headers: dict, account_name: str) -> List[Dict]:
        """获取知识库文档（支持递归获取子节点）"""
        docs = []

        # 1. 获取知识库列表
        spaces_url = "https://open.feishu.cn/open-apis/wiki/v2/spaces?page_size=50"
        response = requests.get(spaces_url, headers=headers)
        data = response.json()

        if data.get('code') != 0:
            logger.error(f"获取知识库列表失败: {data.get('msg')}")
            return docs

        spaces = data.get('data', {}).get('items', [])
        logger.info(f"找到 {len(spaces)} 个知识库")

        # 2. 遍历每个知识库获取文档
        for space in spaces:
            space_id = space.get('space_id')
            space_name = space.get('name', 'unnamed')
            logger.info(f"正在扫描知识库: {space_name}")

            # 递归获取所有节点
            self._fetch_wiki_nodes_recursive(
                space_id, None, headers, account_name, space_name, docs, depth=0
            )

        return docs

    def _fetch_wiki_nodes_recursive(
        self,
        space_id: str,
        parent_node_token: str,
        headers: dict,
        account_name: str,
        space_name: str,
        docs: List[Dict],
        depth: int = 0
    ):
        """
        递归获取知识库节点

        Args:
            space_id: 知识库ID
            parent_node_token: 父节点token（None表示根节点）
            headers: 请求头
            account_name: 账号名称
            space_name: 知识库名称
            docs: 文档列表（输出参数）
            depth: 当前递归深度
        """
        indent = "  " * depth

        # 构建URL
        if parent_node_token:
            url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/{space_id}/nodes?page_size=50&parent_node_token={parent_node_token}"
        else:
            url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/{space_id}/nodes?page_size=50"

        response = requests.get(url, headers=headers)
        data = response.json()

        if data.get('code') != 0:
            logger.error(f"{indent}获取节点失败: {data.get('msg')}")
            return

        items = data.get('data', {}).get('items', [])

        for item in items:
            node_token = item.get('node_token')
            obj_token = item.get('obj_token')
            title = item.get('title', 'unnamed')
            obj_type = item.get('obj_type', '')
            has_child = item.get('has_child', False)

            # 如果有子节点，递归获取
            if has_child:
                logger.info(f"{indent}📁 {title} (obj_type={obj_type}, 有子节点)")
                self._fetch_wiki_nodes_recursive(
                    space_id, node_token, headers, account_name, space_name, docs, depth + 1
                )

            # 如果是文档类型，添加到列表（包括有子节点的父文档，因为它本身也可能是文档）
            if obj_type in ['docx', 'doc', 'sheet', 'bitable', 'mindnote', 'wiki']:
                docs.append({
                    "id": f"feishu_{account_name}_wiki_{node_token}",
                    "title": title,
                    "content": "",  # 内容稍后获取
                    "url": f"https://feishu.cn/wiki/{node_token}",
                    "source": "feishu",
                    "account": f"feishu_{account_name}",
                    "doc_type": "wiki",
                    "doc_token": obj_token,
                    "obj_type": obj_type,
                    "space_name": space_name,
                    "updated_at": datetime.now().timestamp(),
                    "store_locally": False
                })
                if not has_child:
                    logger.info(f"{indent}  📄 {title} ({obj_type})")

    def _fetch_from_account(self, account: FeishuAccount) -> List[Dict]:
        """
        使用应用身份获取文档（仅云空间）

        Args:
            account: 飞书账号实例

        Returns:
            文档列表
        """
        if not account.client:
            logger.warning(f"飞书账号 [{account.name}] 客户端未初始化")
            return []

        docs = []

        try:
            from lark_oapi.api.drive.v1 import ListFileRequest

            all_files = []
            page_token = None

            while True:
                request = ListFileRequest.builder() \
                    .page_size(50) \
                    .page_token(page_token) \
                    .build()

                response = account.client.drive.v1.file.list(request)

                if response.success() and response.data:
                    files = response.data.files if hasattr(response.data, 'files') else []
                    all_files.extend(files)

                    if not response.data.has_more:
                        break
                    page_token = response.data.next_page_token
                else:
                    if not response.success():
                        logger.error(f"获取文件列表失败 [{account.name}]: {response.code} - {response.msg}")
                    break

            logger.info(f"从飞书账号 [{account.name}] 获取到 {len(all_files)} 个文件")

            for file in all_files:
                try:
                    file_token = file.token
                    file_name = file.name
                    file_type = file.type

                    if file_type not in ['docx', 'doc', 'sheet', 'bitable', 'mindnote']:
                        continue

                    content_summary = self._get_document_summary(file_token, account.client, file_type)

                    doc_data = {
                        "id": f"feishu_{account.name}_drive_{file_token}",
                        "title": file_name,
                        "content": content_summary,
                        "url": f"https://feishu.cn/docx/{file_token}",
                        "source": "feishu",
                        "account": f"feishu_{account.name}",
                        "doc_type": "drive",
                        "doc_token": file_token,
                        "updated_at": datetime.now().timestamp(),
                        "store_locally": False
                    }

                    docs.append(doc_data)

                except Exception as e:
                    logger.warning(f"处理文件失败 [{file.name}]: {e}")
                    continue

        except Exception as e:
            logger.error(f"获取飞书文档失败 [{account.name}]: {e}")
            import traceback
            traceback.print_exc()

        return docs

    def get_document_content(self, doc_id: str, doc_token: str, account_name: str,
                            obj_type: str = "docx", user_access_token: str = None) -> Optional[str]:
        """
        获取文档完整内容

        Args:
            doc_id: 文档 ID
            doc_token: 文档 Token
            account_name: 账号名称
            obj_type: 文档对象类型（docx, sheet, bitable等）
            user_access_token: 用户访问令牌（可选）

        Returns:
            文档内容
        """
        if user_access_token:
            return self._get_doc_content_with_user_token(doc_token, user_access_token, obj_type)

        account = self.accounts.get(account_name)
        if account and account.client:
            return self._get_document_summary(doc_token, account.client, obj_type)

        return None

    def _get_doc_content_with_user_token(self, doc_token: str, user_access_token: str, obj_type: str = "docx") -> str:
        """使用用户令牌获取文档内容"""
        headers = {
            "Authorization": f"Bearer {user_access_token}",
            "Content-Type": "application/json"
        }

        # 根据文档类型选择不同的API
        if obj_type == "docx" or obj_type == "doc":
            return self._get_docx_content(doc_token, headers)
        elif obj_type == "sheet":
            return self._get_sheet_content(doc_token, headers)
        elif obj_type == "bitable":
            return self._get_bitable_content(doc_token, headers)
        elif obj_type == "mindnote":
            return self._get_mindnote_content(doc_token, headers)
        else:
            logger.warning(f"不支持的文档类型: {obj_type}")
            return ""

    def _get_docx_content(self, doc_token: str, headers: dict) -> str:
        """获取docx文档内容 - 使用 raw_content API 获取完整内容"""
        # 方法1: 使用 raw_content API 获取完整内容
        raw_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/raw_content"
        response = requests.get(raw_url, headers=headers)
        data = response.json()

        if data.get('code') == 0:
            content = data.get('data', {}).get('content', '')
            if content:
                return content[:5000] if len(content) > 5000 else content

        # 方法2: 如果 raw_content 失败，尝试 blocks API
        url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{doc_token}/children"
        response = requests.get(url, headers=headers)
        data = response.json()

        if data.get('code') == 0:
            items = data.get('data', {}).get('items', [])
            all_text = []

            for item in items:
                # 提取文本
                if 'text' in item and 'elements' in item['text']:
                    for elem in item['text']['elements']:
                        if 'text_run' in elem and 'content' in elem['text_run']:
                            all_text.append(elem['text_run']['content'])

            content = "\n".join(all_text)
            return content[:5000] if len(content) > 5000 else content

        logger.warning(f"获取docx内容失败: {data.get('msg')}")
        return ""

    def _get_sheet_content(self, doc_token: str, headers: dict) -> str:
        """获取电子表格内容"""
        # 1. 获取工作表列表
        sheets_url = f"https://open.feishu.cn/open-apis/sheets/v3/spreadsheets/{doc_token}/sheets/query"
        response = requests.get(sheets_url, headers=headers)
        data = response.json()

        all_content = []

        if data.get('code') == 0:
            sheets = data.get('data', {}).get('sheets', [])

            # 先在开头列出所有sheet名称，确保所有sheet名称都在embeddings的前5000字符内
            sheet_titles = [sheet.get('title', 'unnamed') for sheet in sheets]
            all_content.append("【工作表列表】")
            all_content.append(" | ".join(sheet_titles))
            all_content.append("")  # 空行分隔

            # 索引所有工作表，sheet 名必须包含在索引内容中
            for sheet in sheets:
                sheet_id = sheet.get('sheet_id')
                sheet_title = sheet.get('title', 'unnamed')

                # 2. 获取工作表数据
                data_url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{doc_token}/values/{sheet_id}"
                data_resp = requests.get(data_url, headers=headers)
                data_json = data_resp.json()

                if data_json.get('code') == 0:
                    values = data_json.get('data', {}).get('valueRange', {}).get('values', [])
                    if values:
                        # sheet 名作为标题，确保被索引
                        all_content.append(f"【工作表：{sheet_title}】")

                        # 累积当前 sheet 的内容，限制每个 sheet 最多 5000 字符
                        sheet_content = []
                        for row in values[:50]:  # 每个 sheet 最多 50 行
                            row_text = " | ".join([str(cell) if cell else "" for cell in row])
                            if row_text.strip():
                                sheet_content.append(row_text)

                        sheet_text = "\n".join(sheet_content)
                        # 每个 sheet 内容限制 5000 字符，确保所有 sheet 都能被索引
                        if len(sheet_text) > 5000:
                            sheet_text = sheet_text[:5000]
                        all_content.append(sheet_text)

            content = "\n".join(all_content)
            # 总内容限制 50000 字符，足够覆盖所有 sheet
            return content[:50000] if len(content) > 50000 else content

        logger.warning(f"获取电子表格内容失败: {data.get('msg')}")
        return ""

    def _get_bitable_content(self, doc_token: str, headers: dict) -> str:
        """获取多维表格内容"""
        # 1. 获取数据表列表
        tables_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{doc_token}/tables"
        response = requests.get(tables_url, headers=headers)
        data = response.json()

        all_content = []

        if data.get('code') == 0:
            tables = data.get('data', {}).get('items', [])
            for table in tables[:3]:  # 只取前3个数据表
                table_id = table.get('table_id')
                table_name = table.get('name', 'unnamed')

                # 2. 获取记录列表
                records_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{doc_token}/tables/{table_id}/records"
                records_resp = requests.get(records_url, headers=headers)
                records_json = records_resp.json()

                if records_json.get('code') == 0:
                    records = records_json.get('data', {}).get('items', [])
                    if records:
                        all_content.append(f"【{table_name}】")
                        for record in records[:20]:  # 每个表只取前20条记录
                            fields = record.get('fields', {})
                            row_text = " | ".join([f"{k}: {v}" for k, v in list(fields.items())[:5]])
                            if row_text.strip():
                                all_content.append(row_text)

            content = "\n".join(all_content)
            return content[:5000] if len(content) > 5000 else content

        logger.warning(f"获取多维表格内容失败: {data.get('msg')}")
        return ""

    def _get_mindnote_content(self, doc_token: str, headers: dict) -> str:
        """获取思维导图内容"""
        # 思维导图API较为复杂，这里简化处理，返回基本信息
        return f"思维导图文档: {doc_token}"

    def _get_document_summary(self, doc_id: str, client, doc_type: str = "docx") -> str:
        """获取文档摘要（应用身份）"""
        try:
            if doc_type == "docx":
                from lark_oapi.api.docx.v1 import GetDocumentBlockChildrenRequest

                all_text = []

                request = GetDocumentBlockChildrenRequest.builder() \
                    .document_id(doc_id) \
                    .block_id(doc_id) \
                    .build()

                response = client.docx.v1.document_block_children.get(request)

                if response.success() and response.data:
                    items = response.data.items if hasattr(response.data, 'items') else []

                    for item in items:
                        if item.text and hasattr(item.text, 'elements'):
                            for elem in item.text.elements:
                                if hasattr(elem, 'text_run') and elem.text_run:
                                    if hasattr(elem.text_run, 'content'):
                                        all_text.append(elem.text_run.content)

                content = "\n".join(all_text)
                return content[:5000] if len(content) > 5000 else content

            return ""

        except Exception as e:
            logger.warning(f"获取文档摘要失败 [{doc_id}]: {e}")

        return ""
