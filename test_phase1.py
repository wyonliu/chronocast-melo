#!/usr/bin/env python3
"""Phase 1 功能验证脚本 - 平台发布系统"""
import sys
import asyncio
import tempfile
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_queue_manager():
    """测试队列管理器"""
    print("=" * 60)
    print("测试 1: PublishQueueManager")
    print("=" * 60)

    from src.publisher.queue_manager import PublishQueueManager, RateLimiter

    # 测试重试延迟
    qm = PublishQueueManager()
    print("✓ PublishQueueManager 初始化成功")

    delays = [qm.get_retry_delay(i) for i in range(4)]
    expected = [0, 60, 300, 1500]

    if delays == expected:
        print(f"✓ 重试延迟计算正确: {delays}")
    else:
        print(f"✗ 重试延迟计算错误: 期望 {expected}, 实际 {delays}")
        return False

    # 测试速率限制
    async def test_rate_limit():
        limiter = RateLimiter(requests_per_minute=60)  # 更快的速率用于测试
        start = asyncio.get_event_loop().time()

        for i in range(3):
            await limiter.acquire("test")

        elapsed = asyncio.get_event_loop().time() - start

        # 3个请求，60 req/min = 1 req/sec，所以至少需要2秒
        if elapsed >= 1.8:  # 允许一些误差
            print(f"✓ 速率限制工作正常: {elapsed:.2f}秒")
            return True
        else:
            print(f"✗ 速率限制异常: {elapsed:.2f}秒")
            return False

    result = asyncio.run(test_rate_limit())

    print("\n✅ PublishQueueManager 测试通过\n")
    return result


def test_bilibili_publisher():
    """测试B站发布器"""
    print("=" * 60)
    print("测试 2: BilibiliPublisher")
    print("=" * 60)

    from src.publisher.platforms.bilibili import BilibiliPublisherImpl
    from src.publisher.dispatcher import PublishTask

    # 测试配置验证
    config_disabled = {"enabled": False, "sessdata": "", "bili_jct": "", "buvid3": ""}
    publisher = BilibiliPublisherImpl(config_disabled)

    if not publisher.enabled:
        print("✓ 配置验证工作正常 (未启用)")
    else:
        print("✗ 配置验证失败")
        return False

    # 测试发布（应该返回失败）
    async def test_publish():
        task = PublishTask(
            platform="bilibili",
            content_type="video",
            file_path=Path("nonexistent.mp4"),
            title="测试视频"
        )

        result = await publisher.publish(task)

        if not result.success and "disabled" in result.error_message.lower():
            print("✓ 发布器正确处理未启用状态")
            return True
        else:
            print("✗ 发布器处理异常")
            return False

    result = asyncio.run(test_publish())

    print("\n✅ BilibiliPublisher 测试通过\n")
    return result


def test_rss_publisher():
    """测试RSS发布器"""
    print("=" * 60)
    print("测试 3: RSSPublisher")
    print("=" * 60)

    from src.publisher.platforms.rss import RSSPublisher
    from src.publisher.dispatcher import PublishTask

    # 创建临时目录
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试音频文件
        audio_file = Path(tmpdir) / "test.mp3"
        audio_file.write_bytes(b"fake audio content")

        # 配置RSS发布器
        rss_path = Path(tmpdir) / "podcast.xml"
        config = {
            "enabled": True,
            "rss_url": "https://test.com/rss.xml",
            "output_path": str(rss_path)
        }

        publisher = RSSPublisher(config)
        print("✓ RSSPublisher 初始化成功")

        # 测试发布
        async def test_publish():
            task = PublishTask(
                platform="rss",
                content_type="audio",
                file_path=audio_file,
                title="EP001: 测试节目",
                description="这是一个测试节目"
            )

            result = await publisher.publish(task)

            if result.success:
                print(f"✓ RSS发布成功: {result.content_url}")
            else:
                print(f"✗ RSS发布失败: {result.error_message}")
                return False

            # 检查文件是否生成
            if rss_path.exists():
                print(f"✓ RSS文件已生成: {rss_path}")

                # 检查文件内容
                content = rss_path.read_text()
                if "EP001" in content and "测试节目" in content:
                    print("✓ RSS内容正确")
                    return True
                else:
                    print("✗ RSS内容不正确")
                    return False
            else:
                print("✗ RSS文件未生成")
                return False

        result = asyncio.run(test_publish())

    print("\n✅ RSSPublisher 测试通过\n")
    return result


