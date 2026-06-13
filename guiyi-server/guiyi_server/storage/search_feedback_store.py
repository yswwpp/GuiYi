"""
搜索反馈存储 - 使用 MySQL 持久化搜索反馈和结果快照

第一阶段：建立稳定的反馈数据采集闭环，不直接影响搜索结果。
"""

import json
import uuid
import logging
from datetime import datetime
from typing import List, Optional
import pymysql
from pymysql.cursors import DictCursor

from guiyi_server.sync.metadata import DatabaseConfig

logger = logging.getLogger(__name__)


# 后端硬限制
MAX_RESULTS_PER_FEEDBACK = 50      # 单次反馈最多保存的结果数
MAX_TEXT_PREVIEW_LENGTH = 1000     # 单条结果摘要最大字符数
MAX_REASON_TEXT_LENGTH = 2000      # reason_text 最大字符数
MAX_EXPECTED_RESULT_LENGTH = 2000  # expected_result 最大字符数


class SearchFeedbackStore:
    """搜索反馈存储管理"""

    def __init__(self):
        self.db_config = DatabaseConfig()
        self._init_db()
        logger.info("搜索反馈存储初始化完成: MySQL")

    def _get_connection(self):
        """获取数据库连接"""
        return pymysql.connect(**self.db_config.mysql_config)

    def _init_db(self):
        """初始化反馈相关表"""
        config = self.db_config.mysql_config.copy()
        db_name = config.pop('database')

        conn = pymysql.connect(**config)
        cursor = conn.cursor()

        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` DEFAULT CHARACTER SET utf8mb4")
        cursor.execute(f"USE `{db_name}`")

        # 主表：反馈主体
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_feedback (
                id VARCHAR(64) PRIMARY KEY,
                query_text TEXT NOT NULL,
                source VARCHAR(50) DEFAULT NULL,
                account VARCHAR(255) DEFAULT NULL,
                doc_type VARCHAR(50) DEFAULT NULL,
                limit_value INT DEFAULT 20,

                search_mode VARCHAR(20) NOT NULL,
                keyword_extraction_enabled TINYINT(1) DEFAULT 0,
                rerank_enabled TINYINT(1) DEFAULT 0,
                ai_enhanced TINYINT(1) DEFAULT 0,
                rerank_used TINYINT(1) DEFAULT 0,
                keywords_extracted TEXT,
                processing_time_ms DOUBLE DEFAULT NULL,

                rating VARCHAR(20) NOT NULL,
                reason_code VARCHAR(50) DEFAULT NULL,
                reason_text TEXT DEFAULT NULL,
                expected_result TEXT DEFAULT NULL,

                result_count INT DEFAULT 0,
                client_created_at DOUBLE DEFAULT NULL,
                created_at DOUBLE NOT NULL,

                INDEX idx_created_at (created_at),
                INDEX idx_rating (rating),
                INDEX idx_reason_code (reason_code),
                INDEX idx_search_mode (search_mode)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # 结果快照表
        # 注：受 MySQL 账号权限限制，不创建外键约束；通过 feedback_id 索引关联，应用层保证一致性。
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_feedback_results (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                feedback_id VARCHAR(64) NOT NULL,
                rank_index INT NOT NULL,

                doc_id VARCHAR(255) DEFAULT NULL,
                title TEXT DEFAULT NULL,
                url TEXT DEFAULT NULL,
                source VARCHAR(50) DEFAULT NULL,
                account VARCHAR(255) DEFAULT NULL,
                doc_type VARCHAR(50) DEFAULT NULL,
                extension VARCHAR(20) DEFAULT NULL,

                score DOUBLE DEFAULT NULL,
                rerank_score DOUBLE DEFAULT NULL,
                final_score DOUBLE DEFAULT NULL,
                text_preview TEXT DEFAULT NULL,

                created_at DOUBLE NOT NULL,

                INDEX idx_feedback_id (feedback_id),
                INDEX idx_doc_id (doc_id),
                INDEX idx_source (source)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        conn.commit()
        conn.close()
        logger.info(f"MySQL 搜索反馈表初始化完成: {db_name}")

    @staticmethod
    def _truncate(text: Optional[str], max_len: int) -> Optional[str]:
        """截断字符串到指定长度"""
        if text is None:
            return None
        if len(text) <= max_len:
            return text
        return text[:max_len]

    def create_feedback(self, payload: dict) -> str:
        """
        创建一条搜索反馈

        Args:
            payload: Pydantic 校验后的请求字典

        Returns:
            生成的 feedback_id
        """
        feedback_id = f"fb_{uuid.uuid4().hex[:16]}"
        now = datetime.now().timestamp()

        # 序列化 keywords_extracted 为 JSON 字符串（保留中文）
        keywords = payload.get('keywords_extracted') or []
        keywords_json = json.dumps(keywords, ensure_ascii=False)

        # 截断文本字段
        reason_text = self._truncate(payload.get('reason_text'), MAX_REASON_TEXT_LENGTH)
        expected_result = self._truncate(payload.get('expected_result'), MAX_EXPECTED_RESULT_LENGTH)

        # 限制结果数量
        results = payload.get('results') or []
        if len(results) > MAX_RESULTS_PER_FEEDBACK:
            logger.warning(
                f"反馈结果数量 {len(results)} 超限，截断为前 {MAX_RESULTS_PER_FEEDBACK} 条"
            )
            results = results[:MAX_RESULTS_PER_FEEDBACK]

        result_count = len(results)

        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # 写入主表
            cursor.execute("""
                INSERT INTO search_feedback (
                    id, query_text, source, account, doc_type, limit_value,
                    search_mode, keyword_extraction_enabled, rerank_enabled,
                    ai_enhanced, rerank_used, keywords_extracted, processing_time_ms,
                    rating, reason_code, reason_text, expected_result,
                    result_count, client_created_at, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s
                )
            """, (
                feedback_id,
                payload['query'],
                payload.get('source'),
                payload.get('account'),
                payload.get('doc_type'),
                payload.get('limit', 20),
                payload['search_mode'],
                1 if payload.get('keyword_extraction_enabled') else 0,
                1 if payload.get('rerank_enabled') else 0,
                1 if payload.get('ai_enhanced') else 0,
                1 if payload.get('rerank_used') else 0,
                keywords_json,
                payload.get('processing_time_ms'),
                payload['rating'],
                payload.get('reason_code'),
                reason_text,
                expected_result,
                result_count,
                payload.get('client_created_at'),
                now,
            ))

            # 写入结果表
            for rank_index, item in enumerate(results):
                text_preview = self._truncate(item.get('text'), MAX_TEXT_PREVIEW_LENGTH)
                cursor.execute("""
                    INSERT INTO search_feedback_results (
                        feedback_id, rank_index,
                        doc_id, title, url, source, account, doc_type, extension,
                        score, rerank_score, final_score, text_preview,
                        created_at
                    ) VALUES (
                        %s, %s,
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s
                    )
                """, (
                    feedback_id,
                    rank_index,
                    item.get('id'),
                    item.get('title'),
                    item.get('url'),
                    item.get('source'),
                    item.get('account'),
                    item.get('doc_type'),
                    item.get('extension'),
                    item.get('score'),
                    item.get('rerank_score'),
                    item.get('final_score'),
                    text_preview,
                    now,
                ))

            conn.commit()
            logger.info(f"搜索反馈已保存: id={feedback_id}, rating={payload['rating']}, results={result_count}")
            return feedback_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_feedback(self, feedback_id: str) -> Optional[dict]:
        """读取单条反馈（供后续分析使用）"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor(DictCursor)
            cursor.execute(
                "SELECT * FROM search_feedback WHERE id = %s",
                (feedback_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            feedback = dict(row)

            cursor.execute(
                "SELECT * FROM search_feedback_results WHERE feedback_id = %s ORDER BY rank_index",
                (feedback_id,)
            )
            feedback['results'] = [dict(r) for r in cursor.fetchall()]
            return feedback
        finally:
            conn.close()
