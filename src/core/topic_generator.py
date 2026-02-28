"""AI 自动选题生成器

使用 LLM 自动生成节目主题
"""
import json
import random
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from loguru import logger

from .config import Config, get_config
from ..writer.generator import EpisodeInput


@dataclass
class TopicIdea:
    """选题想法"""
    theme: str
    judgments: List[str]
    relevance: str  # 相关性说明
    novelty_score: float  # 新颖度评分 (0-1)
    source: str  # 来源 (trend/archive/creative)


class TopicGenerator:
    """AI 自动选题生成器"""

    def __init__(self, config: Optional[Config] = None):
        """初始化选题生成器

        Args:
            config: 配置对象
        """
        self.config = config or get_config()

        # 初始化 LLM
        self.llm_provider, self.llm_config = self.config.get_active_llm()
        logger.info(f"TopicGenerator 使用 LLM: {self.llm_provider}")

        # 历史主题存储
        self.history_file = Path("data/topic_history.json")
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

        # 加载历史主题
        self.history = self._load_history()

    def _load_history(self) -> List[Dict[str, Any]]:
        """加载历史主题

        Returns:
            List[Dict]: 历史主题列表
        """
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载历史主题失败: {e}")
                return []
        return []

    def _save_history(self) -> None:
        """保存历史主题"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存历史主题失败: {e}")

    def _add_to_history(self, topic: TopicIdea) -> None:
        """添加主题到历史

        Args:
            topic: 选题想法
        """
        self.history.append({
            'theme': topic.theme,
            'date': datetime.now().isoformat(),
            'source': topic.source,
            'novelty_score': topic.novelty_score
        })
        # 只保留最近 50 个
        self.history = self.history[-50:]
        self._save_history()

    async def generate_from_trends(self) -> EpisodeInput:
        """从热点追踪生成主题

        Returns:
            EpisodeInput: 节目输入数据
        """
        logger.info("开始从热点生成节目主题...")

        # 1. 获取候选主题
        candidates = await self._generate_topic_candidates()

        # 2. 评估和筛选
        best_topic = self._select_best_topic(candidates)

        # 3. 生成完整输入
        episode_input = await self._generate_full_input(best_topic)

        # 4. 记录到历史
        self._add_to_history(best_topic)

        logger.info(f"✓ 自动生成主题: {best_topic.theme}")

        return episode_input

    async def _generate_topic_candidates(self) -> List[TopicIdea]:
        """生成候选主题列表

        Returns:
            List[TopicIdea]: 候选主题列表
        """
        candidates = []

        # 1. 从热点生成 (模拟热点追踪)
        trend_topics = await self._generate_from_trends()
        candidates.extend(trend_topics)

        # 2. 从历史归档启发
        archive_topics = await self._generate_from_archives()
        candidates.extend(archive_topics)

        # 3. 创意主题
        creative_topics = await self._generate_creative_topics()
        candidates.extend(creative_topics)

        logger.info(f"生成 {len(candidates)} 个候选主题")

        return candidates

    async def _generate_from_trends(self) -> List[TopicIdea]:
        """从热点生成主题

        Returns:
            List[TopicIdea]: 热点相关主题
        """
        # 构建 prompt
        prompt = self._build_trend_prompt()

        # 调用 LLM
        try:
            response = await self._call_llm(prompt)
            topics = self._parse_topic_response(response, source='trend')
            return topics
        except Exception as e:
            logger.error(f"从热点生成主题失败: {e}")
            return []

    async def _generate_from_archives(self) -> List[TopicIdea]:
        """从历史归档启发新主题

        Returns:
            List[TopicIdea]: 归档启发的主题
        """
        if len(self.history) < 3:
            return []

        # 获取最近的主题
        recent_themes = [h['theme'] for h in self.history[-5:]]

        prompt = f"""作为"ChronoCast 超时空电台"的制作人，基于以下最近讨论的主题，提出1-2个相关但有新角度的主题：

最近主题:
{chr(10).join(f'- {t}' for t in recent_themes)}

要求:
1. 与最近主题有关联，但提供新视角
2. 符合节目定位：麦洛(10岁小女孩)和船长(AI创业者)的对话
3. 适合12分钟音频节目

