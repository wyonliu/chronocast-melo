"""数据监控 - AI 周报生成器

自动分析数据，生成周报，驱动 Prompt 进化
"""
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from loguru import logger

from ..core.config import get_config, Config
from .collector import MetricsDatabase, EpisodeMetrics, DataCollector


@dataclass
class WeeklyReport:
    """周报表"""
    week_start: str
    week_end: str
    episodes: List[int]
    summary: str
    highlights: List[str]
    improvements: List[str]
    next_week_suggestions: List[str]
    raw_data: Dict[str, Any]


class AIReporter:
    """AI 周报生成器"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.db = MetricsDatabase()
        self.llm_provider, self.llm_config = self.config.get_active_llm()
    
    async def generate_weekly_report(
        self,
        week_start: Optional[str] = None
    ) -> WeeklyReport:
        """生成周报
        
        Args:
            week_start: 周开始日期 (YYYY-MM-DD)，默认上周
            
        Returns:
            WeeklyReport: 周报表
        """
        if week_start is None:
            # 默认上周
            today = datetime.now()
            last_monday = today - timedelta(days=today.weekday() + 7)
            week_start = last_monday.strftime("%Y-%m-%d")
        
        week_end = (datetime.strptime(week_start, "%Y-%m-%d") + 
                   timedelta(days=6)).strftime("%Y-%m-%d")
        
        # 获取本周数据
        all_metrics = self.db.get_all_metrics(limit=4)
        week_metrics = [m for m in all_metrics if week_start <= m.date <= week_end]
        
        if not week_metrics:
            logger.warning(f"未找到 {week_start} 到 {week_end} 的数据")
            return WeeklyReport(
                week_start=week_start,
                week_end=week_end,
                episodes=[],
                summary="本周暂无数据",
                highlights=[],
                improvements=[],
                next_week_suggestions=[],
                raw_data={}
            )
        
        # 统计数据
        stats = self._calculate_stats(week_metrics)
        
        # 生成 AI 分析
        analysis = await self._generate_ai_analysis(week_metrics, stats)
        
        report = WeeklyReport(
            week_start=week_start,
            week_end=week_end,
            episodes=[m.episode_number for m in week_metrics],
            summary=analysis.get("summary", ""),
            highlights=analysis.get("highlights", []),
            improvements=analysis.get("improvements", []),
            next_week_suggestions=analysis.get("next_week_suggestions", []),
            raw_data=stats
        )
        
        # 保存报告
        self._save_report(report)
        
        return report
    
    def _calculate_stats(self, metrics: List[EpisodeMetrics]) -> Dict[str, Any]:
        """计算统计数据"""
        if not metrics:
            return {}
        
        total_reach = sum(m.total_reach for m in metrics)
        avg_engagement = sum(m.engagement_rate for m in metrics) / len(metrics)
        
        # 找出最佳内容
        best_episode = max(metrics, key=lambda m: m.total_reach)
        
        # 平台分布
        platform_breakdown = {
            "podcast": sum(m.podcast_plays for m in metrics),
            "bilibili": sum(m.bili_views for m in metrics),
            "short_video": sum(m.short_views for m in metrics),
            "wechat": sum(m.wechat_reads for m in metrics),
        }
        
        return {
            "total_episodes": len(metrics),
            "total_reach": total_reach,
            "avg_reach_per_episode": total_reach / len(metrics),
            "avg_engagement_rate": avg_engagement,
            "best_episode": best_episode.episode_number,
            "best_episode_reach": best_episode.total_reach,
            "platform_breakdown": platform_breakdown,
        }
    
    async def _generate_ai_analysis(
        self,
        metrics: List[EpisodeMetrics],
        stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """使用 AI 生成分析"""
        # 构建分析 Prompt
        prompt = self._build_analysis_prompt(metrics, stats)
        
        # 调用 LLM
        try:
            response = await self._call_llm(prompt)
            return json.loads(response)
        except Exception as e:
            logger.error(f"AI 分析生成失败: {e}")
            return {
                "summary": f"本周发布 {stats.get('total_episodes', 0)} 期内容，总触达 {stats.get('total_reach', 0)}",
                "highlights": [],
                "improvements": ["数据分析暂时不可用"],
                "next_week_suggestions": []
            }
    
    def _build_analysis_prompt(
        self,
        metrics: List[EpisodeMetrics],
        stats: Dict[str, Any]
    ) -> str:
        """构建分析 Prompt"""
        metrics_text = "\n".join([
            f"EP{m.episode_number:03d}: 触达 {m.total_reach}, "
            f"播客 {m.podcast_plays}, B站 {m.bili_views}, "
            f"互动率 {m.engagement_rate:.2%}"
            for m in metrics
        ])
        
        return f"""你是「麦洛与船长的电台」的数据分析师和内容策略顾问。

