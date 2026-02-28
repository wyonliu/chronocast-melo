"""RSS Podcast 发布器

生成标准的 Podcast RSS 2.0 feed,支持 iTunes/Spotify
"""
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
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


class RSSPublisher(PlatformPublisher):
    """RSS Podcast 发布器"""

    def __init__(self, config: Dict[str, Any]):
        """初始化RSS发布器

        Args:
            config: 配置字典，需包含:
                - rss_url: RSS feed 的公开访问URL
                - enabled: 是否启用
                - title: 播客标题 (可选)
                - description: 播客描述 (可选)
                - author: 作者 (可选)
                - email: 联系邮箱 (可选)
                - image_url: 播客封面图URL (可选)
                - category: 分类 (可选)
                - output_path: RSS文件输出路径 (可选)
        """
        super().__init__(config)

        self.rss_url = config.get("rss_url", "")
        self.title = config.get("title", "ChronoCast 超时空电台")
        self.description = config.get("description", "麦洛与船长聊聊这个正在被 AI 改变的世界")
        self.author = config.get("author", "麦洛与船长")
        self.email = config.get("email", "podcast@chronocast.com")
        self.image_url = config.get("image_url", "")
        self.category = config.get("category", "Technology")
        self.output_path = Path(config.get("output_path", "output/rss/podcast.xml"))

        # 确保输出目录存在
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    async def publish(self, task: PublishTask) -> PublishResult:
        """发布音频到RSS feed

        Args:
            task: 发布任务

        Returns:
            PublishResult: 发布结果
        """
        if not self.enabled:
            return PublishResult(
                platform="rss",
                success=False,
                error_message="RSS publisher is disabled"
            )

        try:
            # 检查音频文件是否存在
            if not task.file_path or not Path(task.file_path).exists():
                return PublishResult(
                    platform="rss",
                    success=False,
                    error_message=f"Audio file not found: {task.file_path}"
                )

            logger.info(f"添加节目到RSS: {task.title}")

            # 获取文件大小
            file_size = Path(task.file_path).stat().st_size

            # 生成音频URL（需要部署到可访问的服务器）
            # 这里使用相对路径，实际部署时需要完整URL
            audio_url = f"https://your-domain.com/audio/{Path(task.file_path).name}"

            # 读取现有RSS或创建新的
            if self.output_path.exists():
                tree = ET.parse(self.output_path)
                root = tree.getroot()
                channel = root.find('channel')
            else:
                root, channel = self._create_rss_skeleton()
                tree = ET.ElementTree(root)

            # 添加新episode
            item = self._create_episode_item(
                title=task.title,
                description=task.description or "",
                audio_url=audio_url,
                file_size=file_size,
                pub_date=datetime.now(),
                guid=audio_url
            )

            channel.append(item)

            # 更新lastBuildDate
            last_build = channel.find('lastBuildDate')
            if last_build is not None:
                last_build.text = self._format_rfc822(datetime.now())

            # 写入文件
            self._write_rss(tree, self.output_path)

            logger.info(f"✓ RSS feed 已更新: {self.output_path}")
            logger.info(f"  公开访问: {self.rss_url}")

            return PublishResult(
                platform="rss",
                success=True,
                content_url=self.rss_url,
                published_at=datetime.now().isoformat()
            )

        except Exception as e:
            logger.exception(f"RSS发布失败: {e}")
            return PublishResult(
                platform="rss",
                success=False,
                error_message=str(e)
            )

    def _create_rss_skeleton(self) -> tuple:
        """创建RSS骨架结构

        Returns:
            tuple: (root, channel) ElementTree节点
        """
        # RSS 2.0 根元素
        root = ET.Element('rss', {
            'version': '2.0',
            'xmlns:itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd',
            'xmlns:content': 'http://purl.org/rss/1.0/modules/content/',
            'xmlns:atom': 'http://www.w3.org/2005/Atom'
        })

        channel = ET.SubElement(root, 'channel')

        # 基本信息
        ET.SubElement(channel, 'title').text = self.title
        ET.SubElement(channel, 'description').text = self.description
        ET.SubElement(channel, 'link').text = self.rss_url
        ET.SubElement(channel, 'language').text = 'zh-CN'
        ET.SubElement(channel, 'lastBuildDate').text = self._format_rfc822(datetime.now())

        # iTunes 标签
        ET.SubElement(channel, '{http://www.itunes.com/dtds/podcast-1.0.dtd}author').text = self.author
        ET.SubElement(channel, '{http://www.itunes.com/dtds/podcast-1.0.dtd}subtitle').text = self.description
        ET.SubElement(channel, '{http://www.itunes.com/dtds/podcast-1.0.dtd}summary').text = self.description
        ET.SubElement(channel, '{http://www.itunes.com/dtds/podcast-1.0.dtd}explicit').text = 'false'

        # iTunes 分类
        category_elem = ET.SubElement(channel, '{http://www.itunes.com/dtds/podcast-1.0.dtd}category', {'text': self.category})

        # iTunes 封面
        if self.image_url:
            ET.SubElement(channel, '{http://www.itunes.com/dtds/podcast-1.0.dtd}image', {'href': self.image_url})
            image_elem = ET.SubElement(channel, 'image')
            ET.SubElement(image_elem, 'url').text = self.image_url
            ET.SubElement(image_elem, 'title').text = self.title
            ET.SubElement(image_elem, 'link').text = self.rss_url

        # Owner
        owner = ET.SubElement(channel, '{http://www.itunes.com/dtds/podcast-1.0.dtd}owner')
        ET.SubElement(owner, '{http://www.itunes.com/dtds/podcast-1.0.dtd}name').text = self.author
        ET.SubElement(owner, '{http://www.itunes.com/dtds/podcast-1.0.dtd}email').text = self.email

        return root, channel

    def _create_episode_item(
        self,
        title: str,
        description: str,
        audio_url: str,
        file_size: int,
        pub_date: datetime,
        guid: str
    ) -> ET.Element:
        """创建episode item元素

        Args:
            title: 标题
            description: 描述
            audio_url: 音频文件URL
            file_size: 文件大小(字节)
            pub_date: 发布日期
            guid: 唯一标识符

        Returns:
            ET.Element: item元素
        """
        item = ET.Element('item')

        ET.SubElement(item, 'title').text = title
        ET.SubElement(item, 'description').text = description
        ET.SubElement(item, 'pubDate').text = self._format_rfc822(pub_date)
        ET.SubElement(item, 'guid', {'isPermaLink': 'true'}).text = guid

        # Enclosure (音频文件)
        ET.SubElement(item, 'enclosure', {
            'url': audio_url,
            'length': str(file_size),
            'type': 'audio/mpeg'
        })

        # iTunes 标签
        ET.SubElement(item, '{http://www.itunes.com/dtds/podcast-1.0.dtd}author').text = self.author
        ET.SubElement(item, '{http://www.itunes.com/dtds/podcast-1.0.dtd}subtitle').text = title
        ET.SubElement(item, '{http://www.itunes.com/dtds/podcast-1.0.dtd}summary').text = description
        ET.SubElement(item, '{http://www.itunes.com/dtds/podcast-1.0.dtd}explicit').text = 'false'

        return item

    def _format_rfc822(self, dt: datetime) -> str:
        """格式化日期为RFC822格式

        Args:
            dt: datetime对象

        Returns:
            str: RFC822格式的日期字符串
        """
        # RFC822 格式: "Wed, 02 Oct 2002 13:00:00 GMT"
        return dt.strftime('%a, %d %b %Y %H:%M:%S +0800')

    def _write_rss(self, tree: ET.ElementTree, output_path: Path) -> None:
        """写入RSS文件

        Args:
            tree: ElementTree对象
            output_path: 输出路径
        """
        # 美化XML
        self._indent(tree.getroot())

        # 写入文件
        tree.write(
            str(output_path),
            encoding='utf-8',
            xml_declaration=True,
            method='xml'
        )

    def _indent(self, elem: ET.Element, level: int = 0) -> None:
        """美化XML缩进

        Args:
            elem: XML元素
            level: 缩进级别
        """
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for child in elem:
                self._indent(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i

    async def check_status(self, content_id: str) -> Dict[str, Any]:
        """检查RSS feed状态

        Args:
            content_id: 内容ID (这里是RSS URL)

        Returns:
            Dict: 状态信息
        """
        try:
            if self.output_path.exists():
                return {
                    "exists": True,
                    "path": str(self.output_path),
                    "size": self.output_path.stat().st_size,
                    "modified": datetime.fromtimestamp(self.output_path.stat().st_mtime).isoformat()
                }
            return {"exists": False}
        except Exception as e:
            logger.error(f"检查RSS状态失败: {e}")
            return {}


if __name__ == "__main__":
    # 测试代码
    import asyncio

    logger.info("测试 RSSPublisher")

    # 创建测试配置
    config = {
        "enabled": True,
        "rss_url": "https://chronocast.com/rss.xml",
        "title": "ChronoCast 测试",
        "output_path": "/tmp/test_podcast.xml"
    }

    publisher = RSSPublisher(config)
    print(f"✓ RSSPublisher 初始化成功")

    # 创建临时测试文件
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.mp3', delete=False) as f:
        f.write("fake audio content")
        temp_audio = f.name

    # 测试发布
    async def test_publish():
        task = PublishTask(
            platform="rss",
            content_type="audio",
            file_path=Path(temp_audio),
            title="EP001: 测试节目",
            description="这是一个测试节目"
        )

        result = await publisher.publish(task)
        print(f"✓ 发布测试完成")
        print(f"  成功: {result.success}")
        print(f"  URL: {result.content_url}")

        # 检查生成的RSS文件
        if Path(config["output_path"]).exists():
            print(f"✓ RSS文件已生成: {config['output_path']}")

    asyncio.run(test_publish())

    # 清理
    import os
    os.unlink(temp_audio)
    if Path(config["output_path"]).exists():
        os.unlink(config["output_path"])

    print("\n✓ 所有测试通过!")
