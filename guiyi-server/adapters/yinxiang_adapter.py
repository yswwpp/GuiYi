"""
印象笔记适配器 - 优化版

支持：
- 国际版 Evernote
- 中国版印象笔记
- Developer Token 认证
- 增量同步（避免限流）

优化策略：
1. 使用 sync API 只获取变更的笔记
2. 缓存笔记本列表
3. 批量处理，减少 API 调用
4. 检测限流并优雅处理
"""

import os
import json
import logging
import time
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
import re
import html

logger = logging.getLogger(__name__)


@dataclass
class YinxiangAccount:
    """印象笔记账号配置"""
    name: str
    token: str
    note_store_url: str
    is_china: bool = True
    sync_notebooks: List[str] = field(default_factory=list)
    # 分批同步：每次最多获取多少条笔记内容（避免限流）
    max_notes_per_sync: int = 100
    # 从 token 解析的 shard_id 和 user_id（用于生成正确的 URL）
    shard_id: str = ""
    user_id: str = ""

    def __post_init__(self):
        """从 token 解析 shard_id 和 user_id"""
        self._parse_token_info()

    def _parse_token_info(self):
        """
        从 Token 解析 shard ID 和 user ID

        Token 格式: S=s1:U=124701:E=...:P=...:A=...:V=...:H=...
        - S=s1 → shard ID 是 "s1"
        - U=124701 → user ID 是 "124701"
        """
        try:
            # 解析 token 中的各个字段
            parts = self.token.split(':')
            for part in parts:
                if part.startswith('S='):
                    self.shard_id = part[2:]
                elif part.startswith('U='):
                    self.user_id = part[2:]

            logger.info(f"从 Token 解析: shard_id={self.shard_id}, user_id={self.user_id}")
        except Exception as e:
            logger.warning(f"解析 Token 失败: {e}")


