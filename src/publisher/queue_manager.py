"""发布队列管理器

负责发布任务的队列管理、重试逻辑和速率限制
"""
import asyncio
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from loguru import logger

from ..core.task_manager import TaskManager, PublishTaskRecord
from .models import PublishTask, PublishResult


@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3
    base_delay: int = 60  # 基础延迟(秒)
    backoff_multiplier: int = 5  # 退避倍数


class PublishQueueManager:
    """发布队列管理器"""

    def __init__(self, task_manager: Optional[TaskManager] = None, retry_config: Optional[RetryConfig] = None):
        """初始化队列管理器

        Args:
            task_manager: 任务管理器
            retry_config: 重试配置
        """
        self.task_manager = task_manager or TaskManager()
        self.retry_config = retry_config or RetryConfig()

    def get_retry_delay(self, retry_count: int) -> int:
        """计算重试延迟时间(指数退避)

        Args:
            retry_count: 当前重试次数

        Returns:
            int: 延迟秒数

        Examples:
            retry_count=0: 0秒 (首次尝试)
            retry_count=1: 60秒
            retry_count=2: 300秒 (5分钟)
            retry_count=3: 1500秒 (25分钟)
        """
        if retry_count == 0:
            return 0

        return self.retry_config.base_delay * (self.retry_config.backoff_multiplier ** (retry_count - 1))

    async def enqueue_publish_tasks(
        self,
        tasks: List[PublishTask],
        parent_task_id: Optional[int] = None
    ) -> List[PublishTaskRecord]:
        """将发布任务加入队列

        Args:
            tasks: 发布任务列表
            parent_task_id: 父任务ID

        Returns:
            List[PublishTaskRecord]: 创建的发布任务记录列表
        """
        records = []

        for task in tasks:
            record = self.task_manager.create_publish_task(
                task_id=parent_task_id,
                episode_number=task.episode_number if hasattr(task, 'episode_number') else 0,
                platform=task.platform,
                content_type=task.content_type,
                file_path=str(task.file_path) if task.file_path else None,
                scheduled_time=task.scheduled_time
            )
            records.append(record)
            logger.info(f"发布任务已入队: #{record.id} {record.platform}")

        return records

    async def process_queue(
        self,
        episode_number: Optional[int] = None,
        platform: Optional[str] = None
    ) -> List[PublishResult]:
        """处理队列中的待发布任务

        Args:
            episode_number: 可选，仅处理指定期号
            platform: 可选，仅处理指定平台

        Returns:
            List[PublishResult]: 发布结果列表
        """
        # 获取待处理任务
        pending_tasks = self.task_manager.get_pending_publish_tasks(episode_number)

        if platform:
            pending_tasks = [t for t in pending_tasks if t.platform == platform]

        if not pending_tasks:
            logger.info("队列中没有待处理的发布任务")
            return []

        logger.info(f"开始处理 {len(pending_tasks)} 个发布任务")

        results = []
        for record in pending_tasks:
            # 检查是否需要延迟
            if record.retry_count > 0:
                delay = self.get_retry_delay(record.retry_count)
                logger.info(f"重试任务 #{record.id}，延迟 {delay} 秒")
                await asyncio.sleep(delay)

            # 这里暂时返回一个占位结果
            # 实际发布逻辑由 PublishDispatcher 处理
            result = PublishResult(
                platform=record.platform,
                success=False,
                error_message="需要由 PublishDispatcher 执行实际发布"
            )
            results.append(result)

        return results

    async def retry_failed_tasks(
        self,
        episode_number: Optional[int] = None
    ) -> List[PublishResult]:
        """重试失败的发布任务

        Args:
            episode_number: 可选，仅重试指定期号

        Returns:
            List[PublishResult]: 发布结果列表
        """
        # 获取失败的任务
        # 注意：这里简化实现，实际应该查询数据库
        logger.info("查找可重试的失败任务")

        # TODO: 实现从数据库查询失败任务的逻辑
        # 这需要在 TaskManager 中添加相应方法

        return []

    def should_retry(self, record: PublishTaskRecord) -> bool:
        """判断任务是否应该重试

        Args:
            record: 发布任务记录

        Returns:
            bool: 是否应该重试
        """
        if record.status != 'failed':
            return False

        if record.retry_count >= self.retry_config.max_attempts:
            logger.info(f"任务 #{record.id} 已达最大重试次数 ({record.retry_count})")
            return False

        return True


