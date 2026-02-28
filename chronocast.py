#!/usr/bin/env python3
"""ChronoCast CLI - 超时空电台内容工厂

使用示例:
    # 生成单期内容
    python chronocast.py generate --input episode_input.txt --episode 1
    
    # 启动完整流水线
    python chronocast.py pipeline --input episode_input.txt --episode 1 --mode semi
    
    # 克隆船长声音
    python chronocast.py clone-voice --name captain --samples samples/
    
    # 启动自动化调度
    python chronocast.py scheduler --config config/schedule.yaml
"""
import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from loguru import logger

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.config import get_config, reload_config
from src.core.pipeline import run_pipeline, ContentPipeline
from src.writer.generator import EpisodeInput
from src.voice.synthesizer import VoiceCloner


console = Console()


def print_banner():
    """打印启动画面"""
    banner = Text()
    banner.append("╔══════════════════════════════════════════╗\n", style="cyan")
    banner.append("║     ", style="cyan")
    banner.append("ChronoCast", style="bold yellow")
    banner.append(" · ", style="cyan")
    banner.append("超时空电台", style="bold yellow")
    banner.append("     ║\n", style="cyan")
    banner.append("╠══════════════════════════════════════════╣\n", style="cyan")
    banner.append("║  麦洛与船长的AI内容工厂                  ║\n", style="cyan")
    banner.append("╚══════════════════════════════════════════╝", style="cyan")
    console.print(banner)
    console.print()


@click.group()
@click.option('--config', '-c', type=click.Path(), help='配置文件路径')
@click.option('--verbose', '-v', is_flag=True, help='详细输出')
def cli(config, verbose):
    """ChronoCast - 超时空电台内容工厂"""
    print_banner()
    
    # 加载配置
    if config:
        reload_config(config)
    
    # 设置日志级别
    if verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.remove()
        logger.add(sys.stderr, level="INFO")


@cli.command()
@click.option('--input', '-i', required=True, type=click.Path(exists=True), 
              help='输入文件路径（包含主题和要点）')
@click.option('--episode', '-e', default=1, help='期号')
@click.option('--output', '-o', type=click.Path(), help='输出目录')
def generate(input, episode, output):
    """生成单期文稿"""
    console.print(Panel.fit(f"生成 EP{episode:03d} 文稿", style="blue"))
    
    # 读取输入
    input_text = Path(input).read_text(encoding='utf-8')
    input_data = EpisodeInput.from_text(input_text)
    
    console.print(f"[green]主题:[/green] {input_data.theme}")
    console.print(f"[green]核心观点:[/green]")
    for i, j in enumerate(input_data.core_judgments, 1):
        console.print(f"  {i}. {j}")
    
    # 生成
    async def do_generate():
        from src.writer.generator import ScriptGenerator
        
        generator = ScriptGenerator()
        script = generator.generate(input_data, episode)
        
        # 保存
        if output:
            output_dir = Path(output)
        else:
            config = get_config()
            output_dir = Path(config.storage.output_base) / f"EP{episode:03d}" / "drafts"
        
        script_path = script.save(output_dir)
        
        console.print(f"\n[green]✓[/green] 文稿已生成: {script_path}")
        console.print(f"[dim]标题: {script.title}[/dim]")
        console.print(f"[dim]预计时长: {script.duration_estimate}[/dim]")
        console.print(f"[dim]切片标记: {len(script.clips)} 个[/dim]")
        console.print(f"[dim]金句: {len(script.quotes)} 条[/dim]")
    
    asyncio.run(do_generate())


@cli.command()
@click.option('--input', '-i', required=True, type=click.Path(exists=True),
              help='输入文件路径')
@click.option('--episode', '-e', default=1, help='期号')
@click.option('--mode', '-m', default='semi', 
              type=click.Choice(['manual', 'semi', 'auto']),
              help='运行模式: manual(手动), semi(半自动), auto(全自动)')