class YinxiangAdapter:
    """印象笔记适配器 - 优化版"""

    # API 调用间隔，避免限流（印象笔记限流严格，增加到 1.5 秒）
    API_CALL_DELAY = 1.5  # 每次调用间隔 1.5 秒

    # 限流处理策略
    RATE_LIMIT_MAX_WAIT = 3600  # 单次限流最多等待 1 小时
    RATE_LIMIT_RETRY_COUNT = 3  # 同一笔记最多重试3次
    RATE_LIMIT_GLOBAL_PAUSE = True  # 全局暂停标志

    # 每小时同步限制（印象笔记 API 每小时有限额）
    HOURLY_SYNC_LIMIT = 30  # 每小时最多同步 30 条笔记

    def __init__(self):
        self.accounts: Dict[str, YinxiangAccount] = {}
        self._note_stores: Dict[str, object] = {}
        self._tokens: Dict[str, str] = {}
        self._notebook_cache: Dict[str, List[Dict]] = {}  # 笔记本缓存
        self._last_call_time: float = 0  # 上次 API 调用时间
        self._sync_state_cache: Dict[str, int] = {}  # sync state 缓存
        self._hourly_sync_count: Dict[str, int] = {}  # 每小时同步计数
        self._hourly_sync_hour: Dict[str, int] = {}  # 当前小时

        # 同步状态存储路径
        self._sync_state_path = os.path.join(
            os.path.dirname(__file__), '..', 'data', 'yinxiang_sync_state.json'
        )
        self._load_sync_state()

    def _load_sync_state(self):
        """加载上次同步状态"""
        if os.path.exists(self._sync_state_path):
            try:
                with open(self._sync_state_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._sync_state_cache = data.get('sync_states', {})
                    self._notebook_cache = data.get('notebook_cache', {})
            except Exception as e:
                logger.warning(f"加载同步状态失败: {e}")

    def _save_sync_state(self):
        """保存同步状态"""
        try:
            os.makedirs(os.path.dirname(self._sync_state_path), exist_ok=True)
            with open(self._sync_state_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'sync_states': self._sync_state_cache,
                    'notebook_cache': self._notebook_cache
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存同步状态失败: {e}")

    def _rate_limit_check(self):
        """速率限制检查 - 确保调用间隔"""
        elapsed = time.time() - self._last_call_time
        if elapsed < self.API_CALL_DELAY:
            time.sleep(self.API_CALL_DELAY - elapsed)
        self._last_call_time = time.time()

    def add_account(self, account: YinxiangAccount):
        """添加账号"""
        self.accounts[account.name] = account
        logger.info(f"添加印象笔记账号: {account.name}")

    def _get_note_store(self, account_name: str):
        """获取 NoteStore（延迟初始化）"""
        if account_name not in self.accounts:
            return None, None

        if account_name in self._note_stores:
            return self._note_stores[account_name], self._tokens[account_name]

        account = self.accounts[account_name]
        try:
            from evernote.edam.notestore import NoteStore
            import thrift.transport.THttpClient as THttpClient
            import thrift.protocol.TBinaryProtocol as TBinaryProtocol

            transport = THttpClient.THttpClient(account.note_store_url)
            protocol = TBinaryProtocol.TBinaryProtocol(transport)
            note_store = NoteStore.Client(protocol)

            self._note_stores[account_name] = note_store
            self._tokens[account_name] = account.token

            logger.info(f"印象笔记 NoteStore 连接成功: {account_name}")
            return note_store, account.token

        except Exception as e:
            logger.error(f"印象笔记连接失败: {e}")
            return None, None

    def get_sync_state(self, account_name: str) -> Optional[int]:
        """
        获取同步状态（用于增量同步）

        Returns:
            sync_chunk 数，用于判断是否有变更
        """
        note_store, token = self._get_note_store(account_name)
        if not note_store:
            return None

        try:
            self._rate_limit_check()
            sync_state = note_store.getSyncState(token)
            return sync_state.updateCount
        except Exception as e:
            logger.error(f"获取同步状态失败: {e}")
            # 检测限流
            if 'rateLimitDuration' in str(e):
                logger.warning(f"API 限流，需要等待")
            return None

    def list_notebooks(self, account_name: str, use_cache: bool = True) -> List[Dict]:
        """
        列出所有笔记本（支持缓存）
        """
        # 使用缓存
        if use_cache and account_name in self._notebook_cache:
            cached = self._notebook_cache[account_name]
            logger.info(f"使用缓存笔记本列表: {len(cached)} 个")
            return cached

        note_store, token = self._get_note_store(account_name)
        if not note_store:
            return []

        try:
            self._rate_limit_check()
            notebooks = note_store.listNotebooks(token)
            result = []
            for nb in notebooks:
                result.append({
                    "guid": nb.guid,
                    "name": nb.name,
                    "default_notebook": getattr(nb, 'defaultNotebook', False),
                    "stack": getattr(nb, 'stack', None),
                })

            # 缓存结果
            self._notebook_cache[account_name] = result
            self._save_sync_state()

            logger.info(f"获取笔记本列表: {len(result)} 个")
            return result

        except Exception as e:
            logger.error(f"获取笔记本列表失败: {e}")
            return []

    def get_sync_chunk(self, account_name: str, after_usn: int = 0) -> Optional[object]:
        """
        获取同步块（增量同步的核心）

        Args:
            account_name: 账号名
            after_usn: 上次同步的 update sequence number

        Returns:
            SyncChunk 对象，包含变更的笔记信息
        """
        note_store, token = self._get_note_store(account_name)
        if not note_store:
            return None

        try:
            self._rate_limit_check()
            # 获取同步块，最多 500 条笔记
            sync_chunk = note_store.getSyncChunk(
                token,
                after_usn,  # 从上次同步位置开始
                500,        # 最大条数
                True        # includeNotes
            )
            return sync_chunk

        except Exception as e:
            logger.error(f"获取同步块失败: {e}")
            if 'rateLimitDuration' in str(e):
                logger.warning("API 限流")
            return None

    def list_notes_incremental(self, account_name: str, last_usn: int = 0) -> List[Dict]:
        """
        增量获取笔记列表（只获取变更的笔记）

        Args:
            account_name: 账号名
            last_usn: 上次同步的 update sequence number

        Returns:
            变更的笔记列表
        """
        note_store, token = self._get_note_store(account_name)
        if not note_store:
            return []

        notes = []
        current_usn = last_usn

        try:
            while True:
                self._rate_limit_check()
                sync_chunk = note_store.getSyncChunk(
                    token,
                    current_usn,
                    100,  # 每批 100 条
                    True  # includeNotes
                )

                if not sync_chunk or not sync_chunk.notes:
                    break

                for note in sync_chunk.notes:
                    notes.append({
                        "guid": note.guid,
                        "title": note.title,
                        "notebook_guid": note.notebookGuid,
                        "created": note.created,
                        "updated": note.updated,
                        "active": note.active,  # 是否被删除
                        "update_seq_num": note.updateSequenceNum
                    })

                current_usn = sync_chunk.chunkHighUSN

                # 如果已到达最新
                if sync_chunk.chunkHighUSN >= sync_chunk.updateCount:
                    break

                logger.info(f"增量同步: 已获取 {len(notes)} 条，继续...")

            logger.info(f"增量同步完成: {len(notes)} 条变更笔记")
            return notes

        except Exception as e:
            logger.error(f"增量获取笔记失败: {e}")
            if 'rateLimitDuration' in str(e):
                logger.warning("API 限流")
            return notes  # 返回已获取的部分

    def get_note_content(self, account_name: str, note_guid: str, retry_count: int = 0) -> Optional[str]:
        """
        获取笔记内容（支持限流重试）

        Args:
            account_name: 账号名
            note_guid: 笔记 GUID
            retry_count: 当前重试次数

        Returns:
            笔记内容，限流时返回 None（会自动重试）
        """
        note_store, token = self._get_note_store(account_name)
        if not note_store:
            return None

        try:
            self._rate_limit_check()
            note = note_store.getNote(token, note_guid, True, False, False, False)
            content = note.content
            return self._extract_text_from_enml(content)

        except Exception as e:
            error_str = str(e)

            # 检测限流
            if 'errorCode=19' in error_str or 'RATE_LIMIT_REACHED' in error_str or 'rateLimitDuration' in error_str:
                # 解析等待时间
                rate_limit_duration = self._parse_rate_limit_duration(error_str)

                if rate_limit_duration and retry_count < self.RATE_LIMIT_RETRY_COUNT:
                    # 限流时间很长，直接等待实际时间（但最多 1 小时）
                    wait_time = min(rate_limit_duration + 60, self.RATE_LIMIT_MAX_WAIT)  # 多等 60 秒确保安全
                    logger.warning(f"API 限流，需等待 {rate_limit_duration} 秒，实际等待 {wait_time} 秒后重试: {note_guid[:20]}...")
                    time.sleep(wait_time)
                    return self.get_note_content(account_name, note_guid, retry_count + 1)
                else:
                    logger.warning(f"API 限流，已达重试上限: {note_guid[:20]}...")
                    return None
            else:
                logger.error(f"获取笔记内容失败 [{note_guid[:20]}]: {e}")
                return None

    def _parse_rate_limit_duration(self, error_str: str) -> Optional[int]:
        """
        从错误信息中解析限流等待时间

        Args:
            error_str: 异常字符串

        Returns:
            等待秒数，无法解析时返回 None
        """
        # 格式类似: rateLimitDuration=3464 或 rateLimitDuration: 3464
        import re
        match = re.search(r'rateLimitDuration[=:]\s*(\d+)', error_str)
        if match:
            return int(match.group(1))
        return None

    def get_pending_notes_content(self, account_name: str, note_guids: List[str]) -> List[Dict]:
        """
        获取待处理笔记的内容（用于继续上次未完成的同步）

        Args:
            account_name: 账号名
            note_guids: 待处理的笔记 GUID 列表

        Returns:
            成功获取的笔记文档列表
        """
        documents = []

        if account_name not in self.accounts:
            logger.error(f"账号不存在: {account_name}")
            return documents

        account = self.accounts[account_name]

        notebooks = self.list_notebooks(account_name, use_cache=True)
        notebook_map = {nb["guid"]: nb["name"] for nb in notebooks}

        for guid in note_guids:
            content = self.get_note_content(account_name, guid)
            if content:
                # 获取笔记元数据
                note_store, token = self._get_note_store(account_name)
                if note_store:
                    try:
                        self._rate_limit_check()
                        note_meta = note_store.getNote(token, guid, False, False, False, False)
                        notebook_name = notebook_map.get(note_meta.notebookGuid, "未知笔记本")

                        doc = {
                            "id": f"yinxiang_{account_name}_{guid}",
                            "title": note_meta.title,
                            "text": content[:5000],
                            "content": content[:5000],
                            "url": self._build_note_url(account, guid),
                            "source": "yinxiang",
                            "account": account_name,
                            "notebook": notebook_name,
                            "created": note_meta.created,
                            "updated": note_meta.updated,
                            "updated_at": note_meta.updated
                        }
                        documents.append(doc)
                    except Exception as e:
                        logger.error(f"获取笔记元数据失败 [{guid}]: {e}")

        return documents

    def _extract_text_from_enml(self, enml: str) -> str:
        """从 ENML 提取纯文本"""
        if not enml:
            return ""

        text = re.sub(r'<\?xml[^>]*\?>', '', enml)
        text = re.sub(r'<!DOCTYPE[^>]*>', '', text)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        text = html.unescape(text)

        return text

    def _build_note_url(self, account: YinxiangAccount, note_guid: str) -> str:
        """
        构建笔记 URL

        正确格式: https://app.yinxiang.com/shard/{shardId}/nl/{userId}/{noteGuid}
        或: https://www.evernote.com/shard/{shardId}/nl/{userId}/{noteGuid}

        Args:
            account: 账号配置
            note_guid: 笔记 GUID

        Returns:
            笔记的完整 URL
        """
        shard_id = account.shard_id or "s1"  # 默认值
        user_id = account.user_id

        if account.is_china:
            base_url = "https://app.yinxiang.com"
        else:
            base_url = "https://www.evernote.com"

        if user_id:
            return f"{base_url}/shard/{shard_id}/nl/{user_id}/{note_guid}"
        else:
            # 如果没有解析到 user_id，使用旧格式（可能不工作）
            logger.warning(f"账号 {account.name} 未解析到 user_id，URL 可能无法打开")
            return f"{base_url}/shard/{shard_id}/nl/{note_guid}"

    def fetch_all_for_index(self, account_name: str = None) -> List[Dict]:
        """
        增量同步获取笔记用于索引

        使用增量同步策略：
        1. 检查 sync state 判断是否有变更
        2. 只获取变更的笔记
        3. 只获取需要更新/新增的笔记内容
        4. 限流时保存未完成的笔记，下次继续
        """
        documents = []
        failed_notes = []  # 限流失败的笔记

        accounts_to_sync = [account_name] if account_name else list(self.accounts.keys())

        for acc_name in accounts_to_sync:
            if acc_name not in self.accounts:
                continue

            account = self.accounts[acc_name]

            # 获取笔记本列表（使用缓存）
            notebooks = self.list_notebooks(acc_name, use_cache=True)
            notebook_map = {nb["guid"]: nb["name"] for nb in notebooks}

            # 获取上次同步状态
            last_usn = self._sync_state_cache.get(acc_name, 0)

            # 获取已成功同步的笔记列表（包含 updated 时间戳，用于检测更新）
            synced_notes_key = f"{acc_name}_synced"
            synced_notes_data = self._sync_state_cache.get(synced_notes_key, {})
            # 格式: {"guid": {"updated": 123456, "usn": 100}, ...}
            synced_note_guids = set(synced_notes_data.keys())

            # 获取上次失败的笔记列表
            pending_notes_key = f"{acc_name}_pending"
            pending_note_guids = set(self._sync_state_cache.get(pending_notes_key, []))

            # 检查是否有变更
            current_sync_state = self.get_sync_state(acc_name)
            if current_sync_state is None:
                logger.warning(f"无法获取同步状态，跳过 {acc_name}")
                continue

            # 如果有待处理的笔记，优先处理它们
            if pending_note_guids:
                logger.info(f"账号 [{acc_name}] 有 {len(pending_note_guids)} 条待处理笔记，优先处理")
                pending_docs = self.get_pending_notes_content(acc_name, list(pending_note_guids))
                documents.extend(pending_docs)
                # 移除已成功获取的笔记
                for doc in pending_docs:
                    guid = doc["id"].split("_")[-1]
                    pending_note_guids.discard(guid)
                logger.info(f"待处理笔记已获取 {len(pending_docs)} 条")

            if current_sync_state == last_usn and not pending_note_guids:
                logger.info(f"账号 [{acc_name}] 无变更且无待处理，跳过同步")
                continue

            logger.info(f"账号 [{acc_name}] 有变更: last_usn={last_usn}, current={current_sync_state}")

            # 增量获取笔记
            changed_notes = self.list_notes_incremental(acc_name, last_usn)

            if not changed_notes and not pending_note_guids:
                logger.info(f"账号 [{acc_name}] 无变更笔记")
                continue

            # 过滤笔记本范围
            if account.sync_notebooks:
                sync_notebook_guids = {
                    nb["guid"] for nb in notebooks
                    if nb["name"] in account.sync_notebooks
                }
                changed_notes = [
                    n for n in changed_notes
                    if n["notebook_guid"] in sync_notebook_guids
                ]

            # 处理变更笔记
            new_usn = last_usn
            rate_limited = False
            processed_count = 0
            skipped_synced = 0
            MAX_NOTES_PER_SYNC = 50  # 每次同步最多处理 50 条笔记内容，避免限流
            newly_synced_guids = []  # 本次成功同步的笔记

            for note in changed_notes:
                # 更新 USN（即使不获取内容也要更新进度）
                if note.get("update_seq_num") > new_usn:
                    new_usn = note["update_seq_num"]

                # 被删除的笔记不处理
                if not note.get("active", True):
                    logger.debug(f"笔记已删除: {note['title']}")
                    # 从已同步列表移除
                    synced_note_guids.discard(note["guid"])
                    continue

                # 跳过已成功同步的笔记（避免重复获取），但如果笔记有更新则需要重新获取
                note_updated = note.get("updated", 0)
                synced_data = synced_notes_data.get(note["guid"])
                if synced_data and synced_data.get("updated") == note_updated:
                    # 笔记未更新，跳过
                    skipped_synced += 1
                    continue

                # 检查是否达到单次同步上限
                if processed_count >= MAX_NOTES_PER_SYNC:
                    # 达到上限，剩余笔记作为待处理
                    remaining_guids = [n["guid"] for n in changed_notes[changed_notes.index(note):] if n.get("active", True) and n["guid"] not in synced_note_guids]
                    failed_notes.extend(remaining_guids)
                    logger.info(f"达到单次同步上限 ({MAX_NOTES_PER_SYNC})，剩余 {len(remaining_guids)} 条笔记待处理")
                    break

                # 获取笔记内容
                content = self.get_note_content(acc_name, note["guid"])
                processed_count += 1

                # 检查是否限流
                if content is None:
                    # 可能是限流或其他错误，记录待处理
                    failed_notes.append(note["guid"])
                    rate_limited = True
                    logger.warning(f"笔记内容获取失败，已记录待处理: {note['title']}")
                    continue

                if not content:
                    continue

                notebook_name = notebook_map.get(note["notebook_guid"], "未知笔记本")

                doc = {
                    "id": f"yinxiang_{acc_name}_{note['guid']}",
                    "title": note["title"],
                    "text": content[:5000],
                    "content": content[:5000],
                    "url": self._build_note_url(account, note["guid"]),
                    "source": "yinxiang",
                    "account": acc_name,
                    "notebook": notebook_name,
                    "created": note["created"],
                    "updated": note["updated"],
                    "updated_at": note["updated"]
                }
                documents.append(doc)

                # 记录成功同步（包含 updated 时间戳，用于下次检测更新）
                newly_synced_guids.append({
                    "guid": note["guid"],
                    "updated": note["updated"],
                    "usn": note.get("update_seq_num", 0)
                })
                synced_notes_data[note["guid"]] = {
                    "updated": note["updated"],
                    "usn": note.get("update_seq_num", 0)
                }

            # 计算待处理笔记总数（变更笔记中未同步的）
            unsynced_count = len([n for n in changed_notes if n.get("active", True) and (n["guid"] not in synced_notes_data or synced_notes_data.get(n["guid"], {}).get("updated") != n.get("updated"))])

            # 保存同步状态
            # 1. 保存已成功同步的笔记数据（包含 updated 时间戳）
            # 只保留最近 1000 条，避免文件过大
            if len(synced_notes_data) > 1000:
                # 按更新时间排序，保留最新的
                sorted_guids = sorted(synced_notes_data.keys(), key=lambda g: synced_notes_data[g].get("updated", 0), reverse=True)
                synced_notes_data = {g: synced_notes_data[g] for g in sorted_guids[:1000]}
            self._sync_state_cache[synced_notes_key] = synced_notes_data

            # 2. 保存待处理笔记
            if failed_notes:
                existing_pending = self._sync_state_cache.get(pending_notes_key, [])
                all_pending = list(set(existing_pending + failed_notes))
                self._sync_state_cache[pending_notes_key] = all_pending

            # 3. 全部完成时更新 USN 并清理
            if unsynced_count == 0 and not rate_limited:
                self._sync_state_cache[acc_name] = new_usn
                if pending_notes_key in self._sync_state_cache:
                    del self._sync_state_cache[pending_notes_key]
                logger.info(f"账号 [{acc_name}] 全量同步完成，USN={new_usn}")

            self._save_sync_state()

            logger.info(f"账号 [{acc_name}] 同步完成: 新增 {len(documents)} 条，跳过已同步 {skipped_synced} 条，待处理 {unsynced_count} 条")

        return documents

    def test_connection(self, account_name: str = None, token: str = None, note_store_url: str = None) -> Dict:
        """测试连接"""
        result = {"success": False, "message": "", "notebook_count": 0, "note_count": 0}

        try:
            from evernote.edam.notestore import NoteStore
            from evernote.edam.notestore.ttypes import NoteFilter, NotesMetadataResultSpec
            import thrift.transport.THttpClient as THttpClient
            import thrift.protocol.TBinaryProtocol as TBinaryProtocol

            if token and note_store_url:
                test_token = token
                test_url = note_store_url
            elif account_name and account_name in self.accounts:
                account = self.accounts[account_name]
                test_token = account.token
                test_url = account.note_store_url
            else:
                result["message"] = "缺少连接参数"
                return result

            transport = THttpClient.THttpClient(test_url)
            protocol = TBinaryProtocol.TBinaryProtocol(transport)
            note_store = NoteStore.Client(protocol)

            # 获取笔记本数量
            notebooks = note_store.listNotebooks(test_token)
            result["notebook_count"] = len(notebooks)

            # 获取同步状态（包含笔记计数等信息）
            sync_state = note_store.getSyncState(test_token)
            # SyncState 有 updateCount 等属性，不是 noteCount
            result["note_count"] = getattr(sync_state, 'noteCount', getattr(sync_state, 'updateCount', 0))

            result["success"] = True
            result["message"] = f"连接成功，共 {result['notebook_count']} 个笔记本"

        except Exception as e:
            error_msg = str(e)
            if 'rateLimitDuration' in error_msg:
                result["message"] = "API 限流，请稍后再试"
            else:
                result["message"] = f"连接失败: {e}"

        return result

    def reset_sync_state(self, account_name: str):
        """重置同步状态（强制全量同步）"""
        if account_name in self._sync_state_cache:
            del self._sync_state_cache[account_name]
        if account_name in self._notebook_cache:
            del self._notebook_cache[account_name]
        self._save_sync_state()
        logger.info(f"已重置账号 [{account_name}] 同步状态")


# 导出
__all__ = ['YinxiangAdapter', 'YinxiangAccount']