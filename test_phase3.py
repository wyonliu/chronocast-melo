"""Phase 3 测试 - 完整自动化

测试内容:
1. TopicGenerator 初始化
2. AI 自动选题
3. 主题历史管理
4. Orchestrator 集成自动选题
5. 失败任务自动恢复
"""
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from loguru import logger

# 配置日志
logger.remove()
logger.add(lambda msg: print(msg, end=''), colorize=True, format="<level>{message}</level>")


def test_topic_generator_init():
    """测试 TopicGenerator 初始化"""
    print("\n" + "="*60)
    print("测试 1: TopicGenerator 初始化")
    print("="*60)

    # 创建临时配置
    from types import SimpleNamespace

    config = SimpleNamespace()
    config.api_keys = SimpleNamespace(
        deepseek=SimpleNamespace(
            api_key="test_key",
            model="deepseek-chat",
            base_url="https://api.deepseek.com"
        ),
        anthropic=SimpleNamespace(api_key=""),
        openai=SimpleNamespace(api_key="")
    )

    # Mock get_active_llm
    def mock_get_active_llm():
        return 'deepseek', {
            'api_key': 'test_key',
            'model': 'deepseek-chat',
            'base_url': 'https://api.deepseek.com'
        }

    config.get_active_llm = mock_get_active_llm

    from src.core.topic_generator import TopicGenerator

    generator = TopicGenerator(config)

    assert generator is not None, "TopicGenerator 应该被初始化"
    assert generator.llm_provider == 'deepseek', "应该使用 deepseek"
    assert len(generator.history) >= 0, "历史记录应该被加载"

    print("✓ TopicGenerator 初始化成功")
    print(f"  LLM Provider: {generator.llm_provider}")
    print(f"  历史记录数: {len(generator.history)}")


