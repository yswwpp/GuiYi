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

from guiyi_server.config import settings

logger = logging.getLogger(__name__)


class DatabaseConfig:
    """数据库配置"""

    def __init__(self, config_path: str = None):
        self.config_path = config_path or settings.DB_CONFIG_PATH
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """加载配置文件"""
        if Path(self.config_path).exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f).get('database', {})
            except Exception as e:
                raise RuntimeError(f"加载数据库配置失败: {e}")

        raise FileNotFoundError(f"数据库配置文件不存在: {self.config_path}")

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

    def __init__(self, config_path: str = None):
        """
        Args:
            config_path: 数据库配置文件路径
        """
        self.db_config = DatabaseConfig(config_path)
        self._connection_pool = None

        # 初始化数据库
        self._init_db()
        logger.info("同步元数据数据库初始化完成: MySQL")

    def _get_connection(self):
        """获取数据库连接"""
        return pymysql.connect(**self.db_config.mysql_config)

    def _execute(self, query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False):
        """执行 SQL 语句"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor(DictCursor if fetch_one or fetch_all else None)
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
                doc_type VARCHAR(50) DEFAULT NULL,
                mime_type VARCHAR(100) DEFAULT NULL,
                extension VARCHAR(20) DEFAULT NULL,
                content_hash VARCHAR(64),
                file_size BIGINT DEFAULT 0,
                file_mtime DOUBLE DEFAULT 0,
                ai_summary TEXT,
                ai_tags TEXT,
                last_modified DOUBLE,
                last_synced DOUBLE,
                sync_status VARCHAR(20) DEFAULT 'synced',
                created_at DOUBLE DEFAULT 0,
                INDEX idx_source_account (source, account),
                INDEX idx_doc_type (source, doc_type),
                INDEX idx_extension (extension)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # 兼容已有表：补齐新增字段（doc_type / mime_type / extension）
        self._migrate_add_type_columns(cursor)

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
                doc_type VARCHAR(50) DEFAULT NULL,
                error_message TEXT,
                INDEX idx_sync_time (sync_time)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # 兼容已有表：补齐 sync_logs.doc_type
        self._migrate_add_column(cursor, 'sync_logs', 'doc_type', 'VARCHAR(50) DEFAULT NULL')

        conn.commit()
        conn.close()
        logger.info(f"MySQL 数据库初始化完成: {db_name}")

    def _migrate_add_column(self, cursor, table: str, column: str, definition: str):
        """给已有表补齐单个字段（若不存在）"""
        try:
            cursor.execute(f"DESCRIBE `{table}`")
            existing_cols = {row[0] for row in cursor.fetchall()}
            if column not in existing_cols:
                cursor.execute(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}")
                logger.info(f"已为表 {table} 添加字段 {column}")
        except Exception as e:
            logger.warning(f"检查/添加字段 {table}.{column} 失败: {e}")

    def _migrate_add_type_columns(self, cursor):
        """为已有 sync_metadata 表补齐 doc_type/mime_type/extension 并回填"""
        # 先检查字段是否存在，不存在则添加
        cursor.execute("DESCRIBE sync_metadata")
        existing_cols = {row[0] for row in cursor.fetchall()}

        for col, defn in [
            ('doc_type', 'VARCHAR(50) DEFAULT NULL'),
            ('mime_type', 'VARCHAR(100) DEFAULT NULL'),
            ('extension', 'VARCHAR(20) DEFAULT NULL'),
        ]:
            if col not in existing_cols:
                cursor.execute(f"ALTER TABLE sync_metadata ADD COLUMN `{col}` {defn}")
                logger.info(f"sync_metadata 添加字段: {col}")

        # 添加索引（幂等，已存在则忽略）
        for idx_sql in [
            "ALTER TABLE sync_metadata ADD INDEX idx_doc_type (source, doc_type)",
            "ALTER TABLE sync_metadata ADD INDEX idx_extension (extension)",
        ]:
            try:
                cursor.execute(idx_sql)
            except Exception as e:
                logger.debug(f"添加索引跳过: {e}")

        # 回填 doc_type / extension（幂等，每次启动都跑，只更新空值）
        self._backfill_doc_type(cursor)

    def _backfill_doc_type(self, cursor):
        """回填 doc_type / extension（幂等，只更新 NULL 或空字符串的行）"""
        try:
            # 1) local 源：从 URL（file://...）推断扩展名
            cursor.execute("""
                UPDATE sync_metadata
                SET extension = LOWER(SUBSTRING_INDEX(url, '.', -1))
                WHERE source = 'local' AND (extension IS NULL OR extension = '')
                  AND url LIKE '%%.%%'
            """)
            # 2) local 源：doc_type = 扩展名
            cursor.execute("""
                UPDATE sync_metadata
                SET doc_type = extension
                WHERE source = 'local' AND (doc_type IS NULL OR doc_type = '')
                  AND extension IS NOT NULL AND extension != ''
            """)
            # 3) feishu 源：先修正旧值 "drive"/"wiki" -> NULL，再回填
            cursor.execute("""
                UPDATE sync_metadata
                SET doc_type = NULL
                WHERE source = 'feishu' AND doc_type IN ('drive', 'wiki')
            """)
            cursor.execute("""
                UPDATE sync_metadata
                SET doc_type = CASE
                    WHEN url LIKE '%%/wiki/%%' THEN 'wiki'
                    WHEN url LIKE '%%/sheets/%%' THEN 'sheet'
                    WHEN url LIKE '%%/bitable/%%' THEN 'bitable'
                    WHEN url LIKE '%%/mindnote/%%' THEN 'mindnote'
                    WHEN url LIKE '%%/docx/%%' THEN 'docx'
                    WHEN url LIKE '%%/drive/%%' THEN 'docx'
                    ELSE 'docx'
                END
                WHERE source = 'feishu' AND (doc_type IS NULL OR doc_type = '')
            """)
            # 4) wps 源
            cursor.execute("""
                UPDATE sync_metadata
                SET doc_type = 'wps_doc'
                WHERE source = 'wps' AND (doc_type IS NULL OR doc_type = '')
            """)
            # 5) yinxiang 源
            cursor.execute("""
                UPDATE sync_metadata
                SET doc_type = 'note'
                WHERE source = 'yinxiang' AND (doc_type IS NULL OR doc_type = '')
            """)
            # 6) web 源（网页收藏）
            cursor.execute("""
                UPDATE sync_metadata
                SET doc_type = 'web_page', extension = 'html'
                WHERE source = 'web' AND (doc_type IS NULL OR doc_type = '')
            """)
            logger.info("doc_type 回填完成")
        except Exception as e:
            logger.warning(f"回填 doc_type 失败: {e}")

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
        ai_tags: str = None,
        doc_type: str = None,
        mime_type: str = None,
        extension: str = None
    ):
        """插入或更新文档同步状态"""
        now = datetime.now().timestamp()

        self._execute("""
            INSERT INTO sync_metadata
            (id, source, account, url, title, doc_type, mime_type, extension,
             content_hash, last_modified, last_synced, sync_status,
             file_size, file_mtime, ai_summary, ai_tags)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                source = VALUES(source),
                account = VALUES(account),
                url = VALUES(url),
                title = VALUES(title),
                doc_type = VALUES(doc_type),
                mime_type = VALUES(mime_type),
                extension = VALUES(extension),
                content_hash = VALUES(content_hash),
                last_modified = VALUES(last_modified),
                last_synced = VALUES(last_synced),
                sync_status = VALUES(sync_status),
                file_size = VALUES(file_size),
                file_mtime = VALUES(file_mtime),
                ai_summary = VALUES(ai_summary),
                ai_tags = VALUES(ai_tags)
        """, (
            doc_id, source, account, url, title, doc_type, mime_type, extension,
            content_hash, last_modified, now, "synced",
            file_size, file_mtime, ai_summary, ai_tags
        ))

    def mark_deleted(self, doc_id: str):
        """标记文档已删除"""
        self._execute(
            "UPDATE sync_metadata SET sync_status = 'deleted' WHERE id = %s",
            (doc_id,)
        )

    def update_file_info(self, doc_id: str, file_size: int, file_mtime: float):
        """更新文件大小和修改时间"""
        now = datetime.now().timestamp()
        self._execute(
            "UPDATE sync_metadata SET file_size = %s, file_mtime = %s, last_synced = %s WHERE id = %s",
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

        if source:
            query += " AND source = %s"
            params.append(source)

        if account:
            query += " AND account = %s"
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

        placeholders = ",".join(["%s"] * len(current_doc_ids))

        query = f"""
            SELECT id FROM sync_metadata
            WHERE sync_status = 'synced'
            AND id NOT IN ({placeholders})
        """
        params = list(current_doc_ids)

        if source:
            query += " AND source = %s"
            params.append(source)

        if account:
            query += " AND account = %s"
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
        doc_type: str = None,
        error: str = None
    ):
        """记录同步日志"""
        now = datetime.now().timestamp()

        self._execute("""
            INSERT INTO sync_logs
            (sync_time, source, account, action, doc_id, doc_title, doc_type, error_message)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (now, source, account, action, doc_id, doc_title, doc_type, error))

    def get_sync_stats(self, source: str = None, account: str = None) -> Dict:
        """获取同步统计信息"""
        query = "SELECT COUNT(*) as count FROM sync_metadata WHERE sync_status = 'synced'"
        params = []

        if source:
            query += " AND source = %s"
            params.append(source)

        if account:
            query += " AND account = %s"
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

    def get_doc_type_stats(self, source: str = None) -> Dict[str, int]:
        """获取按 doc_type 分组的统计信息"""
        query = """
            SELECT source, doc_type, COUNT(*) as count
            FROM sync_metadata
            WHERE sync_status = 'synced'
        """
        params = []

        if source:
            query += " AND source = %s"
            params.append(source)

        query += " GROUP BY source, doc_type"

        rows = self._execute(query, tuple(params), fetch_all=True) or []

        result = {}
        for row in rows:
            key = row['source']
            if key not in result:
                result[key] = {}
            result[key][row['doc_type'] or 'unknown'] = row['count']
        return result

    def get_docs_by_type(
        self,
        doc_type: str,
        source: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """按 doc_type 查询文档"""
        query = "SELECT * FROM sync_metadata WHERE sync_status = 'synced' AND doc_type = %s"
        params = [doc_type]

        if source:
            query += " AND source = %s"
            params.append(source)

        query += " ORDER BY last_modified DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        return self._execute(query, tuple(params), fetch_all=True) or []

    def get_doc_type(self, doc_id: str) -> Optional[str]:
        """获取指定文档的 doc_type"""
        row = self._execute(
            "SELECT doc_type FROM sync_metadata WHERE id = %s",
            (doc_id,),
            fetch_one=True
        )
        return row['doc_type'] if row else None


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
