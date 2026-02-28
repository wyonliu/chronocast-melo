"""通知模块

提供多渠道通知能力:
- Webhook 通用接口
- 钉钉机器人
- 飞书机器人
"""

from .notifier import NotificationService

__all__ = ["NotificationService"]
