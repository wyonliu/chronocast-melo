"""任务管理系统

负责任务生命周期管理和状态持久化
"""
import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from loguru import logger


@dataclass
class Task:
    """任务数据模型"""
    id: Optional[int] = None
    task_type: str = ""  # 'generate', 'publish', 'collect', 'report'
    episode_number: Optional[int] = None
    status: str = "pending"  # 'pending', 'running', 'completed', 'failed'
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    config_json: Optional[str] = None
    result_json: Optional[str] = None

    @property
    def config(self) -> Dict[str, Any]:
        """解析配置 JSON"""
        if self.config_json:
            return json.loads(self.config_json)
        return {}

    @property
    def result(self) -> Dict[str, Any]:
        """解析结果 JSON"""
        if self.result_json:
            return json.loads(self.result_json)
        return {}


@dataclass
class PublishTaskRecord:
    """发布任务记录"""
    id: Optional[int] = None
    task_id: Optional[int] = None
    episode_number: int = 0
    platform: str = ""
    content_type: str = ""  # 'audio', 'video', 'clip', 'text'
    file_path: Optional[str] = None
    status: str = "pending"  # 'pending', 'uploading', 'success', 'failed'
    scheduled_time: Optional[str] = None
    published_at: Optional[str] = None
    content_url: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0


