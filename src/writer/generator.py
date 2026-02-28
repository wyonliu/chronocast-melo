"""AI 编剧 - 对话文稿生成器"""
import re
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from loguru import logger

from ..core.config import get_config, Config


@dataclass
class EpisodeInput:
    """单期节目的输入数据"""
    theme: str  # 主题
    core_judgments: List[str] = field(default_factory=list)  # 核心判断
    mood: str = "兴奋但克制"  # 情绪基调
    reference: str = ""  # 参考素材
    melo_questions: List[str] = field(default_factory=list)  # 想让麦洛问的问题
    special_requests: str = ""  # 特殊要求
    
    @classmethod
    def from_text(cls, text: str) -> "EpisodeInput":
        """从文本解析输入"""
        lines = text.strip().split("\n")
        
        theme = ""
        judgments = []
        mood = "兴奋但克制"
        reference = ""
        questions = []
        
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith("【主题】") or line.startswith("【本期主题】"):
                theme = line.split("】", 1)[-1].strip()
                current_section = None
            elif line.startswith("【核心判断】"):
                current_section = "judgments"
            elif line.startswith("【情绪基调】") or line.startswith("【情绪】"):
                mood = line.split("】", 1)[-1].strip()
                current_section = None
            elif line.startswith("【参考素材】") or line.startswith("【参考】"):
                reference = line.split("】", 1)[-1].strip()
                current_section = None
            elif line.startswith("【想让麦洛问的问题】"):
                current_section = "questions"
            elif line.startswith("【"):
                current_section = None
            elif current_section == "judgments" and line.startswith(("1.", "2.", "3.", "-")):
                judgments.append(line.lstrip("123.- "))
            elif current_section == "questions" and line.startswith(("-", "•")):
                questions.append(line.lstrip("-• "))
        
        return cls(
            theme=theme,
            core_judgments=judgments,
            mood=mood,
            reference=reference,
            melo_questions=questions
        )
    
    def to_prompt(self) -> str:
        """转换为 LLM Prompt 格式"""
        parts = [f"【本期主题】{self.theme}"]
        
        if self.core_judgments:
            parts.append("\n【核心判断】")
            for i, j in enumerate(self.core_judgments, 1):
                parts.append(f"{i}. {j}")
        
        parts.append(f"\n【情绪基调】{self.mood}")
        
        if self.reference:
            parts.append(f"\n【参考素材】{self.reference}")
        
        if self.melo_questions:
            parts.append("\n【想让麦洛问的问题】")
            for q in self.melo_questions:
                parts.append(f"- {q}")
        
        return "\n".join(parts)


@dataclass
class ClipMarker:
    """短视频切片标记"""
    title: str
    start_time: str
    end_time: str
    hook: str


@dataclass
class EpisodeScript:
    """生成的文稿"""
    episode_number: int
    title: str
    theme: str
    content: str
    clips: List[ClipMarker] = field(default_factory=list)
    quotes: List[str] = field(default_factory=list)
    duration_estimate: str = "12-15分钟"
    
    def save(self, output_dir: Path) -> Path:
        """保存文稿到文件"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = output_dir / f"EP{self.episode_number:03d}_script.md"
        
        content = f"""# EP{self.episode_number:03d}：{self.title}

## 元信息
- **主题**：{self.theme}
- **预计时长**：{self.duration_estimate}

## 文稿

{self.content}

## 切片标记

"""
        for i, clip in enumerate(self.clips, 1):
            content += f"""{i}. **{clip.title}**
   - 时间戳：{clip.start_time} - {clip.end_time}
   - 钩子：{clip.hook}

