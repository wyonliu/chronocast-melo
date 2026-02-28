"""发布系统数据模型

定义共享的数据类，避免循环导入
"""
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field
from enum import Enum


class PlatformType(Enum):
    """平台类型"""
    PODCAST = "podcast"      # 播客平台
    VIDEO = "video"          # 视频平台
    SHORT_VIDEO = "short"    # 短视频平台
    SOCIAL = "social"        # 社交平台
    BLOG = "blog"            # 博客平台


@dataclass
class PublishTask:
    """发布任务"""
    platform: str
    content_type: str  # "audio", "video", "clip", "card", "text"
    file_path: Optional[Path] = None
    title: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    scheduled_time: Optional[str] = None  # ISO格式时间
    episode_number: int = 0  # 添加期号字段


@dataclass
class PublishResult:
    """发布结果"""
    platform: str
    success: bool
    content_url: Optional[str] = None
    error_message: Optional[str] = None
    published_at: Optional[str] = None