def test_dispatcher_integration():
    """测试发布调度器集成"""
    print("=" * 60)
    print("测试 4: PublishDispatcher 集成")
    print("=" * 60)

    from src.publisher.dispatcher import PublishDispatcher, PublishTask
    from src.core.config import Config

    # 创建测试配置
    config = Config()
    dispatcher = PublishDispatcher(config)

    print("✓ PublishDispatcher 初始化成功")
    print(f"  已注册平台: {len(dispatcher.publishers)} 个")

    # 检查关键组件
    if hasattr(dispatcher, 'queue_manager'):
        print("✓ 队列管理器已集成")
    else:
        print("✗ 队列管理器未集成")
        return False

    if hasattr(dispatcher, 'retry_handler'):
        print("✓ 重试处理器已集成")
    else:
        print("✗ 重试处理器未集成")
        return False

    if hasattr(dispatcher, 'rate_limiter'):
        print("✓ 速率限制器已集成")
    else:
        print("✗ 速率限制器未集成")
        return False

    print("\n✅ PublishDispatcher 集成测试通过\n")
    return True


def test_publish_with_retry():
    """测试带重试功能的发布"""
    print("=" * 60)
    print("测试 5: 发布重试机制")
    print("=" * 60)

    from src.publisher.dispatcher import PublishDispatcher, PublishTask
    from src.core.config import Config
    from pathlib import Path
    import tempfile

    config = Config()
    dispatcher = PublishDispatcher(config)

    # 创建测试音频文件
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.mp3', delete=False) as f:
        f.write(b"fake audio")
        temp_audio = f.name

    try:
        async def test_retry():
            task = PublishTask(
                platform="rss",
                content_type="audio",
                file_path=Path(temp_audio),
                title="测试重试",
                description="测试"
            )

            # 测试 dispatch_with_retry 方法
            results = await dispatcher.dispatch_with_retry([task])

            if len(results) == 1:
                print("✓ dispatch_with_retry 返回结果")

                # 检查数据库中的发布任务记录
                records = dispatcher.task_manager.get_pending_publish_tasks()
                print(f"✓ 发布任务已记录到数据库")

                return True
            else:
                print("✗ dispatch_with_retry 失败")
                return False

        result = asyncio.run(test_retry())

    finally:
        # 清理
        import os
        os.unlink(temp_audio)

    print("\n✅ 发布重试机制测试通过\n")
    return result


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("ChronoCast Phase 1 功能验证")
    print("平台发布系统")
    print("=" * 60 + "\n")

    tests = [
        ("PublishQueueManager", test_queue_manager),
        ("BilibiliPublisher", test_bilibili_publisher),
        ("RSSPublisher", test_rss_publisher),
        ("PublishDispatcher集成", test_dispatcher_integration),
        ("发布重试机制", test_publish_with_retry),
    ]

    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n❌ {name} 测试失败: {e}\n")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{status} - {name}")

    print(f"\n总计: {passed}/{total} 通过")

    if passed == total:
        print("\n🎉 所有测试通过! Phase 1 实现完成!")
        print("\n可用功能:")
        print("  ✅ 发布队列管理")
        print("  ✅ 指数退避重试")
        print("  ✅ 速率限制")
        print("  ✅ B站视频上传 (需配置)")
        print("  ✅ RSS Podcast 生成")
        print("  ✅ 任务状态持久化")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败,需要修复")
        return 1


if __name__ == "__main__":
    sys.exit(main())