"""
        
        content += "\n## 金句提取\n\n"
        for i, quote in enumerate(self.quotes, 1):
            content += f'{i}. "{quote}"\n'
        
        filepath.write_text(content, encoding="utf-8")
        logger.info(f"文稿已保存: {filepath}")
        return filepath


class ScriptGenerator:
    """文稿生成器"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.system_prompt = self._load_system_prompt()
        self.llm_provider, self.llm_config = self.config.get_active_llm()
    
    def _load_system_prompt(self) -> str:
        """加载 System Prompt"""
        prompt_path = Path("config/writer/system_prompt.md")
        if not prompt_path.exists():
            prompt_path = Path("../config/writer/system_prompt.md")
        
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        else:
            logger.warning("System prompt file not found, using default")
            return self._default_system_prompt()
    
    def _default_system_prompt(self) -> str:
        """默认 System Prompt"""
        return """你是「麦洛与船长的电台」的首席编剧。

节目是一档父女对话体的科技人文播客。船长（爸爸）是一位空间智能和 AI 领域的创业老兵，麦洛（女儿）是一个 10 岁的好奇小孩。

【风格要求】
- 对话必须自然，像真实父女聊天
- 禁止说教感、PPT式罗列
- 鼓励用动漫/游戏类比技术概念

请基于用户输入生成本期完整文稿。"""
    
    def generate(
        self,
        input_data: EpisodeInput,
        episode_number: int = 1,
        max_retries: int = None
    ) -> EpisodeScript:
        """生成文稿
        
        Args:
            input_data: 节目输入数据
            episode_number: 期号
            max_retries: 最大重试次数
            
        Returns:
            EpisodeScript: 生成的文稿
        """
        if max_retries is None:
            max_retries = self.config.content.max_retries
        
        logger.info(f"开始生成 EP{episode_number:03d} 文稿")
        logger.info(f"主题: {input_data.theme}")
        
        # 构建完整 prompt
        user_prompt = f"""期号：EP{episode_number:03d}

{input_data.to_prompt()}

请按照系统设定的格式和风格，生成完整的对话文稿。"""
        
        # 调用 LLM
        content = self._call_llm(self.system_prompt, user_prompt)
        
        # 解析生成结果
        script = self._parse_content(content, episode_number, input_data.theme)
        
        logger.info(f"文稿生成完成: {script.title}")
        return script
    
    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """调用 LLM API"""
        if self.llm_provider == "anthropic":
            return self._call_anthropic(system_prompt, user_prompt)
        elif self.llm_provider == "deepseek":
            return self._call_deepseek(system_prompt, user_prompt)
        elif self.llm_provider == "openai":
            return self._call_openai(system_prompt, user_prompt)
        else:
            raise ValueError(f"Unknown LLM provider: {self.llm_provider}")
    
    def _call_anthropic(self, system_prompt: str, user_prompt: str) -> str:
        """调用 Claude API"""
        import anthropic
        
        client = anthropic.Anthropic(
            api_key=self.llm_config.api_key,
            base_url=self.llm_config.base_url if self.llm_config.base_url else None
        )
        
        response = client.messages.create(
            model=self.llm_config.model or "claude-opus-4-6",
            max_tokens=4000,
            temperature=self.config.content.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        
        return response.content[0].text
    
    def _call_deepseek(self, system_prompt: str, user_prompt: str) -> str:
        """调用 DeepSeek API"""
        from openai import OpenAI
        
        client = OpenAI(
            api_key=self.llm_config.api_key,
            base_url=self.llm_config.base_url or "https://api.deepseek.com"
        )
        
        response = client.chat.completions.create(
            model=self.llm_config.model or "deepseek-chat",
            max_tokens=4000,
            temperature=self.config.content.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        return response.choices[0].message.content
    
    def _call_openai(self, system_prompt: str, user_prompt: str) -> str:
        """调用 OpenAI API"""
        from openai import OpenAI
        
        client = OpenAI(
            api_key=self.llm_config.api_key,
            base_url=self.llm_config.base_url if self.llm_config.base_url else None
        )
        
        response = client.chat.completions.create(
            model=self.llm_config.model or "gpt-4o",
            max_tokens=4000,
            temperature=self.config.content.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        return response.choices[0].message.content
    
    def _parse_content(
        self,
        content: str,
        episode_number: int,
        theme: str
    ) -> EpisodeScript:
        """解析 LLM 返回的内容"""
        # 提取标题
        title_match = re.search(r'# EP\d+：(.+)', content)
        title = title_match.group(1) if title_match else f"第{episode_number}期"
        
        # 提取切片标记
        clips = []
        clip_pattern = r'\[CLIP:(.+?)\](.+?)\[/CLIP\]'
        clip_matches = re.findall(clip_pattern, content, re.DOTALL)
        
        for i, (clip_title, clip_content) in enumerate(clip_matches[:3], 1):
            # 估算时间戳（简化处理）
            start_min = 2 + i * 3
            clips.append(ClipMarker(
                title=clip_title.strip(),
                start_time=f"{start_min}:00",
                end_time=f"{start_min + 1}:00",
                hook=self._extract_hook(clip_content)
            ))
        
        # 清理内容中的切片标记标签
        clean_content = re.sub(r'\[CLIP:.+?\]', '', content)
        clean_content = re.sub(r'\[/CLIP\]', '', clean_content)
        
        # 提取金句（引号内的内容）
        quotes = re.findall(r'["""]([^"""]+)["""]', content)
        quotes = [q for q in quotes if len(q) > 10 and len(q) < 100][:5]
        
        return EpisodeScript(
            episode_number=episode_number,
            title=title,
            theme=theme,
            content=clean_content,
            clips=clips,
            quotes=quotes
        )
    
    def _extract_hook(self, content: str) -> str:
        """从切片内容中提取 hook（开头）"""
        lines = [l.strip() for l in content.strip().split('\n') if l.strip()]
        if lines:
            # 优先取麦洛的话作为 hook
            for line in lines:
                if line.startswith('麦洛：'):
                    return line[3:].strip()[:50]
            return lines[0][:50]
        return "精彩内容"


def generate_script(
    input_text: str,
    episode_number: int = 1,
    output_dir: Optional[str] = None
) -> Path:
    """便捷函数：从文本输入生成文稿"""
    input_data = EpisodeInput.from_text(input_text)
    generator = ScriptGenerator()
    script = generator.generate(input_data, episode_number)
    
    if output_dir:
        return script.save(Path(output_dir))
    else:
        config = get_config()
        return script.save(Path(config.storage.output_base) / "drafts")


if __name__ == "__main__":
    # 测试
    test_input = """
【主题】为什么 AI 眼镜会取代手机
【核心判断】
1. 不是取代，是"隐身"——手机让你低头，眼镜让你抬头
2. 真正的杀手应用不是显示信息，而是"看懂世界"
3. 2028年会有一个iPhone时刻
【情绪基调】兴奋但克制
【参考素材】Meta Orion最新发布会
"""
    
    result = generate_script(test_input, episode_number=1)
    print(f"Generated: {result}")