请分析本周数据，生成周报。

## 原始数据

本周统计 ({stats.get('week_start', '')} 至 {stats.get('week_end', '')}):

{metrics_text}

汇总数据:
- 总期数: {stats.get('total_episodes', 0)}
- 总触达: {stats.get('total_reach', 0)}
- 平均每期触达: {stats.get('avg_reach_per_episode', 0):.0f}
- 平均互动率: {stats.get('avg_engagement_rate', 0):.2%}
- 最佳单期: EP{stats.get('best_episode', 0):03d} (触达 {stats.get('best_episode_reach', 0)})

平台分布:
- 播客: {stats.get('platform_breakdown', {}).get('podcast', 0)}
- B站: {stats.get('platform_breakdown', {}).get('bilibili', 0)}
- 短视频: {stats.get('platform_breakdown', {}).get('short_video', 0)}
- 公众号: {stats.get('platform_breakdown', {}).get('wechat', 0)}

## 输出格式

请以 JSON 格式输出：

```json
{{
  "summary": "本周整体表现一句话总结",
  "highlights": [
    "本周做得好的地方1（数据支撑）",
    "本周做得好的地方2（数据支撑）"
  ],
  "improvements": [
    "需要改进的地方1及建议",
    "需要改进的地方2及建议"
  ],
  "next_week_suggestions": [
    "下周选题建议1",
    "下周选题建议2",
    "内容策略调整建议"
  ]
}}
```

分析要点：
1. 对比历史数据趋势（如果有）
2. 分析不同平台的表现差异
3. 找出内容质量与数据表现的关联
4. 给出可执行的建议，而非泛泛而谈"""
    
    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM"""
        # 简化为使用与编剧相同的 LLM
        if self.llm_provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=self.llm_config.api_key)
            response = client.messages.create(
                model=self.llm_config.model or "claude-3-5-sonnet-20241022",
                max_tokens=2000,
                temperature=0.5,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        else:
            from openai import OpenAI
            client = OpenAI(
                api_key=self.llm_config.api_key,
                base_url=self.llm_config.base_url if self.llm_config.base_url else None
            )
            response = client.chat.completions.create(
                model=self.llm_config.model or "gpt-4o",
                max_tokens=2000,
                temperature=0.5,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
    
    def _save_report(self, report: WeeklyReport):
        """保存周报"""
        report_dir = Path("data/reports")
        report_dir.mkdir(parents=True, exist_ok=True)
        
        report_path = report_dir / f"weekly_report_{report.week_start}.md"
        
        content = f"""# 周报 {report.week_start} ~ {report.week_end}

## 概览

{report.summary}

## 本期内容

{', '.join([f"EP{ep:03d}" for ep in report.episodes])}

## 亮点

"""
        for i, h in enumerate(report.highlights, 1):
            content += f"{i}. {h}\n"
        
        content += "\n## 改进建议\n\n"
        for i, imp in enumerate(report.improvements, 1):
            content += f"{i}. {imp}\n"
        
        content += "\n## 下周建议\n\n"
        for i, sug in enumerate(report.next_week_suggestions, 1):
            content += f"{i}. {sug}\n"
        
        content += f"\n## 原始数据\n\n```json\n{json.dumps(report.raw_data, ensure_ascii=False, indent=2)}\n```\n"
        
        report_path.write_text(content, encoding="utf-8")
        logger.info(f"周报已保存: {report_path}")


def print_report(report: WeeklyReport):
    """打印周报（用于 CLI 展示）"""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    
    console = Console()
    
    console.print(Panel.fit(
        f"周报 {report.week_start} ~ {report.week_end}",
        style="green"
    ))
    
    console.print(f"\n[bold]概览:[/bold] {report.summary}")
    
    console.print(f"\n[bold]本期内容:[/bold] {', '.join([f'EP{ep:03d}' for ep in report.episodes])}")
    
    if report.highlights:
        console.print("\n[bold green]亮点:[/bold green]")
        for h in report.highlights:
            console.print(f"  ✓ {h}")
    
    if report.improvements:
        console.print("\n[bold yellow]改进建议:[/bold yellow]")
        for imp in report.improvements:
            console.print(f"  → {imp}")
    
    if report.next_week_suggestions:
        console.print("\n[bold blue]下周建议:[/bold blue]")
        for sug in report.next_week_suggestions:
            console.print(f"  • {sug}")


if __name__ == "__main__":
    # 测试
    import asyncio
    
    async def test():
        reporter = AIReporter()
        report = await reporter.generate_weekly_report()
        print_report(report)
    
    asyncio.run(test())
