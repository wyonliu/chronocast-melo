#!/usr/bin/env python3
"""Phase 0 功能验证脚本"""
import sys
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_task_manager():
    """测试任务管理器"""
    print("=" * 60)
    print("测试 1: TaskManager")
    print("=" * 60)

    from src.core.task_manager import TaskManager

    tm = TaskManager()
    print("✓ TaskManager 初始化成功")

    # 创建任务
    task = tm.create_task('test', {'message': 'Hello'}, episode_number=100)
    print(f"✓ 创建任务 #{task.id}")

    # 更新状态
    tm.update_task_status(task.id, 'running')
    print("✓ 更新状态: running")

    tm.update_task_status(task.id, 'completed', {'result': 'success'})
    print("✓ 更新状态: completed")

    # 查询任务
    retrieved = tm.get_task(task.id)
    assert retrieved.status == 'completed'
    print(f"✓ 查询任务: {retrieved.status}")

    # 获取最新期号
    latest = tm.get_latest_episode_number()
    print(f"✓ 最新期号: {latest}")

    print("\n✅ TaskManager 测试通过\n")
    return True


def test_config():
    """测试配置系统"""
    print("=" * 60)
    print("测试 2: Config")
    print("=" * 60)

    from src.core.config import Config

    # 使用默认配置
    config = Config()
    print("✓ Config 初始化成功")

    print(f"✓ 项目名: {config.project.name}")
    print(f"✓ 工作模式: {config.workflow.mode}")
    print(f"✓ 调度器启用: {config.scheduler.enabled}")
    print(f"✓ 通知启用: {config.notification.enabled}")
    print(f"✓ 重试次数: {config.publish.retry.max_attempts}")

    print("\n✅ Config 测试通过\n")
    return True


def test_cli_commands():
    """测试 CLI 命令"""
    print("=" * 60)
    print("测试 3: CLI Commands")
    print("=" * 60)

    import subprocess

    # 测试 --help
    result = subprocess.run(
        ['python3', 'chronocast.py', '--help'],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print("✓ CLI 基础命令可用")

        # 检查新命令是否存在
        commands = ['scheduler', 'publish', 'collect', 'report']
        for cmd in commands:
            if cmd in result.stdout:
                print(f"✓ {cmd} 命令已注册")
            else:
                print(f"✗ {cmd} 命令未找到")
                return False
    else:
        print("✗ CLI 命令测试失败")
        return False

    print("\n✅ CLI Commands 测试通过\n")
    return True


def test_database():
    """测试数据库表"""
    print("=" * 60)
    print("测试 4: Database Tables")
    print("=" * 60)

    import sqlite3
    from pathlib import Path

    db_path = Path("data/analytics.db")

    if not db_path.exists():
        print("✗ 数据库文件不存在")
        return False

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 检查表是否存在
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table'
        ORDER BY name
    """)

    tables = [row[0] for row in cursor.fetchall()]
    print(f"✓ 数据库存在,共 {len(tables)} 个表")

    required_tables = ['tasks', 'publish_tasks']
    for table in required_tables:
        if table in tables:
            print(f"✓ {table} 表已创建")
        else:
            print(f"✗ {table} 表不存在")
            conn.close()
            return False

    # 检查 tasks 表结构
    cursor.execute("PRAGMA table_info(tasks)")
    columns = [row[1] for row in cursor.fetchall()]
    print(f"✓ tasks 表有 {len(columns)} 列")

    conn.close()

    print("\n✅ Database 测试通过\n")
    return True


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("ChronoCast Phase 0 功能验证")
    print("=" * 60 + "\n")

    tests = [
        ("TaskManager", test_task_manager),
        ("Config", test_config),
        ("CLI Commands", test_cli_commands),
        ("Database", test_database),
    ]

    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n❌ {name} 测试失败: {e}\n")
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
        print("\n🎉 所有测试通过! Phase 0 实现完成!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败,需要修复")
        return 1


if __name__ == "__main__":
    sys.exit(main())
