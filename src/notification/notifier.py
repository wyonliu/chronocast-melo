"""通知服务

支持多种通知渠道:
- Webhook (通用HTTP POST)
- 钉钉机器人
- 飞书机器人
"""
import json
import hmac
import hashlib
import base64
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio
import aiohttp
from loguru import logger

from ..core.config import get_config, Config


class NotificationService:
    """通知服务"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.notification_config = getattr(self.config, 'notification', None)

        if not self.notification_config:
            logger.warning("通知配置未找到，通知功能将被禁用")
            self.enabled = False
            return

        self.enabled = getattr(self.notification_config, 'enabled', False)

        # Webhook 配置
        webhook_config = getattr(self.notification_config, 'webhook', {})
        if isinstance(webhook_config, dict):
            self.webhook_enabled = webhook_config.get('enabled', False)
            self.webhook_url = webhook_config.get('url', '')
        else:
            self.webhook_enabled = getattr(webhook_config, 'enabled', False)
            self.webhook_url = getattr(webhook_config, 'url', '')

        # 钉钉配置
        dingtalk_config = getattr(self.notification_config, 'dingtalk', {})
        if isinstance(dingtalk_config, dict):
            self.dingtalk_enabled = dingtalk_config.get('enabled', False)
            self.dingtalk_webhook = dingtalk_config.get('webhook', '')
            self.dingtalk_secret = dingtalk_config.get('secret', '')
        else:
            self.dingtalk_enabled = getattr(dingtalk_config, 'enabled', False)
            self.dingtalk_webhook = getattr(dingtalk_config, 'webhook', '')
            self.dingtalk_secret = getattr(dingtalk_config, 'secret', '')

        # 飞书配置
        feishu_config = getattr(self.notification_config, 'feishu', {})
        if isinstance(feishu_config, dict):
            self.feishu_enabled = feishu_config.get('enabled', False)
            self.feishu_webhook = feishu_config.get('webhook', '')
            self.feishu_secret = feishu_config.get('secret', '')
        else:
            self.feishu_enabled = getattr(feishu_config, 'enabled', False)
            self.feishu_webhook = getattr(feishu_config, 'webhook', '')
            self.feishu_secret = getattr(feishu_config, 'secret', '')

    async def notify_success(
        self,
        episode_number: int,
        results: List[Any]
    ) -> None:
        """发送成功通知

        Args:
            episode_number: 期号
            results: 发布结果列表
        """
        if not self.enabled:
            return

        # 构建消息
        platforms = {}
        for r in results:
            if hasattr(r, 'success') and r.success:
                platform_name = getattr(r, 'platform', 'unknown')
                content_url = getattr(r, 'content_url', '')
                platforms[platform_name] = content_url

        message = f"✅ EP{episode_number:03d} 发布成功\n\n"
        message += f"发布平台: {len(platforms)}个\n"
        for platform, url in platforms.items():
            message += f"- {platform}: {url}\n"
        message += f"\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        payload = {
            "type": "episode_published",
            "episode_number": episode_number,
            "platforms": platforms,
            "timestamp": datetime.now().isoformat(),
            "message": message
        }

        # 发送到各渠道
        await self._send_all_channels(message, payload)

    async def notify_failure(
        self,
        task_id: int,
        error: str,
        episode_number: Optional[int] = None
    ) -> None:
        """发送失败通知

        Args:
            task_id: 任务ID
            error: 错误信息
            episode_number: 期号(可选)
        """
        if not self.enabled:
            return

        ep_str = f"EP{episode_number:03d}" if episode_number else "未知期号"
        message = f"❌ {ep_str} 任务失败\n\n"
        message += f"任务ID: {task_id}\n"
        message += f"错误: {error}\n"
        message += f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        payload = {
            "type": "task_failed",
            "task_id": task_id,
            "episode_number": episode_number,
            "error": error,
            "timestamp": datetime.now().isoformat(),
            "message": message
        }

        await self._send_all_channels(message, payload)

    async def notify_weekly_report(
        self,
        report_data: Dict[str, Any]
    ) -> None:
        """发送周报通知

        Args:
            report_data: 周报数据
        """
        if not self.enabled:
            return

        message = f"📊 本周数据报告\n\n"
        message += f"发布内容: {report_data.get('episodes_count', 0)}期\n"
        message += f"总播放量: {report_data.get('total_views', 0)}\n"
        message += f"总点赞数: {report_data.get('total_likes', 0)}\n"
        message += f"时间: {datetime.now().strftime('%Y-%m-%d')}"

        payload = {
            "type": "weekly_report",
            "data": report_data,
            "timestamp": datetime.now().isoformat(),
            "message": message
        }

        await self._send_all_channels(message, payload)

    async def _send_all_channels(
        self,
        message: str,
        payload: Dict[str, Any]
    ) -> None:
        """发送到所有启用的通知渠道

        Args:
            message: 纯文本消息
            payload: 结构化数据
        """
        tasks = []

        if self.webhook_enabled and self.webhook_url:
            tasks.append(self.send_webhook(payload))

        if self.dingtalk_enabled and self.dingtalk_webhook:
            tasks.append(self.send_dingtalk(message))

        if self.feishu_enabled and self.feishu_webhook:
            tasks.append(self.send_feishu(message))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"通知发送失败 (渠道 {i+1}): {result}")

    async def send_webhook(self, payload: Dict[str, Any]) -> None:
        """发送 Webhook 通知

        Args:
            payload: 发送的数据
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        logger.info(f"✓ Webhook 通知已发送: {self.webhook_url}")
                    else:
                        logger.error(f"Webhook 通知失败: {resp.status}")
        except Exception as e:
            logger.exception(f"Webhook 发送异常: {e}")
            raise

    async def send_dingtalk(self, message: str) -> None:
        """发送钉钉机器人通知

        Args:
            message: 消息文本
        """
        try:
            # 生成签名
            timestamp = str(round(time.time() * 1000))
            sign = ""

            if self.dingtalk_secret:
                secret_enc = self.dingtalk_secret.encode('utf-8')
                string_to_sign = f'{timestamp}\n{self.dingtalk_secret}'
                string_to_sign_enc = string_to_sign.encode('utf-8')
                hmac_code = hmac.new(
                    secret_enc,
                    string_to_sign_enc,
                    digestmod=hashlib.sha256
                ).digest()
                sign = base64.b64encode(hmac_code).decode('utf-8')

            # 构建URL
            url = self.dingtalk_webhook
            if sign:
                url += f"&timestamp={timestamp}&sign={sign}"

            # 构建消息
            payload = {
                "msgtype": "text",
                "text": {
                    "content": f"ChronoCast 通知\n\n{message}"
                }
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        logger.info("✓ 钉钉通知已发送")
                    else:
                        logger.error(f"钉钉通知失败: {resp.status}")
        except Exception as e:
            logger.exception(f"钉钉通知发送异常: {e}")
            raise

    async def send_feishu(self, message: str) -> None:
        """发送飞书机器人通知

        Args:
            message: 消息文本
        """
        try:
            # 生成签名
            timestamp = str(int(time.time()))
            sign = ""

            if self.feishu_secret:
                string_to_sign = f"{timestamp}\n{self.feishu_secret}"
                hmac_code = hmac.new(
                    self.feishu_secret.encode('utf-8'),
                    string_to_sign.encode('utf-8'),
                    digestmod=hashlib.sha256
                ).digest()
                sign = base64.b64encode(hmac_code).decode('utf-8')

            # 构建消息
            payload = {
                "msg_type": "text",
                "content": {
                    "text": f"ChronoCast 通知\n\n{message}"
                }
            }

            if sign:
                payload["timestamp"] = timestamp
                payload["sign"] = sign

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.feishu_webhook,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        logger.info("✓ 飞书通知已发送")
                    else:
                        logger.error(f"飞书通知失败: {resp.status}")
        except Exception as e:
            logger.exception(f"飞书通知发送异常: {e}")
            raise


if __name__ == "__main__":
    # 测试代码
    import asyncio

    logger.info("测试 NotificationService")

    # 创建测试配置
    from types import SimpleNamespace

    test_config = SimpleNamespace(
        notification=SimpleNamespace(
            enabled=True,
            webhook=SimpleNamespace(
                enabled=False,
                url="https://webhook.site/test"
            ),
            dingtalk=SimpleNamespace(
                enabled=False,
                webhook="",
                secret=""
            ),
            feishu=SimpleNamespace(
                enabled=False,
                webhook="",
                secret=""
            )
        )
    )

    notifier = NotificationService(test_config)
    print(f"✓ NotificationService 初始化成功")
    print(f"  启用状态: {notifier.enabled}")
    print(f"  Webhook: {notifier.webhook_enabled}")
    print(f"  钉钉: {notifier.dingtalk_enabled}")
    print(f"  飞书: {notifier.feishu_enabled}")

    # 测试通知发送
    async def test_notify():
        from dataclasses import dataclass

        @dataclass
        class MockResult:
            platform: str
            success: bool
            content_url: str

        results = [
            MockResult("rss", True, "https://example.com/rss.xml"),
            MockResult("bilibili", True, "https://bilibili.com/video/BV123")
        ]

        # 测试成功通知
        await notifier.notify_success(1, results)
        print("✓ 成功通知测试完成")

        # 测试失败通知
        await notifier.notify_failure(123, "测试错误", 1)
        print("✓ 失败通知测试完成")

        # 测试周报通知
        report_data = {
            "episodes_count": 4,
            "total_views": 1000,
            "total_likes": 50
        }
        await notifier.notify_weekly_report(report_data)
        print("✓ 周报通知测试完成")

    asyncio.run(test_notify())

    print("\n✓ 所有测试通过!")