def pipeline(input, episode, mode):
    """运行完整内容流水线"""
    console.print(Panel.fit(
        f"启动内容流水线 [EP{episode:03d}] 模式={mode}", 
        style="green"
    ))
    
    # 读取输入
    input_text = Path(input).read_text(encoding='utf-8')
    
    async def do_pipeline():
        result = await run_pipeline(input_text, episode, mode)
        
        console.print("\n" + "="*50)
        if result.success:
            console.print("[bold green]✓ 流水线执行成功[/bold green]")
        else:
            console.print("[bold red]✗ 流水线执行失败[/bold red]")
        
        console.print(f"\n[dim]执行耗时: {result.execution_time:.1f}s[/dim]")
        
        if result.script_path:
            console.print(f"[green]文稿:[/green] {result.script_path}")
        if result.final_audio_path:
            console.print(f"[green]音频:[/green] {result.final_audio_path}")
        if result.full_video_path:
            console.print(f"[green]视频:[/green] {result.full_video_path}")
        if result.clip_paths:
            console.print(f"[green]切片:[/green] {len(result.clip_paths)} 个")
        
        if result.inspection_result:
            inspection = result.inspection_result
            console.print(f"\n[dim]质检得分: {inspection.total_score:.1f}/50[/dim]")
            if inspection.passed:
                console.print("[green]质检通过[/green]")
            else:
                console.print("[yellow]质检未通过[/yellow]")
        
        if result.errors:
            console.print("\n[red]错误:[/red]")
            for err in result.errors:
                console.print(f"  - {err}")
    
    asyncio.run(do_pipeline())


@cli.command()
@click.option('--name', '-n', required=True, help='声音名称（如 captain）')
@click.option('--samples', '-s', required=True, type=click.Path(exists=True),
              help='声音样本目录（3-5个清晰录音文件）')
@click.option('--description', '-d', default='', help='声音描述')
def clone_voice(name, samples, description):
    """克隆声音（用于创建船长音色）"""
    console.print(Panel.fit(f"克隆声音: {name}", style="magenta"))
    
    sample_dir = Path(samples)
    sample_files = list(sample_dir.glob("*.mp3")) + list(sample_dir.glob("*.wav"))
    
    if not sample_files:
        console.print("[red]错误: 未找到音频文件[/red]")
        return
    
    console.print(f"找到 {len(sample_files)} 个样本文件")
    
    async def do_clone():
        cloner = VoiceCloner()
        voice_id = await cloner.clone_voice(
            sample_files[:5],  # 最多5个
            name,
            description or f"Cloned voice for {name}"
        )
        
        console.print(f"\n[green]✓ 声音克隆成功[/green]")
        console.print(f"[dim]Voice ID: {voice_id}[/dim]")
        console.print(f"\n请将此 ID 添加到配置文件中:")
        console.print(f"  characters.{name}.voice_id: {voice_id}")
    
    asyncio.run(do_clone())


@cli.command()
def config():
    """显示当前配置"""
    config = get_config()
    
    console.print(Panel.fit("当前配置", style="blue"))
    
    console.print(f"[bold]项目:[/bold] {config.project.name} ({config.project.chinese_name})")
    console.print(f"[bold]版本:[/bold] {config.project.version}")
    
    try:
        llm_name, llm_config = config.get_active_llm()
        console.print(f"[bold]LLM:[/bold] {llm_name} ({llm_config.model})")
    except ValueError as e:
        console.print(f"[bold]LLM:[/bold] [red]未配置 ({e})[/red]")
    
    try:
        tts_name, tts_config = config.get_active_tts()
        console.print(f"[bold]TTS:[/bold] {tts_name}")
    except ValueError as e:
        console.print(f"[bold]TTS:[/bold] [red]未配置 ({e})[/red]")
    
    console.print(f"[bold]工作模式:[/bold] {config.workflow.mode}")
    console.print(f"[bold]输出目录:[/bold] {config.storage.output_base}")


@cli.command()
def init():
    """初始化项目"""
    console.print(Panel.fit("初始化 ChronoCast", style="green"))
    
    # 创建目录结构
    dirs = [
        "config",
        "assets/voices",
        "assets/bgm",
        "assets/templates",
        "assets/brand",
        "output",
        "logs",
        "data",
    ]
    
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
        console.print(f"[green]✓[/green] {d}/")
    
    # 检查配置文件
    config_file = Path("config/config.yaml")
    if not config_file.exists():
        example = Path("config/config.example.yaml")
        if example.exists():
            console.print(f"\n[yellow]提示:[/yellow] 请复制配置文件:")
            console.print(f"  cp config/config.example.yaml config/config.yaml")
            console.print(f"  然后编辑 config/config.yaml 添加你的 API 密钥")
    
    console.print("\n[green]初始化完成！[/green]")


