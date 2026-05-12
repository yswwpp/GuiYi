"""
同步任务调度器 - 定时自动同步
支持任务配置持久化
"""

import os
import json
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Dict, Callable, Optional
import logging

logger = logging.getLogger(__name__)


class SyncScheduler:
    """同步任务调度器"""

    def __init__(self, config_path: str = None):
        self.scheduler = BackgroundScheduler()
        self.sync_jobs: Dict[str, str] = {}  # job_id -> source_name

        # 配置文件路径
        if config_path is None:
            data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
            os.makedirs(data_dir, exist_ok=True)
            config_path = os.path.join(data_dir, 'scheduler_jobs.json')
        self.config_path = config_path

        # 加载已保存的任务配置
        self.saved_jobs: Dict[str, dict] = self._load_jobs()

    def _load_jobs(self) -> Dict[str, dict]:
        """加载已保存的任务配置"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    jobs = json.load(f)
                logger.info(f"加载定时任务配置: {len(jobs)} 个任务")
                return jobs
            except Exception as e:
                logger.warning(f"加载定时任务配置失败: {e}")
        return {}

    def _save_jobs(self):
        """保存任务配置"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.saved_jobs, f, ensure_ascii=False, indent=2)
            logger.debug(f"保存定时任务配置: {len(self.saved_jobs)} 个任务")
        except Exception as e:
            logger.error(f"保存定时任务配置失败: {e}")

    def start(self):
        """启动调度器"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("同步调度器已启动")

    def stop(self):
        """停止调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("同步调度器已停止")

    def add_sync_job(
        self,
        source: str,
        sync_func: Callable,
        account: str = None,
        cron_expression: str = None,
        interval_hours: int = None,
        persist: bool = True
    ) -> str:
        """
        添加同步任务

        Args:
            source: 数据源名称
            sync_func: 同步函数
            account: 账号标识（可选）
            cron_expression: Cron 表达式（如 "0 9 * * *" 表示每天 9:00）
            interval_hours: 间隔小时数（如果指定，则忽略 cron_expression）
            persist: 是否持久化保存

        Returns:
            任务 ID
        """
        job_id = f"sync_{source}_{account or 'default'}"

        # 如果任务已存在，先删除
        if job_id in self.sync_jobs:
            self.remove_sync_job(job_id, persist=False)

        # 确定触发器
        trigger_instance = None
        if interval_hours:
            from apscheduler.triggers.interval import IntervalTrigger
            trigger_instance = IntervalTrigger(hours=interval_hours)
        elif cron_expression:
            trigger_instance = CronTrigger.from_crontab(cron_expression)
        else:
            # 默认：每天早上 9 点
            trigger_instance = CronTrigger(hour=9, minute=0)
            cron_expression = "0 9 * * *"

        # 添加任务
        job = self.scheduler.add_job(
            func=sync_func,
            trigger=trigger_instance,
            id=job_id,
            name=f"{source} ({account or 'default'}) 同步",
            kwargs={"source": source, "account": account},
            misfire_grace_time=3600,  # 容忍 1 小时延迟
            coalesce=True             # 错过多次时只执行一次
        )

        self.sync_jobs[job_id] = source

        # 持久化保存
        if persist:
            self.saved_jobs[job_id] = {
                "source": source,
                "account": account,
                "cron_expression": cron_expression,
                "interval_hours": interval_hours
            }
            self._save_jobs()

        logger.info(f"添加同步任务: {job.id}")
        return job_id

    def remove_sync_job(self, job_id: str, persist: bool = True) -> bool:
        """
        移除同步任务

        Args:
            job_id: 任务 ID
            persist: 是否从持久化存储中删除

        Returns:
            是否移除成功
        """
        try:
            self.scheduler.remove_job(job_id)
            if job_id in self.sync_jobs:
                del self.sync_jobs[job_id]

            # 从持久化存储中删除
            if persist and job_id in self.saved_jobs:
                del self.saved_jobs[job_id]
                self._save_jobs()

            logger.info(f"移除同步任务: {job_id}")
            return True
        except Exception as e:
            logger.error(f"移除同步任务失败 [{job_id}]: {e}")
            return False

    def update_sync_job(
        self,
        job_id: str,
        sync_func: Callable,
        cron_expression: str = None,
        interval_hours: int = None
    ) -> bool:
        """
        更新同步任务

        Args:
            job_id: 任务 ID
            sync_func: 同步函数
            cron_expression: 新的 Cron 表达式
            interval_hours: 新的间隔小时数

        Returns:
            是否更新成功
        """
        if job_id not in self.saved_jobs:
            logger.warning(f"任务不存在: {job_id}")
            return False

        job_config = self.saved_jobs[job_id]
        source = job_config["source"]
        account = job_config.get("account")

        # 先删除再添加
        self.remove_sync_job(job_id, persist=False)
        self.add_sync_job(
            source=source,
            sync_func=sync_func,
            account=account,
            cron_expression=cron_expression,
            interval_hours=interval_hours,
            persist=True
        )

        logger.info(f"更新同步任务: {job_id}")
        return True

    def restore_jobs(self, sync_func: Callable):
        """
        恢复已保存的任务

        Args:
            sync_func: 同步函数
        """
        for job_id, job_config in self.saved_jobs.items():
            try:
                source = job_config["source"]
                account = job_config.get("account")
                cron_expression = job_config.get("cron_expression")
                interval_hours = job_config.get("interval_hours")

                # 检查任务是否已存在
                if job_id in self.sync_jobs:
                    continue

                # 确定触发器
                trigger_instance = None
                if interval_hours:
                    from apscheduler.triggers.interval import IntervalTrigger
                    trigger_instance = IntervalTrigger(hours=interval_hours)
                elif cron_expression:
                    trigger_instance = CronTrigger.from_crontab(cron_expression)
                else:
                    trigger_instance = CronTrigger(hour=9, minute=0)

                # 添加任务
                self.scheduler.add_job(
                    func=sync_func,
                    trigger=trigger_instance,
                    id=job_id,
                    name=f"{source} ({account or 'default'}) 同步",
                    kwargs={"source": source, "account": account},
                    misfire_grace_time=3600,  # 容忍 1 小时延迟
                    coalesce=True             # 错过多次时只执行一次
                )
                self.sync_jobs[job_id] = source
                logger.info(f"恢复同步任务: {job_id}")

            except Exception as e:
                logger.error(f"恢复同步任务失败 [{job_id}]: {e}")

        logger.info(f"已恢复 {len(self.sync_jobs)} 个同步任务")

    def trigger_sync_now(self, source: str, account: str = None):
        """
        立即触发同步

        Args:
            source: 数据源名称
            account: 账号标识（可选）
        """
        job_id = f"sync_{source}_{account or 'default'}"

        try:
            job = self.scheduler.get_job(job_id)
            if job:
                job.modify(next_run_time=None)  # 立即执行
                logger.info(f"立即触发同步: {job_id}")
            else:
                logger.warning(f"任务不存在: {job_id}")
        except Exception as e:
            logger.error(f"触发同步失败 [{job_id}]: {e}")

    def get_jobs_info(self) -> list:
        """
        获取所有任务信息

        Returns:
            任务信息列表
        """
        jobs_info = []

        for job in self.scheduler.get_jobs():
            job_info = {
                "id": job.id,
                "name": job.name,
                "trigger": str(job.trigger)
            }

            # next_run_time may not be available until scheduler starts
            if hasattr(job, 'next_run_time') and job.next_run_time:
                job_info["next_run_time"] = job.next_run_time.isoformat()
            else:
                job_info["next_run_time"] = None

            # 从保存的配置中获取 cron 表达式
            if job.id in self.saved_jobs:
                job_info["cron_expression"] = self.saved_jobs[job.id].get("cron_expression")
                job_info["interval_hours"] = self.saved_jobs[job.id].get("interval_hours")

            jobs_info.append(job_info)

        return jobs_info

    def setup_default_jobs(self, sync_func: Callable):
        """
        设置默认同步任务（仅在无已保存任务时使用）

        Args:
            sync_func: 同步函数
        """
        # 如果已有保存的任务，恢复它们
        if self.saved_jobs:
            self.restore_jobs(sync_func)
            return

        # 否则设置默认任务
        logger.info("设置默认同步任务...")

        # 飞书：每天早上 9 点同步
        self.add_sync_job(
            source="feishu",
            sync_func=sync_func,
            cron_expression="0 9 * * *"
        )

        # 印象笔记：每天中午 12 点同步
        self.add_sync_job(
            source="yinxiang",
            sync_func=sync_func,
            cron_expression="0 12 * * *"
        )

        # 夸克网盘：每周一早上 8 点同步
        self.add_sync_job(
            source="quark",
            sync_func=sync_func,
            cron_expression="0 8 * * 1"
        )

        logger.info("默认同步任务已设置")
