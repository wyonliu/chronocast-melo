"""内容编排调度器

负责自动化调度和任务编排
"""
import asyncio
import schedule
import time
import signal
import sys
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime
from loguru import logger

from .config import get_config
from .task_manager import TaskManager
from .pipeline import ContentPipeline, PipelineResult
from .topic_generator import TopicGenerator
from ..writer.generator import EpisodeInput
from ..publisher.dispatcher import PublishDispatcher, PublishTask
from ..notification.notifier import NotificationService


@dataclass
class TaskResult:
    """任务执行结果"""
    success: bool
    task_id: Optional[int] = None
    episode_number: Optional[int] = None
    error: Optional[str] = None
    pipeline_result: Optional[PipelineResult] = None
    publish_results: Optional[List] = None


class ContentOrchestrator:
    """内容编排调度器"""

    def __init__(self):
        """初始化调度器"""
        self.config = get_config()
        self.task_manager = TaskManager()
        self.pipeline = ContentPipeline(self.config)
        self.dispatcher = PublishDispatcher(self.config)
        self.notifier = NotificationService(self.config)
        self.topic_generator = TopicGenerator(self.config)

        self.running = False
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """设置信号处理器,用于优雅退出"""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"收到信号 {signum},准备退出...")
        self.running = False

    def start_scheduler(self, daemon: bool = False) -> None:
        """启动调度器

        Args:
            daemon: 是否作为守护进程运行
        """
        logger.info("启动 ChronoCast 调度器")
        logger.info(f"模式: {'守护进程' if daemon else '前台运行'}")

        # 加载配置
        config = self.config

        # 注册定时任务
        if hasattr(config, 'scheduler') and config.scheduler.get('enabled', False):
            scheduler_config = config.scheduler

            # 每周一期内容生成
            if scheduler_config.get('weekly_episode', {}).get('enabled', False):
                cron = scheduler_config['weekly_episode'].get('cron', '0 6 * * 1')
                time_str = self._parse_cron_time(cron)
                if time_str:
                    schedule.every().monday.at(time_str).do(
                        lambda: asyncio.run(self.run_weekly_episode())
                    )
                    logger.info(f"已注册: 每周一期内容生成 (每周一 {time_str})")

            # 每日数据收集
            if scheduler_config.get('data_collection', {}).get('enabled', False):
                cron = scheduler_config['data_collection'].get('cron', '0 8 * * *')
                time_str = self._parse_cron_time(cron)
                if time_str:
                    schedule.every().day.at(time_str).do(
                        lambda: asyncio.run(self.collect_analytics())
                    )
                    logger.info(f"已注册: 每日数据收集 (每天 {time_str})")

            # 每周报告
            if scheduler_config.get('weekly_report', {}).get('enabled', False):
                cron = scheduler_config['weekly_report'].get('cron', '0 9 * * 1')
                time_str = self._parse_cron_time(cron)
                if time_str:
                    schedule.every().monday.at(time_str).do(
                        lambda: asyncio.run(self.generate_weekly_report())
                    )
                    logger.info(f"已注册: 每周报告生成 (每周一 {time_str})")

        else:
            logger.warning("调度器未启用,请检查配置文件")

        # 显示所有注册的任务
        jobs = schedule.get_jobs()
        logger.info(f"共注册 {len(jobs)} 个定时任务")

        # 主循环
        self.running = True
        logger.info("调度器已启动,等待任务触发...")

        try:
            while self.running:
                schedule.run_pending()
                time.sleep(60)  # 每分钟检查一次
        except KeyboardInterrupt:
            logger.info("收到中断信号,停止调度器")
        finally:
            logger.info("调度器已停止")

    def _parse_cron_time(self, cron: str) -> Optional[str]:
        """解析 cron 表达式获取时间

        仅支持简单格式: "0 6 * * 1" -> "06:00"

        Args:
            cron: cron 表达式

        Returns:
            Optional[str]: 时间字符串 HH:MM,解析失败返回 None
        """
        try:
            parts = cron.split()
            if len(parts) >= 2:
                minute = parts[0]
                hour = parts[1]
                return f"{int(hour):02d}:{int(minute):02d}"
        except:
            pass
        return None

    async def run_weekly_episode(self) -> TaskResult:
        """执行每周内容生成和发布"""
        logger.info("=== 开始每周内容生成任务 ===")

        # 获取下一个期号
        episode_number = self.task_manager.get_latest_episode_number() + 1
        logger.info(f"期号: EP{episode_number:03d}")

        # 创建任务记录
        task = self.task_manager.create_task(
            'generate',
            {'auto_generated': True},
            episode_number=episode_number
        )

        try:
            # 读取输入 (支持自动选题)
            scheduler_config = self.config.scheduler.get('weekly_episode', {})
            auto_topic = scheduler_config.get('auto_topic', False)

            if auto_topic:
                # 使用 AI 自动生成主题
                logger.info("使用 AI 自动生成节目主题...")
                input_data = await self.topic_generator.generate_from_trends()
                logger.info(f"✓ 自动生成主题: {input_data.theme}")
            else:
                # 从文件读取
                input_file = scheduler_config.get('input_file', 'input/weekly_topic.txt')
                input_path = Path(input_file)

                if not input_path.exists():
                    raise FileNotFoundError(f"输入文件不存在: {input_file}")

                input_text = input_path.read_text(encoding='utf-8')
                input_data = EpisodeInput.from_text(input_text)
                logger.info(f"主题: {input_data.theme}")

            # 更新任务状态为运行中
            self.task_manager.update_task_status(task.id, 'running')

            # 运行内容流水线
            logger.info("运行内容流水线...")
            pipeline_result = await self.pipeline.run(
                input_data,
                episode_number,
                mode='auto'
            )

            if not pipeline_result.success:
                raise Exception(f"流水线执行失败: {pipeline_result.errors}")

            logger.info("✓ 内容生成完成")

            # 自动发布
            publish_results = []
            if scheduler_config.get('auto_publish', True):
                logger.info("开始自动发布...")

                # 创建发布任务
                base_dir = Path(self.config.storage.output_base)
                publish_tasks = self.dispatcher.create_default_tasks(
                    episode_number,
                    base_dir
                )

                # 过滤启用的平台
                enabled_platforms = scheduler_config.get('platforms', ['rss'])
                publish_tasks = [
                    t for t in publish_tasks
                    if t.platform in enabled_platforms
                ]

                if publish_tasks:
                    # 并行发布
                    publish_results = await self.dispatcher.dispatch(
                        publish_tasks,
                        parallel=True
                    )

                    # 统计结果
                    success_count = sum(1 for r in publish_results if r.success)
                    logger.info(f"✓ 发布完成: {success_count}/{len(publish_results)} 成功")

                    # 发送成功通知
                    try:
                        await self.notifier.notify_success(episode_number, publish_results)
                    except Exception as notify_error:
                        logger.error(f"发送通知失败: {notify_error}")
                else:
                    logger.warning("没有可发布的任务")

            # 更新任务状态为完成
            self.task_manager.update_task_status(
                task.id,
                'completed',
                {
                    'pipeline': {
                        'success': pipeline_result.success,
                        'script_path': str(pipeline_result.script_path) if pipeline_result.script_path else None,
                        'audio_path': str(pipeline_result.final_audio_path) if pipeline_result.final_audio_path else None,
                        'video_path': str(pipeline_result.full_video_path) if pipeline_result.full_video_path else None,
                    },
                    'publish': [
                        {
                            'platform': r.platform,
                            'success': r.success,
                            'url': r.content_url
                        }
                        for r in publish_results
                    ]
                }
            )

            logger.info(f"=== 任务完成 (Task #{task.id}) ===")

            return TaskResult(
                success=True,
                task_id=task.id,
                episode_number=episode_number,
                pipeline_result=pipeline_result,
                publish_results=publish_results
            )

        except Exception as e:
            logger.exception("任务执行失败")

            # 更新任务状态为失败
            self.task_manager.update_task_status(
                task.id,
                'failed',
                error_message=str(e)
            )

            # 发送失败通知
            try:
                await self.notifier.notify_failure(task.id, str(e), episode_number)
            except Exception as notify_error:
                logger.error(f"发送通知失败: {notify_error}")

            return TaskResult(
                success=False,
                task_id=task.id,
                episode_number=episode_number,
                error=str(e)
            )

    async def collect_analytics(self) -> TaskResult:
        """收集分析数据"""
        logger.info("=== 开始数据收集任务 ===")

        task = self.task_manager.create_task('collect')

        try:
            self.task_manager.update_task_status(task.id, 'running')

            # 导入数据收集器
            from ..analytics.collector import DataCollector

            collector = DataCollector()

            # 获取最近的期号
            latest_ep = self.task_manager.get_latest_episode_number()
            if latest_ep > 0:
                logger.info(f"收集 EP{latest_ep:03d} 数据")
                metrics = await collector.collect_all(latest_ep)

                self.task_manager.update_task_status(
                    task.id,
                    'completed',
                    {'episode': latest_ep, 'metrics': str(metrics)}
                )

                logger.info("✓ 数据收集完成")
                return TaskResult(success=True, task_id=task.id)
            else:
                logger.warning("没有可收集的数据")
                self.task_manager.update_task_status(task.id, 'completed')
                return TaskResult(success=True, task_id=task.id)

        except Exception as e:
            logger.exception("数据收集失败")
            self.task_manager.update_task_status(
                task.id,
                'failed',
                error_message=str(e)
            )
            return TaskResult(success=False, task_id=task.id, error=str(e))

    async def generate_weekly_report(self) -> TaskResult:
        """生成每周报告"""
        logger.info("=== 开始生成周报任务 ===")

        task = self.task_manager.create_task('report')

        try:
            self.task_manager.update_task_status(task.id, 'running')

            # 导入报告生成器
            from ..analytics.reporter import AIReporter

            reporter = AIReporter()

            # 生成上周报告
            report = await reporter.generate_weekly_report()

            self.task_manager.update_task_status(
                task.id,
                'completed',
                {'report_path': str(report) if report else None}
            )

            # 发送周报通知
            try:
                # 从报告中提取数据(这里是示例)
                report_data = {
                    'episodes_count': 1,  # 需要从实际报告中获取
                    'total_views': 0,
                    'total_likes': 0,
                    'report_path': str(report) if report else None
                }
                await self.notifier.notify_weekly_report(report_data)
            except Exception as notify_error:
                logger.error(f"发送周报通知失败: {notify_error}")

            logger.info(f"✓ 周报生成完成: {report}")
            return TaskResult(success=True, task_id=task.id)

        except Exception as e:
            logger.exception("周报生成失败")
            self.task_manager.update_task_status(
                task.id,
                'failed',
                error_message=str(e)
            )
            return TaskResult(success=False, task_id=task.id, error=str(e))

    def run_pending_tasks(self) -> List[TaskResult]:
        """执行所有待处理任务

        Returns:
            List[TaskResult]: 任务执行结果列表
        """
        logger.info("执行所有待处理任务")

        results = []

        # 获取待处理任务
        pending_tasks = self.task_manager.get_pending_tasks()
        logger.info(f"找到 {len(pending_tasks)} 个待处理任务")

        for task in pending_tasks:
            logger.info(f"执行任务 #{task.id}: {task.task_type}")

            # 根据任务类型执行
            if task.task_type == 'generate':
                # 如果有 episode_number,执行生成
                if task.episode_number:
                    result = asyncio.run(self._run_generate_task(task))
                    results.append(result)
            elif task.task_type == 'collect':
                result = asyncio.run(self.collect_analytics())
                results.append(result)
            elif task.task_type == 'report':
                result = asyncio.run(self.generate_weekly_report())
                results.append(result)

        # 执行失败重试
        failed_tasks = self.task_manager.get_failed_tasks()
        logger.info(f"找到 {len(failed_tasks)} 个失败任务(可重试)")

        for task in failed_tasks:
            logger.info(f"重试任务 #{task.id}: {task.task_type}")
            self.task_manager.increment_retry_count(task.id)

            if task.task_type == 'generate' and task.episode_number:
                result = asyncio.run(self._run_generate_task(task))
                results.append(result)

        return results

    async def _run_generate_task(self, task) -> TaskResult:
        """执行生成任务（重试失败任务）

        Args:
            task: 任务对象

        Returns:
            TaskResult: 任务执行结果
        """
        logger.info(f"重试生成任务 #{task.id}")

        try:
            # 检查重试次数
            if task.retry_count >= 3:
                logger.error(f"任务 #{task.id} 已达到最大重试次数(3次)")
                return TaskResult(
                    success=False,
                    task_id=task.id,
                    error="超过最大重试次数"
                )

            self.task_manager.update_task_status(task.id, 'running')

            # 尝试使用 AI 自动生成主题重试
            logger.info("使用 AI 自动生成主题进行重试...")
            input_data = await self.topic_generator.generate_from_trends()

            # 运行内容流水线
            pipeline_result = await self.pipeline.run(
                input_data,
                task.episode_number,
                mode='auto'
            )

            if not pipeline_result.success:
                raise Exception(f"流水线执行失败: {pipeline_result.errors}")

            # 更新任务状态
            self.task_manager.update_task_status(
                task.id,
                'completed',
                {'retried': True, 'retry_count': task.retry_count}
            )

            logger.info(f"✓ 任务重试成功 (#{task.id})")

            return TaskResult(
                success=True,
                task_id=task.id,
                episode_number=task.episode_number,
                pipeline_result=pipeline_result
            )

        except Exception as e:
            logger.exception(f"任务重试失败 (#{task.id})")
            self.task_manager.update_task_status(
                task.id,
                'failed',
                error_message=str(e)
            )
            return TaskResult(success=False, task_id=task.id, error=str(e))

    async def auto_recover_failed_tasks(self) -> List[TaskResult]:
        """自动恢复失败的任务

        Returns:
            List[TaskResult]: 恢复结果列表
        """
        logger.info("=== 开始自动恢复失败任务 ===")

        failed_tasks = self.task_manager.get_failed_tasks()

        if not failed_tasks:
            logger.info("没有需要恢复的失败任务")
            return []

        logger.info(f"找到 {len(failed_tasks)} 个失败任务")

        results = []
        for task in failed_tasks:
            # 检查是否可以重试
            if task.retry_count >= 3:
                logger.warning(f"任务 #{task.id} 已达最大重试次数，跳过")
                continue

            # 增加重试计数
            self.task_manager.increment_retry_count(task.id)

            # 等待一段时间后重试 (指数退避)
            wait_time = min(60 * (2 ** task.retry_count), 3600)  # 最多等1小时
            logger.info(f"等待 {wait_time} 秒后重试任务 #{task.id}...")
            await asyncio.sleep(wait_time)

            # 根据任务类型重试
            if task.task_type == 'generate':
                result = await self._run_generate_task(task)
                results.append(result)
            elif task.task_type == 'publish':
                # TODO: 实现发布任务重试
                logger.warning(f"发布任务重试暂未实现 (#{task.id})")
            else:
                logger.warning(f"未知任务类型: {task.task_type} (#{task.id})")

        logger.info(f"=== 恢复完成: {sum(1 for r in results if r.success)}/{len(results)} 成功 ===")

        return results


if __name__ == "__main__":
    # 测试代码
    logger.info("测试 ContentOrchestrator")

    orchestrator = ContentOrchestrator()
    print(f"✓ Orchestrator 初始化成功")

    # 测试解析 cron
    time_str = orchestrator._parse_cron_time("0 6 * * 1")
    print(f"✓ Cron 解析: '0 6 * * 1' -> '{time_str}'")

    print("\n所有测试通过!")