@cli.command()
@click.option('--daemon', '-d', is_flag=True, help='守护进程模式运行')
@click.option('--once', is_flag=True, help='执行所有待处理任务后退出')
def scheduler(daemon, once):
    """启动自动化调度器"""
    from src.core.orchestrator import ContentOrchestrator

    console.print(Panel.fit(
        "ChronoCast 自动化调度器",
        style="green"
    ))

    orchestrator = ContentOrchestrator()

    if once:
        console.print("[yellow]执行待处理任务模式[/yellow]")
        results = orchestrator.run_pending_tasks()

        console.print(f"\n[dim]执行了 {len(results)} 个任务[/dim]")
        for result in results:
            if result.success:
                console.print(f"[green]✓[/green] 任务 #{result.task_id} 完成")
            else:
                console.print(f"[red]✗[/red] 任务 #{result.task_id} 失败: {result.error}")
    else:
        mode_text = "守护进程模式" if daemon else "前台模式"
        console.print(f"[dim]运行模式: {mode_text}[/dim]")
        console.print("[dim]按 Ctrl+C 停止[/dim]\n")

        orchestrator.start_scheduler(daemon=daemon)


@cli.command()
@click.option('--episode', '-e', required=True, type=int, help='期号')
@click.option('--platforms', '-p', multiple=True, help='平台列表')
def publish(episode, platforms):
    """发布内容到平台"""
    from src.publisher.dispatcher import publish_episode

    console.print(Panel.fit(
        f"发布 EP{episode:03d}",
        style="magenta"
    ))

    if platforms:
        console.print(f"[dim]目标平台: {', '.join(platforms)}[/dim]")
    else:
        console.print(f"[dim]发布到所有启用的平台[/dim]")

    async def do_publish():
        results = await publish_episode(
            episode,
            list(platforms) if platforms else None
        )

        console.print("\n" + "="*50)
        success_count = sum(1 for r in results if r.success)

        if success_count == len(results):
            console.print(f"[bold green]✓ 全部发布成功[/bold green] ({success_count}/{len(results)})")
        else:
            console.print(f"[bold yellow]部分发布成功[/bold yellow] ({success_count}/{len(results)})")

        console.print("\n[bold]发布结果:[/bold]")
        for result in results:
            if result.success:
                console.print(f"  [green]✓[/green] {result.platform}: {result.content_url}")
            else:
                console.print(f"  [red]✗[/red] {result.platform}: {result.error_message}")

    asyncio.run(do_publish())


@cli.command()
@click.option('--episode', '-e', type=int, help='期号')
def collect(episode):
    """收集数据"""
    from src.analytics.collector import DataCollector

    if episode:
        console.print(Panel.fit(f"收集 EP{episode:03d} 数据", style="blue"))
    else:
        console.print(Panel.fit("收集最新数据", style="blue"))

    async def do_collect():
        collector = DataCollector()

        if episode:
            metrics = await collector.collect_all(episode)
        else:
            # 收集最新期号
            from src.core.task_manager import TaskManager
            tm = TaskManager()
            latest_ep = tm.get_latest_episode_number()
            if latest_ep > 0:
                metrics = await collector.collect_all(latest_ep)
            else:
                console.print("[yellow]没有可收集的数据[/yellow]")
                return

        console.print(f"\n[green]✓ 数据收集完成[/green]")
        console.print(f"[dim]总触达: {metrics.total_reach}[/dim]")
        console.print(f"[dim]互动率: {metrics.engagement_rate:.2%}[/dim]")

    asyncio.run(do_collect())


@cli.command()
@click.option('--week', '-w', help='周起始日期 (YYYY-MM-DD)')
def report(week):
    """生成AI周报"""
    from src.analytics.reporter import AIReporter

    console.print(Panel.fit("生成AI周报", style="cyan"))

    async def do_report():
        reporter = AIReporter()

        if week:
            console.print(f"[dim]周期: {week}[/dim]")

        report_path = await reporter.generate_weekly_report(week)

        console.print(f"\n[green]✓ 周报已生成[/green]")
        console.print(f"[dim]路径: {report_path}[/dim]")

    asyncio.run(do_report())


if __name__ == '__main__':
    cli()
