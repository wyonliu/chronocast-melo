"""AI 配音 - 混音/后期处理"""
import os
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from loguru import logger

try:
    from pydub import AudioSegment
    from pydub.effects import normalize
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    logger.warning("pydub not available, audio mixing will be limited")

from ..core.config import get_config, Config
from .synthesizer import AudioSegment


@dataclass
class MixConfig:
    """混音配置"""
    bgm_volume: float = 0.15  # 背景音乐音量
    intro_duration: int = 3  # 片头音乐秒数
    outro_duration: int = 5  # 片尾音乐秒数
    target_lufs: float = -16  # 目标响度（播客标准）
    fade_in_ms: int = 500  # 淡入毫秒
    fade_out_ms: int = 1000  # 淡出毫秒
    crossfade_ms: int = 300  # 交叉淡化毫秒


class AudioMixer:
    """音频混音器"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.mix_config = MixConfig(
            bgm_volume=self.config.voice.bgm_volume
        )
        
        # BGM 路径
        self.bgm_dir = Path("assets/bgm")
        self.intro_bgm = self.bgm_dir / "intro.mp3"
        self.main_bgm = self.bgm_dir / "main.mp3"
        self.outro_bgm = self.bgm_dir / "outro.mp3"
    
    def mix_podcast(
        self,
        segments: List[AudioSegment],
        output_path: Path,
        with_bgm: bool = True
    ) -> Path:
        """混音播客
        
        Args:
            segments: 音频片段列表
            output_path: 输出路径
            with_bgm: 是否添加背景音乐
            
        Returns:
            Path: 混音后的文件路径
        """
        if not PYDUB_AVAILABLE:
            raise RuntimeError("pydub is required for audio mixing")
        
        logger.info(f"开始混音，共 {len(segments)} 段音频")
        
        # 1. 合并对话片段
        mixed = self._merge_dialogue(segments)
        
        # 2. 标准化响度
        mixed = normalize(mixed)
        
        # 3. 添加背景音乐（如果需要）
        if with_bgm:
            mixed = self._add_background_music(mixed)
        
        # 4. 添加片头片尾
        mixed = self._add_intros_outros(mixed, with_bgm)
        
        # 5. 最终处理
        mixed = self._final_process(mixed)
        
        # 6. 导出
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        mixed.export(
            output_path,
            format="mp3",
            bitrate="192k",
            tags={
                'artist': 'ChronoCast · 超时空电台',
                'album': '麦洛与船长的电台',
                'genre': 'Technology/Podcast'
            }
        )
        
        duration_sec = len(mixed) / 1000
        logger.info(f"混音完成: {output_path} ({duration_sec:.1f}s)")
        
        return output_path
    
    def _merge_dialogue(self, segments: List[AudioSegment]) -> AudioSegment:
        """合并对话片段"""
        mixed = AudioSegment.empty()
        
        for i, seg in enumerate(segments):
            audio = AudioSegment.from_mp3(seg.audio_path)
            
            # 添加短暂的停顿（模拟真实对话节奏）
            if i > 0:
                pause = AudioSegment.silent(duration=300)  # 300ms 停顿
                mixed += pause
            
            # 淡入
            audio = audio.fade_in(self.mix_config.fade_in_ms)
            
            mixed += audio
        
        return mixed
    
    def _add_background_music(self, dialogue: AudioSegment) -> AudioSegment:
        """添加背景音乐"""
        if not self.main_bgm.exists():
            logger.warning(f"BGM file not found: {self.main_bgm}")
            return dialogue
        
        # 加载背景音乐
        bgm = AudioSegment.from_mp3(self.main_bgm)
        
        # 调整音量
        bgm = bgm - int(20 * (1 - self.mix_config.bgm_volume))
        
        # 循环背景音乐以匹配对话长度
        dialogue_duration = len(dialogue)
        while len(bgm) < dialogue_duration:
            bgm += bgm
        
        # 裁剪到对话长度
        bgm = bgm[:dialogue_duration]
        
        # 背景音乐淡入淡出
        bgm = bgm.fade_in(2000).fade_out(3000)
        
        # 混合（背景音乐作为底层）
        mixed = bgm.overlay(dialogue)
        
        return mixed
    
    def _add_intros_outros(
        self,
        main_audio: AudioSegment,
        with_bgm: bool
    ) -> AudioSegment:
        """添加片头片尾"""
        result = main_audio
        
        # 片头
        if self.intro_bgm.exists():
            intro = AudioSegment.from_mp3(self.intro_bgm)
            # 使用片头前3秒作为开场
            intro = intro[:self.mix_config.intro_duration * 1000]
            intro = intro.fade_out(500)
            result = intro + result
        
        # 片尾
        if self.outro_bgm.exists():
            outro = AudioSegment.from_mp3(self.outro_bgm)
            outro = outro[:self.mix_config.outro_duration * 1000]
            outro = outro.fade_in(500)
            result = result + outro
        
        return result
    
    def _final_process(self, audio: AudioSegment) -> AudioSegment:
        """最终处理"""
        # 整体淡入淡出
        audio = audio.fade_in(500).fade_out(self.mix_config.fade_out_ms)
        
        # 再次标准化
        audio = normalize(audio)
        
        return audio
    
    def create_short_clip(
        self,
        full_audio_path: Path,
        start_sec: float,
        end_sec: float,
        output_path: Path,
        add_subtitle_hint: bool = True
    ) -> Path:
        """创建短视频切片
        
        Args:
            full_audio_path: 完整音频路径
            start_sec: 开始时间（秒）
            end_sec: 结束时间（秒）
            output_path: 输出路径
            add_subtitle_hint: 是否添加字幕提示音
        """
        if not PYDUB_AVAILABLE:
            raise RuntimeError("pydub is required")
        
        audio = AudioSegment.from_mp3(full_audio_path)
        
        # 截取片段
        start_ms = int(start_sec * 1000)
        end_ms = int(end_sec * 1000)
        clip = audio[start_ms:end_ms]
        
        # 添加快节奏的开场音效（用于短视频）
        if add_subtitle_hint:
            # 可以添加一个短音效作为提示
            pass
        
        # 增强响度（短视频需要更响）
        clip = clip + 3  # +3dB
        
        # 导出
        output_path.parent.mkdir(parents=True, exist_ok=True)
        clip.export(output_path, format="mp3", bitrate="192k")
        
        logger.info(f"切片导出: {output_path} ({(end_sec - start_sec):.1f}s)")
        return output_path


def mix_podcast_audio(
    segments: List[AudioSegment],
    output_path: str,
    with_bgm: bool = True
) -> Path:
    """便捷函数：混音播客"""
    mixer = AudioMixer()
    return mixer.mix_podcast(segments, Path(output_path), with_bgm)


if __name__ == "__main__":
    # 测试
    from .synthesizer import AudioSegment
    
    test_segments = [
        AudioSegment("captain", "测试音频1", Path("test1.mp3"), 5.0),
        AudioSegment("melo", "测试音频2", Path("test2.mp3"), 3.0),
    ]
    
    # 注意：这只是一个示例，实际测试需要真实的音频文件
    print("AudioMixer initialized")
