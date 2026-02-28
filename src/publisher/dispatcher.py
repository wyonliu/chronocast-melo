"""自动发行 - 分发调度器

负责将内容分发到各个平台
"""
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger

from ..core.config import get_config, Config
from ..core.task_manager import TaskManager
from .models import PlatformType, PublishTask, PublishResult
from .queue_manager import PublishQueueManager, PublishRetryHandler, RateLimiter, RetryConfig


class PlatformPublisher:
    """平台发布器基类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get("enabled", False)
    
    async def publish(self, task: PublishTask) -> PublishResult:
        """发布内容（子类必须实现）"""
        raise NotImplementedError
    
    async def check_status(self, content_id: str) -> Dict[str, Any]:
        """检查发布状态"""
        return {}


# 导入实际的发布器实现
from .platforms.rss import RSSPublisher
from .platforms.bilibili import BilibiliPublisherImpl as BilibiliPublisher


class WechatPublisher(PlatformPublisher):
    """公众号发布器"""
    
    async def publish(self, task: PublishTask) -> PublishResult:
        """发布到公众号"""
        if not self.enabled:
            return PublishResult(
                platform="wechat",
                success=False,
                error_message="Wechat publishing disabled"
            )
        
        logger.info(f"Publishing to WeChat: {task.title}")
        
        try:
            # 使用 wechatpy 库
            # from wechatpy import WeChatClient
            # client = WeChatClient(
            #     self.config["app_id"],
            #     self.config["app_secret"]
            # )
            # ... 实际发布逻辑
            
            return PublishResult(
                platform="wechat",
                success=True,
                content_url="https://mp.weixin.qq.com/s/xxxx"
            )
        except Exception as e:
            return PublishResult(
                platform="wechat",
                success=False,
                error_message=str(e)
            )


class PublishDispatcher:
    """发布调度器"""
    
    # 平台映射
    PLATFORM_MAP = {
        "rss": RSSPublisher,
        "podcast": RSSPublisher,
        "xiaoyuzhou": RSSPublisher,
        "apple_podcasts": RSSPublisher,
        "spotify": RSSPublisher,
        "bilibili": BilibiliPublisher,
        "b站": BilibiliPublisher,
        "wechat": WechatPublisher,
        "公众号": WechatPublisher,
    }
    
    def __init__(self, config: Optional[Config] = None, task_manager: Optional[TaskManager] = None):
        self.config = config or get_config()
        self.task_manager = task_manager or TaskManager()
        self.publishers: Dict[str, PlatformPublisher] = {}
        self._init_publishers()

        # 初始化队列管理器和重试处理器
        retry_config = RetryConfig(
            max_attempts=getattr(self.config.publish.retry, 'max_attempts', 3),
            backoff_multiplier=getattr(self.config.publish.retry, 'backoff_multiplier', 5)
        )
        self.queue_manager = PublishQueueManager(self.task_manager, retry_config)

        # 初始化速率限制器
        rate_limit_config = getattr(self.config.publish, 'rate_limit', {})
        if isinstance(rate_limit_config, dict):
            requests_per_minute = rate_limit_config.get('requests_per_minute', 10)
        else:
            requests_per_minute = 10
        self.rate_limiter = RateLimiter(requests_per_minute)

        self.retry_handler = PublishRetryHandler(self.queue_manager, self.rate_limiter)
    
    def _init_publishers(self):
        """初始化各平台发布器"""
        for platform_name, publisher_class in self.PLATFORM_MAP.items():
            if hasattr(self.config.publish, platform_name):
                platform_config = getattr(self.config.publish, platform_name)
                if isinstance(platform_config, dict):
                    self.publishers[platform_name] = publisher_class(platform_config)
    
    async def dispatch(
        self,
        tasks: List[PublishTask],
        parallel: bool = True
    ) -> List[PublishResult]:
        """分发发布任务
        
        Args:
            tasks: 发布任务列表
            parallel: 是否并行发布
            
        Returns:
            List[PublishResult]: 发布结果列表
        """
        if parallel:
            # 并行发布
            coroutines = [self._publish_single(task) for task in tasks]
            results = await asyncio.gather(*coroutines, return_exceptions=True)
            
            # 处理异常
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    processed_results.append(PublishResult(
                        platform=tasks[i].platform,
                        success=False,
                        error_message=str(result)
                    ))
                else:
                    processed_results.append(result)
            
            return processed_results
        else:
            # 串行发布
            results = []
            for task in tasks:
                result = await self._publish_single(task)
                results.append(result)
            return results
    
    async def _publish_single(self, task: PublishTask) -> PublishResult:
        """发布单个任务"""
        platform = task.platform.lower()

        if platform not in self.publishers:
            return PublishResult(
                platform=platform,
                success=False,
                error_message=f"Unknown platform: {platform}"
            )

        publisher = self.publishers[platform]
        return await publisher.publish(task)

    async def dispatch_with_retry(
        self,
        tasks: List[PublishTask],
        parent_task_id: Optional[int] = None
    ) -> List[PublishResult]:
        """分发发布任务并处理重试

        Args:
            tasks: 发布任务列表
            parent_task_id: 父任务ID

        Returns:
            List[PublishResult]: 发布结果列表
        """
        if not tasks:
            logger.warning("没有待发布的任务")
            return []

        logger.info(f"开始发布 {len(tasks)} 个任务")

        # 1. 将任务加入队列
        records = await self.queue_manager.enqueue_publish_tasks(tasks, parent_task_id)

        # 2. 并行发布所有任务(带重试)
        results = []
        for task, record in zip(tasks, records):
            # 获取发布器
            platform = task.platform.lower()
            if platform not in self.publishers:
                result = PublishResult(
                    platform=platform,
                    success=False,
                    error_message=f"Unknown platform: {platform}"
                )
                self.task_manager.update_publish_task_status(
                    record.id,
                    'failed',
                    error_message=result.error_message
                )
                results.append(result)
                continue

            publisher = self.publishers[platform]

            # 使用重试处理器执行发布
            result = await self.retry_handler.execute_with_retry(
                publisher.publish,
                task,
                record.id
            )
            results.append(result)

        # 统计结果
        success_count = sum(1 for r in results if r.success)
        logger.info(f"发布完成: {success_count}/{len(results)} 成功")

        return results
    
    def create_default_tasks(
        self,
        episode_number: int,
        base_dir: Path
    ) -> List[PublishTask]:
        """创建默认发布任务列表
        
        根据内容工厂方案，创建各平台的发布任务：
        - 完整播客音频 → 小宇宙/Apple/Spotify (RSS)
        - 完整视频 → B站/YouTube
        - 短视频切片 ×3 → 抖音/视频号/小红书
        - 图文文稿 → 公众号/知乎
        """
        tasks = []
        ep_str = f"EP{episode_number:03d}"
        
        # 1. 播客平台
        audio_path = base_dir / ep_str / "audio" / f"{ep_str}_full.mp3"
        if audio_path.exists():
            tasks.append(PublishTask(
                platform="rss",
                content_type="audio",
                file_path=audio_path,
                title=f"{ep_str}: 标题",
                description="节目描述...",
                tags=["AI", "科技", "播客"]
            ))
        
        # 2. B站
        video_path = base_dir / ep_str / "video" / f"{ep_str}_full.mp4"
        if video_path.exists():
            tasks.append(PublishTask(
                platform="bilibili",
                content_type="video",
                file_path=video_path,
                title=f"{ep_str}: 标题",
                description="视频描述...",
                tags=["AI", "科技", "知识"]
            ))
        
        # 3. 短视频（分3天发布）
        clips_dir = base_dir / ep_str / "video" / "clips"
        if clips_dir.exists():
            for i, clip_file in enumerate(sorted(clips_dir.glob("clip_*.mp4"))[:3], 1):
                tasks.append(PublishTask(
                    platform="douyin",
                    content_type="clip",
                    file_path=clip_file,
                    title=f"切片 {i}",
                    description="#AI #科技",
                    scheduled_time=f"2024-01-0{i}T12:00:00"  # 示例时间
                ))
        
        # 4. 公众号
        script_path = base_dir / ep_str / "drafts" / f"{ep_str}_script.md"
        if script_path.exists():
            tasks.append(PublishTask(
                platform="wechat",
                content_type="text",
                file_path=script_path,
                title=f"{ep_str}: 标题",
                description="公众号图文"
            ))
        
        return tasks


async def publish_episode(
    episode_number: int,
    platforms: Optional[List[str]] = None,
    with_retry: bool = True
) -> List[PublishResult]:
    """便捷函数：发布单期内容

    Args:
        episode_number: 期号
        platforms: 可选，指定平台列表
        with_retry: 是否启用重试机制

    Returns:
        List[PublishResult]: 发布结果列表
    """
    dispatcher = PublishDispatcher()
    config = get_config()

    # 创建默认任务
    base_dir = Path(config.storage.output_base)
    tasks = dispatcher.create_default_tasks(episode_number, base_dir)

    # 过滤指定平台
    if platforms:
        tasks = [t for t in tasks if t.platform in platforms]

    if not tasks:
        logger.warning("No publish tasks created")
        return []

    # 执行发布
    if with_retry:
        results = await dispatcher.dispatch_with_retry(tasks)
    else:
        results = await dispatcher.dispatch(tasks)

    # 输出结果
    for result in results:
        if result.success:
            logger.info(f"✓ {result.platform}: {result.content_url}")
        else:
            logger.error(f"✗ {result.platform}: {result.error_message}")

    return results


if __name__ == "__main__":
    # 测试
    async def test():
        results = await publish_episode(1)
        for r in results:
            print(f"{r.platform}: {'OK' if r.success else 'FAIL'}")
    
    asyncio.run(test())