请以JSON格式返回:
{{
  "topics": [
    {{
      "theme": "主题标题",
      "judgments": ["核心判断1", "核心判断2", "核心判断3"],
      "relevance": "与历史主题的关联性说明",
      "novelty_score": 0.7
    }}
  ]
}}"""

        try:
            response = await self._call_llm(prompt)
            topics = self._parse_topic_response(response, source='archive')
            return topics
        except Exception as e:
            logger.error(f"从归档生成主题失败: {e}")
            return []

    async def _generate_creative_topics(self) -> List[TopicIdea]:
        """生成创意主题

        Returns:
            List[TopicIdea]: 创意主题
        """
        prompt = """作为"ChronoCast 超时空电台"的制作人，提出2个创意节目主题。

节目背景:
- 麦洛: 10岁小女孩，充满好奇，喜欢用动漫/游戏类比
- 船长: AI创业者，擅长用类比解释复杂概念
- 风格: 轻松对话，深入浅出讨论AI技术和未来

主题方向(任选):
1. AI技术的日常应用场景
2. 未来世界的想象
3. 科技伦理问题
4. 有趣的科技历史故事

要求:
1. 适合12分钟音频
2. 有3个核心判断点
3. 既有深度又有趣味性

请以JSON格式返回:
{
  "topics": [
    {
      "theme": "主题标题",
      "judgments": ["核心判断1", "核心判断2", "核心判断3"],
      "relevance": "为什么这个主题有趣且重要",
      "novelty_score": 0.8
    }
  ]
}"""

        try:
            response = await self._call_llm(prompt)
            topics = self._parse_topic_response(response, source='creative')
            return topics
        except Exception as e:
            logger.error(f"生成创意主题失败: {e}")
            return []

    def _build_trend_prompt(self) -> str:
        """构建热点追踪 prompt

        Returns:
            str: Prompt 文本
        """
        # 模拟当前热点 (实际可以接入新闻API)
        current_date = datetime.now().strftime('%Y-%m-%d')

        prompt = f"""作为"ChronoCast 超时空电台"的制作人，基于当前科技热点(截至{current_date})，提出2-3个适合节目的主题。

节目定位:
- 主持人: 麦洛(10岁小女孩) 和 船长(AI创业者)
- 风格: 深入浅出讨论AI和科技趋势
- 时长: 12分钟音频

近期AI领域热点方向:
- AI模型能力突破 (推理、多模态等)
- AI应用落地 (AI搜索、AI助手等)
- AI伦理和安全
- AI与创造力
- AI改变的行业和生活

要求:
1. 主题要有时效性和热度
2. 适合对话形式展开
3. 既有专业深度又通俗易懂
4. 每个主题包含3个核心判断