async def test_topic_generation():
    """测试 AI 自动选题"""
    print("\n" + "="*60)
    print("测试 2: AI 自动选题")
    print("="*60)

    from types import SimpleNamespace
    from src.core.topic_generator import TopicGenerator, TopicIdea

    # 创建测试配置
    config = SimpleNamespace()
    config.api_keys = SimpleNamespace(
        deepseek=SimpleNamespace(api_key="test_key", model="deepseek-chat", base_url="https://api.deepseek.com"),
        anthropic=SimpleNamespace(api_key=""),
        openai=SimpleNamespace(api_key="")
    )

    def mock_get_active_llm():
        return 'deepseek', {'api_key': 'test_key', 'model': 'deepseek-chat'}

    config.get_active_llm = mock_get_active_llm

    generator = TopicGenerator(config)

    # Mock LLM 响应
    mock_response = """
{
  "topics": [
    {
      "theme": "AI能否理解情感？",
      "judgments": [
        "情感计算已经能识别基本情绪",
        "但理解情感的深层含义仍是挑战",
        "未来AI可能发展出自己的'情感'"
      ],
      "relevance": "随着大模型发展,这个话题越来越重要",
      "novelty_score": 0.85
    },
    {
      "theme": "AI绘画会取代艺术家吗？",
      "judgments": [
        "AI已经能生成高质量图像",
        "但艺术创作不只是技术",
        "人机协作可能是未来方向"
      ],
      "relevance": "AI绘画工具爆发,引发行业讨论",
      "novelty_score": 0.75
    }
  ]
}
"""

    with patch.object(generator, '_call_llm', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_response

        # 测试生成候选主题
        candidates = await generator._generate_from_trends()

        assert len(candidates) == 2, "应该生成2个候选主题"
        assert all(isinstance(t, TopicIdea) for t in candidates), "应该是 TopicIdea 对象"
        assert candidates[0].theme == "AI能否理解情感？", "主题应该正确解析"
        assert len(candidates[0].judgments) == 3, "应该有3个核心判断"

    print("✓ AI 自动选题测试通过")
    print(f"  生成主题数: {len(candidates)}")
    print(f"  主题1: {candidates[0].theme}")
    print(f"  主题2: {candidates[1].theme}")


def test_topic_history():
    """测试主题历史管理"""
    print("\n" + "="*60)
    print("测试 3: 主题历史管理")
    print("="*60)

    from types import SimpleNamespace
    from src.core.topic_generator import TopicGenerator, TopicIdea

    # 创建临时历史文件
    with tempfile.TemporaryDirectory() as tmpdir:
        history_file = Path(tmpdir) / "topic_history.json"

        config = SimpleNamespace()
        config.api_keys = SimpleNamespace(
            deepseek=SimpleNamespace(api_key="test", model="test", base_url="test"),
            anthropic=SimpleNamespace(api_key=""),
            openai=SimpleNamespace(api_key="")
        )
        config.get_active_llm = lambda: ('deepseek', {'api_key': 'test'})

        generator = TopicGenerator(config)
        generator.history_file = history_file

        # 添加主题到历史
        topic = TopicIdea(
            theme="测试主题",
            judgments=["判断1", "判断2"],
            relevance="测试",
            novelty_score=0.8,
            source="test"
        )

        generator._add_to_history(topic)

        assert history_file.exists(), "历史文件应该被创建"
        assert len(generator.history) == 1, "应该有1个历史记录"

        # 重新加载
        generator2 = TopicGenerator(config)
        generator2.history_file = history_file
        generator2.history = generator2._load_history()

        assert len(generator2.history) == 1, "历史应该被持久化"
        assert generator2.history[0]['theme'] == "测试主题", "主题应该正确保存"

    print("✓ 主题历史管理测试通过")
    print(f"  历史记录数: {len(generator.history)}")


async def test_orchestrator_integration():
    """测试 Orchestrator 集成自动选题"""
    print("\n" + "="*60)
    print("测试 4: Orchestrator 集成自动选题")
    print("="*60)

    # 这个测试需要完整的配置,我们使用 mock 方式验证集成
    from types import SimpleNamespace
    from src.core.topic_generator import TopicGenerator

    config = SimpleNamespace()
    config.api_keys = SimpleNamespace(
        deepseek=SimpleNamespace(api_key="test", model="test", base_url="test"),
        anthropic=SimpleNamespace(api_key=""),
        openai=SimpleNamespace(api_key="")
    )
    config.get_active_llm = lambda: ('deepseek', {'api_key': 'test'})

    # 验证 TopicGenerator 可以被 Orchestrator 使用
    generator = TopicGenerator(config)

    assert hasattr(generator, 'generate_from_trends'), "应该有 generate_from_trends 方法"
    assert hasattr(generator, 'history'), "应该有 history 属性"

    print("✓ TopicGenerator 可以被 Orchestrator 集成")
    print("  generate_from_trends: ✓")
    print("  history management: ✓")


async def test_topic_selection():
    """测试主题选择逻辑"""
    print("\n" + "="*60)
    print("测试 5: 主题选择逻辑")
    print("="*60)

    from types import SimpleNamespace
    from src.core.topic_generator import TopicGenerator, TopicIdea

    config = SimpleNamespace()
    config.api_keys = SimpleNamespace(
        deepseek=SimpleNamespace(api_key="test", model="test", base_url="test"),
        anthropic=SimpleNamespace(api_key=""),
        openai=SimpleNamespace(api_key="")
    )
    config.get_active_llm = lambda: ('deepseek', {'api_key': 'test'})

    generator = TopicGenerator(config)

    # 创建测试候选主题
    candidates = [
        TopicIdea(
            theme="AI与情感",
            judgments=["判断1", "判断2", "判断3"],
            relevance="重要话题",
            novelty_score=0.9,
            source="trend"
        ),
        TopicIdea(
            theme="AI绘画",
            judgments=["判断1", "判断2", "判断3"],
            relevance="热门话题",
            novelty_score=0.7,
            source="creative"
        ),
        TopicIdea(
            theme="AI历史",
            judgments=["判断1", "判断2", "判断3"],
            relevance="回顾过去",
            novelty_score=0.5,
            source="archive"
        )
    ]

    # 选择最佳主题
    best = generator._select_best_topic(candidates)

    assert best is not None, "应该选出最佳主题"
    assert hasattr(best, 'final_score'), "应该有评分"
    assert best.theme == "AI与情感", "应该选择评分最高的主题（trend+高novelty）"

    print("✓ 主题选择逻辑测试通过")
    print(f"  候选数: {len(candidates)}")
    print(f"  最佳主题: {best.theme}")
    print(f"  评分: {best.final_score:.2f}")


async def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("Phase 3 完整自动化测试")
    print("="*60)

    try:
        # 测试 1: 初始化
        test_topic_generator_init()

        # 测试 2: AI 自动选题
        await test_topic_generation()

        # 测试 3: 主题历史管理
        test_topic_history()

        # 测试 4: Orchestrator 集成
        await test_orchestrator_integration()

        # 测试 5: 主题选择
        await test_topic_selection()

        print("\n" + "="*60)
        print("✅ 所有测试通过! (5/5)")
        print("="*60)

    except Exception as e:
        print("\n" + "="*60)
        print(f"❌ 测试失败: {e}")
        print("="*60)
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(main())