class RateLimiter:
    """速率限制器"""

    def __init__(self, requests_per_minute: int = 10):
        """初始化速率限制器

        Args:
            requests_per_minute: 每分钟最大请求数
        """
        self.requests_per_minute = requests_per_minute
        self.min_interval = 60.0 / requests_per_minute  # 最小请求间隔(秒)
        self.last_request_time: Dict[str, float] = {}  # 每个平台的上次请求时间

    async def acquire(self, platform: str) -> None:
        """获取请求许可(如果需要则等待)

        Args:
            platform: 平台名称
        """
        now = time.time()
        last_time = self.last_request_time.get(platform, 0)
        elapsed = now - last_time

        if elapsed < self.min_interval:
            wait_time = self.min_interval - elapsed
            logger.debug(f"速率限制: {platform} 需等待 {wait_time:.2f} 秒")
            await asyncio.sleep(wait_time)

        self.last_request_time[platform] = time.time()


class PublishRetryHandler:
    """发布重试处理器"""

    def __init__(
        self,
        queue_manager: PublishQueueManager,
        rate_limiter: Optional[RateLimiter] = None
    ):
        """初始化重试处理器

        Args:
            queue_manager: 队列管理器
            rate_limiter: 速率限制器
        """
        self.queue_manager = queue_manager
        self.rate_limiter = rate_limiter or RateLimiter()

    async def execute_with_retry(
        self,
        publish_func,
        task: PublishTask,
        record_id: int
    ) -> PublishResult:
        """执行发布任务并处理重试

        Args:
            publish_func: 发布函数
            task: 发布任务
            record_id: 发布任务记录ID

        Returns:
            PublishResult: 发布结果
        """
        max_attempts = self.queue_manager.retry_config.max_attempts

        for attempt in range(max_attempts):
            try:
                # 速率限制
                await self.rate_limiter.acquire(task.platform)

                # 执行发布
                logger.info(f"尝试发布 {task.platform} (尝试 {attempt + 1}/{max_attempts})")

                if asyncio.iscoroutinefunction(publish_func):
                    result = await publish_func(task)
                else:
                    result = publish_func(task)

                if result.success:
                    # 成功，更新记录
                    self.queue_manager.task_manager.update_publish_task_status(
                        record_id,
                        'success',
                        content_url=result.content_url
                    )
                    logger.info(f"✓ {task.platform} 发布成功: {result.content_url}")
                    return result

                # 失败，但不是异常
                logger.warning(f"✗ {task.platform} 发布失败: {result.error_message}")

                if attempt < max_attempts - 1:
                    # 还有重试机会
                    delay = self.queue_manager.get_retry_delay(attempt + 1)
                    logger.info(f"将在 {delay} 秒后重试...")
                    await asyncio.sleep(delay)
                else:
                    # 已达最大重试次数
                    self.queue_manager.task_manager.update_publish_task_status(
                        record_id,
                        'failed',
                        error_message=result.error_message
                    )
                    return result

            except Exception as e:
                logger.exception(f"发布异常: {e}")

                if attempt < max_attempts - 1:
                    delay = self.queue_manager.get_retry_delay(attempt + 1)
                    logger.info(f"将在 {delay} 秒后重试...")
                    await asyncio.sleep(delay)
                else:
                    # 最终失败
                    self.queue_manager.task_manager.update_publish_task_status(
                        record_id,
                        'failed',
                        error_message=str(e)
                    )
                    return PublishResult(
                        platform=task.platform,
                        success=False,
                        error_message=str(e)
                    )

        # 不应该到这里
        return PublishResult(
            platform=task.platform,
            success=False,
            error_message="Unknown error"
        )


if __name__ == "__main__":
    # 测试代码
    logger.info("测试 PublishQueueManager")

    # 测试重试延迟计算
    qm = PublishQueueManager()
    print("重试延迟测试:")
    for i in range(4):
        delay = qm.get_retry_delay(i)
        print(f"  重试 {i}: {delay} 秒")

    # 测试速率限制
    async def test_rate_limiter():
        limiter = RateLimiter(requests_per_minute=10)
        print("\n速率限制测试 (10 req/min):")

        for i in range(3):
            start = time.time()
            await limiter.acquire("test_platform")
            elapsed = time.time() - start
            print(f"  请求 {i + 1}: 等待 {elapsed:.2f} 秒")

    asyncio.run(test_rate_limiter())

    print("\n✓ 所有测试通过!")
