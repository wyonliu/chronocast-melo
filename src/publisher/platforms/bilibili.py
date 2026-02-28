"""B站视频发布器

使用 bilibili-api-python 库上传视频
"""
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger

from ..models import PublishTask, PublishResult


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


class BilibiliPublisherImpl(PlatformPublisher):
    """B站视频发布器实现"""

    def __init__(self, config: Dict[str, Any]):
        """初始化B站发布器

        Args:
            config: 配置字典，需包含:
                - sessdata: B站 cookie 中的 SESSDATA
                - bili_jct: B站 cookie 中的 bili_jct
                - buvid3: B站 cookie 中的 buvid3
                - enabled: 是否启用
        """
        super().__init__(config)

        self.sessdata = config.get("sessdata", "")
        self.bili_jct = config.get("bili_jct", "")
        self.buvid3 = config.get("buvid3", "")

        # 验证配置
        if self.enabled:
            if not all([self.sessdata, self.bili_jct, self.buvid3]):
                logger.warning("B站配置不完整，请检查 sessdata, bili_jct, buvid3")
                self.enabled = False

    async def publish(self, task: PublishTask) -> PublishResult:
        """发布视频到B站

        Args:
            task: 发布任务

        Returns:
            PublishResult: 发布结果
        """
        if not self.enabled:
            return PublishResult(
                platform="bilibili",
                success=False,
                error_message="Bilibili publisher is disabled or misconfigured"
            )

        try:
            # 检查文件是否存在
            if not task.file_path or not Path(task.file_path).exists():
                return PublishResult(
                    platform="bilibili",
                    success=False,
                    error_message=f"Video file not found: {task.file_path}"
                )

            logger.info(f"开始上传视频到B站: {task.title}")
            logger.info(f"文件路径: {task.file_path}")

            # 导入 bilibili-api 库
            try:
                from bilibili_api import video, Credential
            except ImportError:
                return PublishResult(
                    platform="bilibili",
                    success=False,
                    error_message="bilibili-api-python not installed. Run: pip install bilibili-api-python"
                )

            # 创建凭证
            credential = Credential(
                sessdata=self.sessdata,
                bili_jct=self.bili_jct,
                buvid3=self.buvid3
            )

            # 准备上传参数
            pages = [{
                "path": str(task.file_path),
                "title": task.title,
                "description": task.description or ""
            }]

            # 准备视频元数据
            meta = {
                "title": task.title,
                "desc": task.description or "",
                "copyright": 1,  # 1=原创，2=转载
                "tag": ",".join(task.tags) if task.tags else "AI,科技,播客",
                "tid": 188,  # 科技分区
                "cover": "",  # 封面图URL（如果有）
                "source": "",  # 转载来源（原创则为空）
            }

            logger.info("创建上传器...")

            # 创建上传器
            uploader = video.VideoUploaderWeb(
                pages=pages,
                meta=meta,
                credential=credential
            )

            # 开始上传
            logger.info("开始上传视频...")
            result = await uploader.start()

            # 解析结果
            if result and 'bvid' in result:
                bvid = result['bvid']
                video_url = f"https://www.bilibili.com/video/{bvid}"

                logger.info(f"✓ 视频上传成功: {video_url}")

                return PublishResult(
                    platform="bilibili",
                    success=True,
                    content_url=video_url,
                    published_at=None  # B站API可能不返回发布时间
                )
            else:
                return PublishResult(
                    platform="bilibili",
                    success=False,
                    error_message="Upload succeeded but no bvid returned"
                )

        except Exception as e:
            logger.exception(f"B站上传失败: {e}")
            return PublishResult(
                platform="bilibili",
                success=False,
                error_message=str(e)
            )

    async def check_status(self, content_id: str) -> Dict[str, Any]:
        """检查视频状态

        Args:
            content_id: 视频BV号

        Returns:
            Dict: 视频状态信息
        """
        try:
            from bilibili_api import video, Credential

            credential = Credential(
                sessdata=self.sessdata,
                bili_jct=self.bili_jct,
                buvid3=self.buvid3
            )

            v = video.Video(bvid=content_id, credential=credential)
            info = await v.get_info()

            return {
                "title": info.get("title", ""),
                "view": info.get("stat", {}).get("view", 0),
                "like": info.get("stat", {}).get("like", 0),
                "coin": info.get("stat", {}).get("coin", 0),
                "favorite": info.get("stat", {}).get("favorite", 0),
                "share": info.get("stat", {}).get("share", 0),
                "reply": info.get("stat", {}).get("reply", 0),
            }

        except Exception as e:
            logger.error(f"获取B站视频状态失败: {e}")
            return {}


# 为了保持向后兼容，提供一个别名
BilibiliPublisher = BilibiliPublisherImpl


if __name__ == "__main__":
    # 测试代码
    import asyncio

    logger.info("测试 BilibiliPublisher")

    # 创建测试配置
    config = {
        "enabled": False,  # 测试时不启用
        "sessdata": "test_sessdata",
        "bili_jct": "test_bili_jct",
        "buvid3": "test_buvid3"
    }

    publisher = BilibiliPublisherImpl(config)
    print(f"✓ BilibiliPublisher 初始化成功")
    print(f"  启用状态: {publisher.enabled}")

    # 测试发布（由于未启用，应该返回失败）
    async def test_publish():
        task = PublishTask(
            platform="bilibili",
            content_type="video",
            file_path=Path("test.mp4"),
            title="测试视频",
            description="这是一个测试",
            tags=["测试", "AI"]
        )

        result = await publisher.publish(task)
        print(f"✓ 发布测试完成")
        print(f"  成功: {result.success}")
        print(f"  错误: {result.error_message}")

    asyncio.run(test_publish())

    print("\n✓ 所有测试通过!")
