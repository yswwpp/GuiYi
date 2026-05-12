"""
同步元数据管理 - 使用 MySQL 记录同步状态
"""

import json
import hashlib
from datetime import datetime
from typing import Optional, Dict, List
import logging
from pathlib import Path
import pymysql
from pymysql.cursors import DictCursor

logger = logging.getLogger(__name__)


class DatabaseConfig:
    """数据库配置"""

    def __init__(self, config_path: str = "data/db_config.json"):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """加载配置文件"""
        if Path(self.config_path).exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f).get('database', {})
            except Exception as e:
                logger.warning(f"加载数据库配置失败: {e}，使用默认配置")

        # 默认使用 SQLite（向后兼容）
        return {"type": "sqlite", "path": "data/sync_metadata.sqlite"}

    @property
    def is_mysql(self) -> bool:
        return self.config.get('type', 'sqlite') == 'mysql'

    @property
    def mysql_config(self) -> dict:
        return {
            'host': self.config.get('host', '127.0.0.1'),
            'port': self.config.get('port', 3306),
            'user': self.config.get('user', 'root'),
            'password': self.config.get('password', ''),
            'database': self.config.get('database', 'guiyi'),
            'charset': 'utf8mb4'
        }


class SyncMetadata:
    """同步元数据管理"""

    def __init__(self, config_path: str = "data/db_config.json"):
        """
        Args:
            config_path: 数据库配置文件路径
        """
        self.db_config = DatabaseConfig(config_path)
        self._connection_pool = None

        # 初始化数据库
        self._init_db()
        logger.info(f"同步元数据数据库初始化完成: {'MySQL' if self.db_config.is_mysql else 'SQLite'}")

    def _get_connection(self):
        """获取数据库连接"""
        if self.db_config.is_mysql:
            return pymysql.connect(**self.db_config.mysql_config)
        else:
            import sqlite3
            db_path = self.db_config.config.get('path', 'data/sync_metadata.sqlite')
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            return sqlite3.connect(db_path, timeout=30)

    def _execute(self, query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False):
        """执行 SQL 语句"""
        conn = self._get_connection()
        try:
            if self.db_config.is_mysql:
                cursor = conn.cursor(DictCursor if fetch_one or fetch_all else None)
            else:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

            cursor.execute(query, params)

            result = None
            if fetch_one:
                row = cursor.fetchone()
                if row:
                    result = dict(row) if isinstance(row, dict) else dict(row)
            elif fetch_all:
                rows = cursor.fetchall()
                result = [dict(row) if isinstance(row, dict) else dict(row) for row in rows]
            else:
                result = cursor.lastrowid

            conn.commit()
            return result
        finally:
            conn.close()

    def _init_db(self):
        """初始化数据库表"""
        if self.db_config.is_mysql:
            self._init_mysql()
        else:
            self._init_sqlite()

    def _init_mysql(self):
        """初始化 MySQL 数据库"""
        # 先连接不指定数据库，创建数据库
        config = self.db_config.mysql_config.copy()
        db_name = config.pop('database')

        conn = pymysql.connect(**config)
        cursor = conn.cursor()

        # 创建数据库
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` DEFAULT CHARACTER SET utf8mb4")
        cursor.execute(f"USE `{db_name}`")

        # 同步元数据表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_metadata (
                id VARCHAR(255) PRIMARY KEY,
                source VARCHAR(50) NOT NULL,
                account VARCHAR(255),
                url TEXT,
                title TEXT,
                content_hash VARCHAR(64),
                file_size BIGINT DEFAULT 0,
                file_mtime DOUBLE DEFAULT 0,
                ai_summary TEXT,
                ai_tags TEXT,
                last_modified DOUBLE,
                last_synced DOUBLE,
                sync_status VARCHAR(20) DEFAULT 'synced',
                created_at DOUBLE DEFAULT 0,
                INDEX idx_source_account (source, account)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # 同步日志表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sync_time DOUBLE,
                source VARCHAR(50),
                account VARCHAR(255),
                action VARCHAR(50),
                doc_id VARCHAR(255),
                doc_title TEXT,
                error_message TEXT,
                INDEX idx_sync_time (sync_time)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        conn.commit()
        conn.close()
        logger.info(f"MySQL 数据库初始化完成: {db_name}")

    def _init_sqlite(self):
        """初始化 SQLite 数据库"""
        import sqlite3
        db_path = self.db_config.config.get('path', 'data/sync_metadata.sqlite')
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(db_path, timeout=30)
        cursor = conn.cursor()

        # 同步元数据表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_metadata (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                account TEXT,
                url TEXT,
                title TEXT,
                content_hash TEXT,
                file_size INTEGER DEFAULT 0,
                file_mtime REAL DEFAULT 0,
                ai_summary TEXT,
                ai_tags TEXT,
                last_modified REAL,
                last_synced REAL,
                sync_status TEXT DEFAULT 'synced',
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """)

        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_source_account
            ON sync_metadata(source, account)
        """)

        # 迁移：添加新字段（如果不存在）
        for column, definition in [
            ('file_size', 'INTEGER DEFAULT 0'),
            ('file_mtime', 'REAL DEFAULT 0'),
            ('ai_summary', 'TEXT'),
            ('ai_tags', 'TEXT')
        ]:
            try:
                cursor.execute(f"ALTER TABLE sync_metadata ADD COLUMN {column} {definition}")
            except sqlite3.OperationalError:
                pass  # 字段已存在

        # 同步日志表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sync_time REAL,
                source TEXT,
                account TEXT,
                action TEXT,
                doc_id TEXT,
                doc_title TEXT,
                error_message TEXT
            )
        """)

        conn.commit()
        conn.close()

    def _calculate_hash(self, content: str) -> str:
        """计算内容哈希"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def get_doc_state(self, doc_id: str) -> Optional[Dict]:
        """获取文档上次同步状态"""
        return self._execute(
            "SELECT * FROM sync_metadata WHERE id = %s",
            (doc_id,),
            fetch_one=True
        )

    def upsert_doc(
        self,
        doc_id: str,
        source: str,
        url: str,
        title: str,
        content_hash: str,
        last_modified: float,
        account: str = None,
        file_size: int = 0,
        file_mtime: float = 0.0,
        ai_summary: str = None,
        ai_tags: str = None
    ):
        """插入或更新文档同步状态"""
        now = datetime.now().timestamp()

        if self.db_config.is_mysql:
            # MySQL 使用 ON DUPLICATE KEY UPDATE
            self._execute("""
                INSERT INTO sync_metadata
                (id, source, account, url, title, content_hash, last_modified, last_synced, sync_status,
                 file_size, file_mtime, ai_summary, ai_tags)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    source = VALUES(source),
                    account = VALUES(account),
                    url = VALUES(url),
                    title = VALUES(title),
                    content_hash = VALUES(content_hash),
                    last_modified = VALUES(last_modified),
                    last_synced = VALUES(last_synced),
                    sync_status = VALUES(sync_status),
                    file_size = VALUES(file_size),
                    file_mtime = VALUES(file_mtime),
                    ai_summary = VALUES(ai_summary),
                    ai_tags = VALUES(ai_tags)
            """, (
                doc_id, source, account, url, title, content_hash, last_modified, now, "synced",
                file_size, file_mtime, ai_summary, ai_tags
            ))
        else:
            # SQLite 使用 INSERT OR REPLACE
            self._execute("""
                INSERT OR REPLACE INTO sync_metadata
                (id, source, account, url, title, content_hash, last_modified, last_synced, sync_status,
                 file_size, file_mtime, ai_summary, ai_tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                doc_id, source, account, url, title, content_hash, last_modified, now, "synced",
                file_size, file_mtime, ai_summary, ai_tags
            ))

    def mark_deleted(self, doc_id: str):
        """标记文档已删除"""
        if self.db_config.is_mysql:
            self._execute(
                "UPDATE sync_metadata SET sync_status = 'deleted' WHERE id = %s",
                (doc_id,)
            )
        else:
            self._execute(
                "UPDATE sync_metadata SET sync_status = 'deleted' WHERE id = ?",
                (doc_id,)
            )

    def update_file_info(self, doc_id: str, file_size: int, file_mtime: float):
        """更新文件大小和修改时间"""
        now = datetime.now().timestamp()
        if self.db_config.is_mysql:
            self._execute(
                "UPDATE sync_metadata SET file_size = %s, file_mtime = %s, last_synced = %s WHERE id = %s",
                (file_size, file_mtime, now, doc_id)
            )
        else:
            self._execute(
                "UPDATE sync_metadata SET file_size = ?, file_mtime = ?, last_synced = ? WHERE id = ?",
                (file_size, file_mtime, now, doc_id)
            )

    def get_all_synced_docs(
        self,
        source: str = None,
        account: str = None
    ) -> List[Dict]:
        """获取所有已同步文档"""
        query = "SELECT * FROM sync_metadata WHERE sync_status = 'synced'"
        params = []
        placeholder = "%s" if self.db_config.is_mysql else "?"

        if source:
            query += f" AND source = {placeholder}"
            params.append(source)

        if account:
            query += f" AND account = {placeholder}"
            params.append(account)

        return self._execute(query, tuple(params), fetch_all=True) or []

    def cleanup_deleted(
        self,
        current_doc_ids: List[str],
        source: str = None,
        account: str = None
    ) -> List[str]:
        """清理已删除文档的索引"""
        if not current_doc_ids:
            return []

        placeholder = "%s" if self.db_config.is_mysql else "?"
        placeholders = ",".join([placeholder] * len(current_doc_ids))

        query = f"""
            SELECT id FROM sync_metadata
            WHERE sync_status = 'synced'
            AND id NOT IN ({placeholders})
        """
        params = list(current_doc_ids)

        if source:
            query += f" AND source = {placeholder}"
            params.append(source)

        if account:
            query += f" AND account = {placeholder}"
            params.append(account)

        rows = self._execute(query, tuple(params), fetch_all=True) or []
        deleted_docs = [row['id'] if isinstance(row, dict) else row[0] for row in rows]

        # 标记为删除
        for doc_id in deleted_docs:
            self.mark_deleted(doc_id)

        return deleted_docs

    def log_sync(
        self,
        source: str,
        action: str,
        doc_id: str,
        doc_title: str,
        account: str = None,
        error: str = None
    ):
        """记录同步日志"""
        now = datetime.now().timestamp()

        if self.db_config.is_mysql:
            self._execute("""
                INSERT INTO sync_logs
                (sync_time, source, account, action, doc_id, doc_title, error_message)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (now, source, account, action, doc_id, doc_title, error))
        else:
            self._execute("""
                INSERT INTO sync_logs
                (sync_time, source, account, action, doc_id, doc_title, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (now, source, account, action, doc_id, doc_title, error))

    def get_sync_stats(self, source: str = None, account: str = None) -> Dict:
        """获取同步统计信息"""
        placeholder = "%s" if self.db_config.is_mysql else "?"
        query = "SELECT COUNT(*) as count FROM sync_metadata WHERE sync_status = 'synced'"
        params = []

        if source:
            query += f" AND source = {placeholder}"
            params.append(source)

        if account:
            query += f" AND account = {placeholder}"
            params.append(account)

        result = self._execute(query, tuple(params), fetch_one=True)
        total_docs = result['count'] if result else 0

        # 获取最近同步时间
        last_sync_result = self._execute(
            "SELECT MAX(last_synced) as last_sync FROM sync_metadata",
            fetch_one=True
        )
        last_sync = last_sync_result['last_sync'] if last_sync_result else None

        return {
            "total_documents": total_docs,
            "last_sync_time": last_sync
        }

    def get_source_stats(self) -> Dict[str, Dict]:
        """获取每个数据源的统计信息"""
        rows = self._execute("""
            SELECT source, COUNT(*) as count, MAX(last_synced) as last_sync
            FROM sync_metadata
            WHERE sync_status = 'synced'
            GROUP BY source
        """, fetch_all=True) or []

        result = {}
        for row in rows:
            source = row['source']
            result[source] = {
                "count": row['count'],
                "last_sync": row['last_sync']
            }

        return result


# 使用示例
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # 创建元数据管理器
    metadata = SyncMetadata()

    # 插入测试文档
    doc_id = "test_mysql_001"
    metadata.upsert_doc(
        doc_id=doc_id,
        source="test",
        account="test_account",
        url="https://example.com/test",
        title="MySQL 测试文档",
        content_hash=metadata._calculate_hash("这是测试内容"),
        last_modified=datetime.now().timestamp()
    )

    # 查询文档状态
    state = metadata.get_doc_state(doc_id)
    print(f"文档状态: {state}")

    # 获取统计信息
    stats = metadata.get_sync_stats()
    print(f"统计信息: {stats}")
