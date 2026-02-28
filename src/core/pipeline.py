"""ChronoCast 核心流水线

内容工厂主控，串联所有模块：
输入 → AI编剧 → AI配音 → AI制片 → 输出
"""
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger

from .config import get_config, Config
from ..writer.generator import ScriptGenerator, EpisodeInput, EpisodeScript
from ..writer.inspector import ScriptInspector, InspectionResult
from ..voice.synthesizer import TTSSynthesizer, AudioSegment
from ..voice.mixer import AudioMixer
from ..studio.video import VideoGenerator


@dataclass
class PipelineResult:
    """流水线执行结果"""
    episode_number: int
    success: bool
    
    # 输出文件
    script_path: Optional[Path] = None
    audio_segments_dir: Optional[Path] = None
    final_audio_path: Optional[Path] = None
    full_video_path: Optional[Path] = None
    clip_paths: List[Path] = field(default_factory=list)
    
    # 执行信息
    inspection_result: Optional[InspectionResult] = None
    errors: List[str] = field(default_factory=list)
    execution_time: float = 0.0


class ContentPipeline:
    """内容生产流水线"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        
        # 初始化各模块
        self.script_generator = ScriptGenerator(self.config)
        self.script_inspector = ScriptInspector(self.config)
        self.tts_synthesizer = TTSSynthesizer(self.config)
        self.audio_mixer = AudioMixer(self.config)
        self.video_generator = VideoGenerator(self.config)
        
        # 输出目录
        self.output_base = Path(self.config.storage.output_base)
    
    async def run(
        self,
        input_data: EpisodeInput,
        episode_number: int,
        mode: str = "semi"
    ) -> PipelineResult:
        """运行完整流水线
        
        Args:
            input_data: 节目输入数据
            episode_number: 期号
            mode: 运行模式 (manual/semi/auto)
            
        Returns:
            PipelineResult: 执行结果
        """
        import time
        start_time = time.time()
        
        result = PipelineResult(episode_number=episode_number, success=False)
        
        # 创建本期输出目录
        episode_dir = self.output_base / f"EP{episode_number:03d}"
        episode_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # ========== Step 1: AI 编剧 ==========
            logger.info(f"=== Step 1: AI 编剧 (EP{episode_number:03d}) ===")
            script = await self._step_writer(input_data, episode_number)
            result.script_path = script.save(episode_dir / "drafts")
            
            # ========== Step 2: 质检 ==========
            logger.info(f"=== Step 2: 文稿质检 ===")
            inspection = await self._step_inspector(script)
            result.inspection_result = inspection
            
            if not inspection.passed:
                if mode == "auto":
                    # 自动模式：尝试重新生成
                    logger.warning("质检未通过，尝试重新生成...")
                    # 可以添加重试逻辑
                else:
                    # 手动/半自动模式：等待人工干预
                    logger.warning("质检未通过，请审阅后决定是否继续")
                    if mode == "manual":
                        result.errors.append("质检未通过，需要人工审阅")
                        return result
            
            # ========== Step 3: AI 配音 ==========
            logger.info(f"=== Step 3: AI 配音 ===")
            segments = await self._step_voice(script, episode_dir)
            result.audio_segments_dir = episode_dir / "audio" / "segments"
            
            # 混音
            final_audio_path = episode_dir / "audio" / f"EP{episode_number:03d}_full.mp3"
            self.audio_mixer.mix_podcast(segments, final_audio_path)
            result.final_audio_path = final_audio_path
            
            # ========== Step 4: AI 制片 ==========
            logger.info(f"=== Step 4: AI 制片 ===")
            
            # 生成完整视频
            full_video_path = episode_dir / "video" / f"EP{episode_number:03d}_full.mp4"
            self.video_generator.generate_full_video(
                final_audio_path,
                script.content,
                full_video_path
            )
            result.full_video_path = full_video_path
            
            # 生成短视频切片
            clip_paths = await self._step_clips(script, final_audio_path, episode_dir)
            result.clip_paths = clip_paths
            
            # 成功
            result.success = True
            
        except Exception as e:
            logger.exception("流水线执行失败")
            result.errors.append(str(e))
        
        finally:
            result.execution_time = time.time() - start_time
            logger.info(f"流水线执行完成，耗时: {result.execution_time:.1f}s")
        
        return result
    
    async def _step_writer(
        self,
        input_data: EpisodeInput,
        episode_number: int
    ) -> EpisodeScript:
        """Step 1: AI 编剧"""
        max_retries = self.config.content.max_retries
        
        for attempt in range(max_retries + 1):
            try:
                script = self.script_generator.generate(
                    input_data,
                    episode_number
                )
                return script
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"生成失败，重试 {attempt + 1}/{max_retries}: {e}")
                else:
                    raise
    
    async def _step_inspector(
        self,
        script: EpisodeScript
    ) -> InspectionResult:
        """Step 2: 文稿质检"""
        return self.script_inspector.inspect(script)
    
    async def _step_voice(
        self,
        script: EpisodeScript,
        episode_dir: Path
    ) -> List[AudioSegment]:
        """Step 3: AI 配音"""
        # 解析对话
        dialogue_lines = self.tts_synthesizer.parse_script(script.content)
        
        # 合成音频
        segments_dir = episode_dir / "audio" / "segments"
        segments = await self.tts_synthesizer.synthesize_dialogue(
            dialogue_lines,
            segments_dir,
            script.episode_number
        )
        
        return segments
    
    async def _step_clips(
        self,
        script: EpisodeScript,
        audio_path: Path,
        episode_dir: Path
    ) -> List[Path]:
        """生成短视频切片"""
        clip_paths = []
        clips_dir = episode_dir / "video" / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)
        
        for i, clip_marker in enumerate(script.clips, 1):
            # 解析时间戳
            start_sec = self._parse_timestamp(clip_marker.start_time)
            end_sec = self._parse_timestamp(clip_marker.end_time)
            
            # 如果解析失败，使用估算
            if start_sec is None or end_sec is None:
                # 根据切片索引估算时间
                start_sec = 2 + i * 3 * 60  # 每3分钟一个切片
                end_sec = start_sec + 45
            
            # 生成切片视频
            clip_path = clips_dir / f"clip_{i:02d}.mp4"
            try:
                self.video_generator.generate_clip_video(
                    audio_path,
                    script.content,
                    clip_path,
                    start_sec,
                    end_sec
                )
                clip_paths.append(clip_path)
            except Exception as e:
                logger.error(f"生成切片 {i} 失败: {e}")
        
        return clip_paths
    
    def _parse_timestamp(self, timestamp: str) -> Optional[float]:
        """解析时间戳 MM:SS 或 HH:MM:SS"""
        try:
            parts = timestamp.split(':')
            if len(parts) == 2:
                m, s = map(int, parts)
                return m * 60 + s
            elif len(parts) == 3:
                h, m, s = map(int, parts)
                return h * 3600 + m * 60 + s
        except:
            pass
        return None


async def run_pipeline(
    input_text: str,
    episode_number: int = 1,
    mode: str = "semi"
) -> PipelineResult:
    """便捷函数：运行流水线
    
    Args:
        input_text: 输入文本
        episode_number: 期号
        mode: 运行模式 (manual/semi/auto)
        
    Returns:
        PipelineResult: 执行结果
    """
    input_data = EpisodeInput.from_text(input_text)
    pipeline = ContentPipeline()
    return await pipeline.run(input_data, episode_number, mode)


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
    
    async def test():
        result = await run_pipeline(test_input, episode_number=1, mode="semi")
        print(f"Success: {result.success}")
        print(f"Script: {result.script_path}")
        print(f"Audio: {result.final_audio_path}")
        print(f"Video: {result.full_video_path}")
    
    asyncio.run(test())