class TaskManager:
    """任务管理器"""

    def __init__(self, db_path: Optional[str] = None):
        """初始化任务管理器

        Args:
            db_path: 数据库路径,默认使用 data/analytics.db
        """
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / "data" / "analytics.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # 初始化数据库
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """初始化数据库表"""
        conn = self._get_connection()
        try:
            # 创建 tasks 表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type TEXT NOT NULL,
                    episode_number INTEGER,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    error_message TEXT,
                    config_json TEXT,
                    result_json TEXT
                )
            """)

            # 创建 publish_tasks 表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS publish_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER,
                    episode_number INTEGER NOT NULL,
                    platform TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    file_path TEXT,
                    status TEXT NOT NULL,
                    scheduled_time TEXT,
                    published_at TEXT,
                    content_url TEXT,
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                )
            """)

            # 创建索引
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_status
                ON tasks(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_episode
                ON tasks(episode_number)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_publish_tasks_status
                ON publish_tasks(status)
            """)

            conn.commit()
            logger.info("数据库表初始化完成")
        except Exception as e:
            conn.rollback()
            logger.error(f"数据库初始化失败: {e}")
            raise
        finally:
            conn.close()

    def create_task(
        self,
        task_type: str,
        config: Optional[Dict[str, Any]] = None,
        episode_number: Optional[int] = None
    ) -> Task:
        """创建新任务

        Args:
            task_type: 任务类型
            config: 任务配置
            episode_number: 期号

        Returns:
            Task: 创建的任务对象
        """
        task = Task(
            task_type=task_type,
            episode_number=episode_number,
            config_json=json.dumps(config) if config else None
        )

        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                INSERT INTO tasks (
                    task_type, episode_number, status, created_at,
                    config_json, max_retries
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                task.task_type,
                task.episode_number,
                task.status,
                task.created_at,
                task.config_json,
                task.max_retries
            ))

            task.id = cursor.lastrowid
            conn.commit()

            logger.info(f"创建任务 #{task.id}: {task.task_type} (episode={task.episode_number})")
            return task

        except Exception as e:
            conn.rollback()
            logger.error(f"创建任务失败: {e}")
            raise
        finally:
            conn.close()

    def get_task(self, task_id: int) -> Optional[Task]:
        """获取任务

        Args:
            task_id: 任务ID

        Returns:
            Optional[Task]: 任务对象,不存在返回 None
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                SELECT * FROM tasks WHERE id = ?
            """, (task_id,))

            row = cursor.fetchone()
            if row:
                return Task(**dict(row))
            return None

        finally:
            conn.close()

    def update_task_status(
        self,
        task_id: int,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> None:
        """更新任务状态

        Args:
            task_id: 任务ID
            status: 新状态
            result: 结果数据
            error_message: 错误信息
        """
        conn = self._get_connection()
        try:
            now = datetime.now().isoformat()

            # 构建更新语句
            updates = ["status = ?"]
            params = [status]

            if status == "running":
                updates.append("started_at = ?")
                params.append(now)
            elif status in ("completed", "failed"):
                updates.append("completed_at = ?")
                params.append(now)

            if result:
                updates.append("result_json = ?")
                params.append(json.dumps(result))

            if error_message:
                updates.append("error_message = ?")
                params.append(error_message)

            params.append(task_id)

            conn.execute(f"""
                UPDATE tasks
                SET {', '.join(updates)}
                WHERE id = ?
            """, params)

            conn.commit()
            logger.info(f"更新任务 #{task_id} 状态: {status}")

        except Exception as e:
            conn.rollback()
            logger.error(f"更新任务状态失败: {e}")
            raise
        finally:
            conn.close()

    def increment_retry_count(self, task_id: int) -> int:
        """增加重试计数

        Args:
            task_id: 任务ID

        Returns:
            int: 新的重试计数
        """
        conn = self._get_connection()
        try:
            conn.execute("""
                UPDATE tasks
                SET retry_count = retry_count + 1
                WHERE id = ?
            """, (task_id,))
            conn.commit()

            # 获取新的计数
            cursor = conn.execute("""
                SELECT retry_count FROM tasks WHERE id = ?
            """, (task_id,))
            row = cursor.fetchone()
            return row['retry_count'] if row else 0

        finally:
            conn.close()

    def get_failed_tasks(self, task_type: Optional[str] = None) -> List[Task]:
        """获取失败的任务列表

        Args:
            task_type: 可选,过滤任务类型

        Returns:
            List[Task]: 失败任务列表
        """
        conn = self._get_connection()
        try:
            query = """
                SELECT * FROM tasks
                WHERE status = 'failed' AND retry_count < max_retries
            """
            params = []

            if task_type:
                query += " AND task_type = ?"
                params.append(task_type)

            query += " ORDER BY created_at ASC"

            cursor = conn.execute(query, params)
            return [Task(**dict(row)) for row in cursor.fetchall()]

        finally:
            conn.close()

    def get_pending_tasks(self, task_type: Optional[str] = None) -> List[Task]:
        """获取待处理任务

        Args:
            task_type: 可选,过滤任务类型

        Returns:
            List[Task]: 待处理任务列表
        """
        conn = self._get_connection()
        try:
            query = "SELECT * FROM tasks WHERE status = 'pending'"
            params = []

            if task_type:
                query += " AND task_type = ?"
                params.append(task_type)

            query += " ORDER BY created_at ASC"

            cursor = conn.execute(query, params)
            return [Task(**dict(row)) for row in cursor.fetchall()]

        finally:
            conn.close()

    def get_latest_episode_number(self) -> int:
        """获取最新的期号

        Returns:
            int: 最新期号,如果没有任务返回 0
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                SELECT MAX(episode_number) as max_ep FROM tasks
                WHERE episode_number IS NOT NULL
            """)
            row = cursor.fetchone()
            return row['max_ep'] or 0
        finally:
            conn.close()

    def cleanup_old_tasks(self, days: int = 90) -> int:
        """清理旧任务

        Args:
            days: 保留天数

        Returns:
            int: 删除的任务数
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                DELETE FROM tasks
                WHERE datetime(created_at) < datetime('now', '-' || ? || ' days')
                AND status IN ('completed', 'failed')
            """, (days,))

            deleted = cursor.rowcount
            conn.commit()

            logger.info(f"清理了 {deleted} 个旧任务 (>{days}天)")
            return deleted

        finally:
            conn.close()

    # ==================== Publish Task 管理 ====================

    def create_publish_task(
        self,
        task_id: Optional[int],
        episode_number: int,
        platform: str,
        content_type: str,
        file_path: Optional[str] = None,
        scheduled_time: Optional[str] = None
    ) -> PublishTaskRecord:
        """创建发布任务记录

        Args:
            task_id: 关联的主任务ID
            episode_number: 期号
            platform: 平台名称
            content_type: 内容类型
            file_path: 文件路径
            scheduled_time: 计划发布时间

        Returns:
            PublishTaskRecord: 发布任务记录
        """
        record = PublishTaskRecord(
            task_id=task_id,
            episode_number=episode_number,
            platform=platform,
            content_type=content_type,
            file_path=file_path,
            scheduled_time=scheduled_time
        )

        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                INSERT INTO publish_tasks (
                    task_id, episode_number, platform, content_type,
                    file_path, status, scheduled_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                record.task_id,
                record.episode_number,
                record.platform,
                record.content_type,
                record.file_path,
                record.status,
                record.scheduled_time
            ))

            record.id = cursor.lastrowid
            conn.commit()

            logger.info(f"创建发布任务 #{record.id}: {platform} (episode={episode_number})")
            return record

        except Exception as e:
            conn.rollback()
            logger.error(f"创建发布任务失败: {e}")
            raise
        finally:
            conn.close()

    def update_publish_task_status(
        self,
        publish_task_id: int,
        status: str,
        content_url: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        """更新发布任务状态

        Args:
            publish_task_id: 发布任务ID
            status: 新状态
            content_url: 内容URL
            error_message: 错误信息
        """
        conn = self._get_connection()
        try:
            updates = ["status = ?"]
            params = [status]

            if status == "success":
                updates.append("published_at = ?")
                params.append(datetime.now().isoformat())

            if content_url:
                updates.append("content_url = ?")
                params.append(content_url)

            if error_message:
                updates.append("error_message = ?")
                params.append(error_message)

            if status == "failed":
                updates.append("retry_count = retry_count + 1")

            params.append(publish_task_id)

            conn.execute(f"""
                UPDATE publish_tasks
                SET {', '.join(updates)}
                WHERE id = ?
            """, params)

            conn.commit()
            logger.info(f"更新发布任务 #{publish_task_id} 状态: {status}")

        except Exception as e:
            conn.rollback()
            logger.error(f"更新发布任务状态失败: {e}")
            raise
        finally:
            conn.close()

    def get_pending_publish_tasks(self, episode_number: Optional[int] = None) -> List[PublishTaskRecord]:
        """获取待发布任务

        Args:
            episode_number: 可选,过滤期号

        Returns:
            List[PublishTaskRecord]: 待发布任务列表
        """
        conn = self._get_connection()
        try:
            query = """
                SELECT * FROM publish_tasks
                WHERE status = 'pending'
                AND (scheduled_time IS NULL OR datetime(scheduled_time) <= datetime('now'))
            """
            params = []

            if episode_number:
                query += " AND episode_number = ?"
                params.append(episode_number)

            query += " ORDER BY scheduled_time ASC, id ASC"

            cursor = conn.execute(query, params)
            return [PublishTaskRecord(**dict(row)) for row in cursor.fetchall()]

        finally:
            conn.close()


if __name__ == "__main__":
    # 测试代码
    logger.info("测试 TaskManager")

    tm = TaskManager()

    # 测试创建任务
    task = tm.create_task(
        "test",
        {"message": "Hello ChronoCast"},
        episode_number=1
    )
    print(f"✓ 创建任务: #{task.id}")

    # 测试更新状态
    tm.update_task_status(task.id, "running")
    print(f"✓ 更新状态: running")

    tm.update_task_status(task.id, "completed", {"output": "Success"})
    print(f"✓ 更新状态: completed")

    # 测试查询
    retrieved = tm.get_task(task.id)
    print(f"✓ 查询任务: {retrieved.status}, result={retrieved.result}")

    # 测试获取最新期号
    latest_ep = tm.get_latest_episode_number()
    print(f"✓ 最新期号: {latest_ep}")

    print("\n所有测试通过!")
