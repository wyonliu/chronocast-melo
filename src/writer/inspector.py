"""AI 编剧 - 文稿质检器"""
import json
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field
from loguru import logger

from ..core.config import get_config, Config
from .generator import EpisodeScript


@dataclass
class DimensionScore:
    """维度评分"""
    name: str
    score: int  # 0-10
    weight: float
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    
    @property
    def weighted_score(self) -> float:
        return self.score * self.weight


@dataclass
class InspectionResult:
    """质检结果"""
    passed: bool
    total_score: float
    dimensions: List[DimensionScore]
    critical_issues: List[str]
    revision_guide: str
    
    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "total_score": self.total_score,
            "dimensions": [
                {
                    "name": d.name,
                    "score": d.score,
                    "weight": d.weight,
                    "issues": d.issues,
                    "suggestions": d.suggestions
                }
                for d in self.dimensions
            ],
            "critical_issues": self.critical_issues,
            "revision_guide": self.revision_guide
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class ScriptInspector:
    """文稿质检器"""
    
    # 评分维度权重
    DIMENSION_WEIGHTS = {
        "character_consistency": 0.20,
        "dialogue_naturalness": 0.20,
        "structure_completeness": 0.20,
        "content_quality": 0.25,
        "style_compliance": 0.15
    }
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.system_prompt = self._load_inspector_prompt()
        self.llm_provider, self.llm_config = self.config.get_active_llm()
    
    def _load_inspector_prompt(self) -> str:
        """加载质检 Prompt"""
        prompt_path = Path("config/writer/inspector_prompt.md")
        if not prompt_path.exists():
            prompt_path = Path("../config/writer/inspector_prompt.md")
        
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        else:
            logger.warning("Inspector prompt file not found, using default")
            return self._default_inspector_prompt()
    
    def _default_inspector_prompt(self) -> str:
        """默认质检 Prompt"""
        return """你是「麦洛与船长的电台」的资深内容质检官。

请从以下维度评估文稿质量：
1. 人设一致性（船长是否在说教？麦洛是否太成熟？）
2. 对话自然度（是否像真实对话？）
3. 结构完整性（开场、主体、电台时刻、预告是否齐全？）
4. 内容质量（是否有金句和硬核洞察？）
5. 风格合规（是否有PPT式罗列？）

请以 JSON 格式输出评分结果。"""
    
    def inspect(self, script: EpisodeScript) -> InspectionResult:
        """质检文稿"""
        logger.info(f"开始质检 EP{script.episode_number:03d}")
        
        # 构建质检 prompt
        user_prompt = self._build_inspection_prompt(script)
        
        # 调用 LLM
        response = self._call_llm(self.system_prompt, user_prompt)
        
        # 解析结果
        result = self._parse_response(response)
        
        if result.passed:
            logger.info(f"质检通过，总分: {result.total_score:.1f}")
        else:
            logger.warning(f"质检未通过，总分: {result.total_score:.1f}")
            logger.warning(f"关键问题: {result.critical_issues}")
        
        return result
    
    def _build_inspection_prompt(self, script: EpisodeScript) -> str:
        """构建质检请求"""
        return f"""请质检以下文稿：

## 文稿内容

{script.content}

## 角色设定

**船长**：空间智能和AI领域的创业老兵，语气沉稳、克制、偶尔幽默，喜欢用类比解释复杂概念，禁止说教。

**麦洛**：10岁女孩，好奇、活泼、喜欢用动漫/游戏类比，洞察来自直觉而非知识储备。

## 节目结构要求

1. 冷开场（30-60秒）：生活化场景引入
2. 核心对话（8-10分钟）：3-4轮交锋
3. 电台时刻（1-2分钟）：有温度的情感升华
4. 下期预告（15-30秒）

## 风格铁律

- ✅ 必须：对话自然、有打断笑声、用类比、口语化
- ❌ 禁止：说教感、PPT式罗列（首先其次再次）、过度书面语

## 输出格式

请以严格的 JSON 格式输出：

```json
{{
  "passed": true/false,
  "total_score": 45,
  "dimensions": {{
    "character_consistency": {{"score": 9, "issues": [], "suggestions": []}},
    "dialogue_naturalness": {{"score": 8, "issues": [], "suggestions": []}},
    "structure_completeness": {{"score": 9, "issues": [], "suggestions": []}},
    "content_quality": {{"score": 9, "issues": [], "suggestions": []}},
    "style_compliance": {{"score": 10, "issues": [], "suggestions": []}}
  }},
  "critical_issues": ["如果有"],
  "revision_guide": "修改建议"
}}
```

通过标准：总分 ≥ 40 分，且各项 ≥ 6 分。"""
    
    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """调用 LLM"""
        if self.llm_provider == "anthropic":
            return self._call_anthropic(system_prompt, user_prompt)
        elif self.llm_provider in ["deepseek", "openai"]:
            return self._call_openai_compatible(system_prompt, user_prompt)
        else:
            raise ValueError(f"Unknown LLM provider: {self.llm_provider}")
    
    def _call_anthropic(self, system_prompt: str, user_prompt: str) -> str:
        """调用 Claude API"""
        import anthropic
        
        client = anthropic.Anthropic(api_key=self.llm_config.api_key)
        
        response = client.messages.create(
            model=self.llm_config.model or "claude-3-5-sonnet-20241022",
            max_tokens=2000,
            temperature=0.3,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        
        return response.content[0].text
    
    def _call_openai_compatible(self, system_prompt: str, user_prompt: str) -> str:
        """调用 OpenAI 兼容 API"""
        from openai import OpenAI
        
        client = OpenAI(
            api_key=self.llm_config.api_key,
            base_url=self.llm_config.base_url if self.llm_config.base_url else None
        )
        
        response = client.chat.completions.create(
            model=self.llm_config.model or "gpt-4o",
            max_tokens=2000,
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        return response.choices[0].message.content
    
    def _parse_response(self, response: str) -> InspectionResult:
        """解析 LLM 响应"""
        try:
            # 提取 JSON
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()
            
            data = json.loads(json_str)
            
            # 解析维度评分
            dimensions = []
            raw_dims = data.get("dimensions", {})
            
            for dim_name, weight in self.DIMENSION_WEIGHTS.items():
                dim_data = raw_dims.get(dim_name, {})
                dimensions.append(DimensionScore(
                    name=dim_name,
                    score=dim_data.get("score", 5),
                    weight=weight,
                    issues=dim_data.get("issues", []),
                    suggestions=dim_data.get("suggestions", [])
                ))
            
            # 计算总分
            total_score = sum(d.weighted_score for d in dimensions) * 10
            
            # 判断是否通过
            passed = data.get("passed", False)
            min_score = min(d.score for d in dimensions)
            
            if not passed and total_score >= 40 and min_score >= 6:
                passed = True
            
            return InspectionResult(
                passed=passed,
                total_score=total_score,
                dimensions=dimensions,
                critical_issues=data.get("critical_issues", []),
                revision_guide=data.get("revision_guide", "")
            )
            
        except Exception as e:
            logger.error(f"解析质检结果失败: {e}")
            # 返回默认失败结果
            return InspectionResult(
                passed=False,
                total_score=0,
                dimensions=[],
                critical_issues=[f"解析失败: {e}"],
                revision_guide="请检查 LLM 输出格式"
            )


def inspect_script(script: EpisodeScript) -> InspectionResult:
    """便捷函数：质检文稿"""
    inspector = ScriptInspector()
    return inspector.inspect(script)


if __name__ == "__main__":
    # 测试
    from .generator import EpisodeScript
    
    test_script = EpisodeScript(
        episode_number=1,
        title="测试文稿",
        theme="AI眼镜",
        content="麦洛：爸爸，为什么...\n船长：你可以这样理解..."
    )
    
    result = inspect_script(test_script)
    print(result.to_json())