请以JSON格式返回:
{{
  "topics": [
    {{
      "theme": "主题标题",
      "judgments": ["核心判断1", "核心判断2", "核心判断3"],
      "relevance": "为什么现在讨论这个话题",
      "novelty_score": 0.9
    }}
  ]
}}"""

        return prompt

    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM

        Args:
            prompt: 提示词

        Returns:
            str: LLM 响应
        """
        if self.llm_provider == 'anthropic':
            return await self._call_anthropic(prompt)
        elif self.llm_provider == 'deepseek':
            return await self._call_deepseek(prompt)
        elif self.llm_provider == 'openai':
            return await self._call_openai(prompt)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")

    async def _call_anthropic(self, prompt: str) -> str:
        """调用 Anthropic API

        Args:
            prompt: 提示词

        Returns:
            str: 响应文本
        """
        try:
            from anthropic import AsyncAnthropic

            client = AsyncAnthropic(api_key=self.llm_config['api_key'])

            message = await client.messages.create(
                model=self.llm_config.get('model', 'claude-3-5-sonnet-20241022'),
                max_tokens=2000,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )

            return message.content[0].text

        except Exception as e:
            logger.error(f"Anthropic API 调用失败: {e}")
            raise

    async def _call_deepseek(self, prompt: str) -> str:
        """调用 DeepSeek API

        Args:
            prompt: 提示词

        Returns:
            str: 响应文本
        """
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=self.llm_config['api_key'],
                base_url=self.llm_config.get('base_url', 'https://api.deepseek.com')
            )

            response = await client.chat.completions.create(
                model=self.llm_config.get('model', 'deepseek-chat'),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"DeepSeek API 调用失败: {e}")
            raise

    async def _call_openai(self, prompt: str) -> str:
        """调用 OpenAI API

        Args:
            prompt: 提示词

        Returns:
            str: 响应文本
        """
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=self.llm_config['api_key'])

            response = await client.chat.completions.create(
                model=self.llm_config.get('model', 'gpt-4o'),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"OpenAI API 调用失败: {e}")
            raise

    def _parse_topic_response(self, response: str, source: str) -> List[TopicIdea]:
        """解析 LLM 响应为主题列表

        Args:
            response: LLM 响应文本
            source: 主题来源

        Returns:
            List[TopicIdea]: 主题列表
        """
        try:
            # 尝试提取 JSON
            json_start = response.find('{')
            json_end = response.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)

                topics = []
                for item in data.get('topics', []):
                    topic = TopicIdea(
                        theme=item['theme'],
                        judgments=item['judgments'],
                        relevance=item.get('relevance', ''),
                        novelty_score=item.get('novelty_score', 0.5),
                        source=source
                    )
                    topics.append(topic)

                return topics
            else:
                logger.warning("响应中未找到有效的 JSON")
                return []

        except Exception as e:
            logger.error(f"解析 LLM 响应失败: {e}")
            return []

    def _select_best_topic(self, candidates: List[TopicIdea]) -> TopicIdea:
        """从候选主题中选择最佳主题

        Args:
            candidates: 候选主题列表

        Returns:
            TopicIdea: 最佳主题
        """
        if not candidates:
            raise ValueError("没有可用的候选主题")

        # 评分标准:
        # 1. 新颖度 (novelty_score)
        # 2. 与历史主题的差异性
        # 3. 来源优先级 (trend > creative > archive)

        source_weight = {'trend': 1.2, 'creative': 1.0, 'archive': 0.8}

        for topic in candidates:
            # 计算与历史的相似度 (简化版)
            history_themes = [h['theme'] for h in self.history[-10:]]
            similarity = sum(
                1 for h in history_themes
                if any(word in h for word in topic.theme.split()[:3])
            ) / max(len(history_themes), 1)

            # 综合评分
            topic.final_score = (
                topic.novelty_score * 0.5 +
                (1 - similarity) * 0.3 +
                source_weight[topic.source] * 0.2
            )

        # 选择得分最高的
        best = max(candidates, key=lambda t: getattr(t, 'final_score', 0))

        logger.info(f"最佳主题: {best.theme} (评分: {best.final_score:.2f})")

        return best

    async def _generate_full_input(self, topic: TopicIdea) -> EpisodeInput:
        """基于主题生成完整的节目输入

        Args:
            topic: 选题想法

        Returns:
            EpisodeInput: 节目输入数据
        """
        # 构建标准输入格式
        input_text = f"""【本期主题】{topic.theme}

【核心判断】
{chr(10).join(f'{i+1}. {j}' for i, j in enumerate(topic.judgments))}

【相关性】
{topic.relevance}

【节目要求】
- 时长: 约12分钟
- 风格: 轻松对话，深入浅出
- 麦洛: 提出好奇的问题，用生活化的类比理解
- 船长: 清晰解释概念，分享创业视角

【生成来源】AI自动选题 - {topic.source}
【生成时间】{datetime.now().strftime('%Y-%m-%d %H:%M')}
"""

        # 保存到文件(可选)
        output_file = Path("input") / f"auto_topic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(input_text, encoding='utf-8')

        logger.info(f"✓ 完整输入已保存: {output_file}")

        # 转换为 EpisodeInput
        return EpisodeInput.from_text(input_text)


if __name__ == "__main__":
    # 测试代码
    import asyncio

    logger.info("测试 TopicGenerator")

    async def test():
        # 需要配置 API key
        try:
            generator = TopicGenerator()
            print(f"✓ TopicGenerator 初始化成功")

            # 测试生成主题
            print("\n测试自动生成主题...")
            episode_input = await generator.generate_from_trends()

            print(f"\n✓ 生成成功!")
            print(f"主题: {episode_input.theme}")
            print(f"核心判断: {len(episode_input.judgments)} 个")

        except Exception as e:
            print(f"✗ 测试失败: {e}")
            import traceback
            traceback.print_exc()

    asyncio.run(test())
