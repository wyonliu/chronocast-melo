"""AI 制片 - 视频生成"""
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple
from dataclasses import dataclass
from loguru import logger

try:
    from moviepy.editor import (
        AudioFileClip, ImageClip, TextClip, CompositeVideoClip,
        concatenate_videoclips, ColorClip
    )
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    logger.warning("moviepy not available, video generation will be limited")

from ..core.config import get_config, Config


@dataclass
class VideoScene:
    """视频场景"""
    speaker: str  # "captain" 或 "melo"
    text: str
    duration: float
    visual_type: str = "avatar"  # avatar / subtitle / image


class VideoGenerator:
    """视频生成器（方案 A：动态可视化风格）"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        
        # 品牌资产路径
        self.assets_dir = Path("assets")
        self.templates_dir = self.assets_dir / "templates"
        self.brand_dir = self.assets_dir / "brand"
        
        # 角色头像
        self.captain_avatar = self.brand_dir / "captain_avatar.png"
        self.melo_avatar = self.brand_dir / "melo_avatar.png"
        
        # 字体
        self.font_path = self.brand_dir / "NotoSansCJK-Regular.ttc"
    
    def generate_full_video(
        self,
        audio_path: Path,
        script_content: str,
        output_path: Path,
        resolution: Tuple[int, int] = (1920, 1080)
    ) -> Path:
        """生成完整视频
        
        Args:
            audio_path: 音频文件路径
            script_content: 文稿内容（用于生成字幕和场景）
            output_path: 输出路径
            resolution: 分辨率 (宽, 高)
            
        Returns:
            Path: 生成的视频路径
        """
        if not MOVIEPY_AVAILABLE:
            raise RuntimeError("moviepy is required for video generation")
        
        logger.info(f"开始生成视频: {output_path.name}")
        
        # 1. 解析文稿获取对话场景
        scenes = self._parse_scenes(script_content)
        
        # 2. 加载音频
        audio = AudioFileClip(str(audio_path))
        total_duration = audio.duration
        
        # 3. 生成视频片段
        video_clips = []
        current_time = 0
        
        for scene in scenes:
            clip = self._create_scene_clip(
                scene, 
                resolution,
                current_time
            )
            video_clips.append(clip)
            current_time += scene.duration
        
        # 4. 合并视频
        video = concatenate_videoclips(video_clips, method="compose")
        video = video.set_audio(audio)
        
        # 5. 添加品牌元素
        video = self._add_branding(video, resolution)
        
        # 6. 导出
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        video.write_videofile(
            str(output_path),
            fps=30,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile='temp-audio.m4a',
            remove_temp=True
        )
        
        logger.info(f"视频生成完成: {output_path}")
        return output_path
    
    def _parse_scenes(self, script_content: str) -> List[VideoScene]:
        """解析文稿为视频场景"""
        scenes = []
        
        for line in script_content.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('船长：') or line.startswith('船长:'):
                text = line[3:].strip()
                # 估算时长（中文约每秒4字）
                duration = max(2, len(text) / 4)
                scenes.append(VideoScene(
                    speaker="captain",
                    text=text,
                    duration=duration
                ))
            
            elif line.startswith('麦洛：') or line.startswith('麦洛:'):
                text = line[3:].strip()
                duration = max(2, len(text) / 4)
                scenes.append(VideoScene(
                    speaker="melo",
                    text=text,
                    duration=duration
                ))
        
        return scenes
    
    def _create_scene_clip(
        self,
        scene: VideoScene,
        resolution: Tuple[int, int],
        start_time: float
    ) -> "ImageClip":
        """创建单个场景片段"""
        width, height = resolution
        
        # 创建背景
        bg = ColorClip(size=resolution, color=(20, 20, 30))
        bg = bg.set_duration(scene.duration)
        
        clips = [bg]
        
        # 添加角色头像（左侧或右侧）
        if scene.speaker == "captain":
            avatar_path = self.captain_avatar
            avatar_pos = (width * 0.15, height * 0.3)
        else:
            avatar_path = self.melo_avatar
            avatar_pos = (width * 0.75, height * 0.3)
        
        if avatar_path.exists():
            avatar = ImageClip(str(avatar_path))
            avatar = avatar.set_duration(scene.duration)
            avatar = avatar.set_position(avatar_pos)
            # 说话时添加发光效果（通过缩放模拟）
            avatar = avatar.resize(height=int(height * 0.25))
            clips.append(avatar)
        
        # 添加字幕
        subtitle = self._create_subtitle(
            scene.text, 
            resolution, 
            scene.duration
        )
        clips.append(subtitle)
        
        # 合成
        composite = CompositeVideoClip(clips)
        return composite
    
    def _create_subtitle(
        self,
        text: str,
        resolution: Tuple[int, int],
        duration: float
    ) -> "TextClip":
        """创建字幕"""
        width, height = resolution
        
        # 文字换行处理
        max_chars = 20
        lines = []
        current_line = ""
        for char in text:
            if len(current_line) >= max_chars:
                lines.append(current_line)
                current_line = char
            else:
                current_line += char
        if current_line:
            lines.append(current_line)
        
        display_text = "\n".join(lines)
        
        # 创建文字片段
        try:
            txt_clip = TextClip(
                display_text,
                fontsize=48,
                color='white',
                font=str(self.font_path) if self.font_path.exists() else 'Arial',
                method='caption',
                size=(width * 0.8, None),
                align='center'
            )
        except:
            # 如果指定字体失败，使用默认
            txt_clip = TextClip(
                display_text,
                fontsize=48,
                color='white',
                method='caption',
                size=(width * 0.8, None),
                align='center'
            )
        
        txt_clip = txt_clip.set_duration(duration)
        txt_clip = txt_clip.set_position(('center', height * 0.7))
        
        return txt_clip
    
    def _add_branding(
        self,
        video: "CompositeVideoClip",
        resolution: Tuple[int, int]
    ) -> "CompositeVideoClip":
        """添加品牌元素"""
        width, height = resolution
        
        # Logo（右上角）
        logo_path = self.brand_dir / "logo.png"
        if logo_path.exists():
            logo = ImageClip(str(logo_path))
            logo = logo.set_duration(video.duration)
            logo = logo.set_position((width * 0.85, height * 0.05))
            logo = logo.resize(height=80)
            video = CompositeVideoClip([video, logo])
        
        # 节目名称（左下角）
        try:
            brand_text = TextClip(
                "ChronoCast · 超时空电台",
                fontsize=24,
                color='gray',
                font=str(self.font_path) if self.font_path.exists() else 'Arial'
            )
        except:
            brand_text = TextClip(
                "ChronoCast · 超时空电台",
                fontsize=24,
                color='gray'
            )
        
        brand_text = brand_text.set_duration(video.duration)
        brand_text = brand_text.set_position((width * 0.05, height * 0.92))
        video = CompositeVideoClip([video, brand_text])
        
        return video
    
    def generate_clip_video(
        self,
        audio_path: Path,
        script_content: str,
        output_path: Path,
        start_sec: float,
        end_sec: float,
        resolution: Tuple[int, int] = (1080, 1920)  # 竖屏
    ) -> Path:
        """生成短视频切片（竖屏）"""
        # 截取音频
        from pydub import AudioSegment
        full_audio = AudioSegment.from_mp3(audio_path)
        start_ms = int(start_sec * 1000)
        end_ms = int(end_sec * 1000)
        clip_audio = full_audio[start_ms:end_ms]
        
        # 临时保存截取后的音频
        temp_audio = output_path.parent / "temp_clip_audio.mp3"
        clip_audio.export(temp_audio, format="mp3")
        
        # 生成视频（使用竖屏布局）
        # 简化为大字幕风格
        video = self._create_short_video(
            str(temp_audio),
            script_content,
            resolution
        )
        
        # 清理临时文件
        temp_audio.unlink(missing_ok=True)
        
        return video
    
    def _create_short_video(
        self,
        audio_path: str,
        script_content: str,
        resolution: Tuple[int, int]
    ) -> Path:
        """创建短视频（大字幕风格）"""
        # 这里简化处理，实际可以使用更复杂的模板
        # 或使用 FFmpeg 直接合成
        
        width, height = resolution
        
        # 创建纯色背景视频
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c=black:s={width}x{height}:d=30",
            "-i", audio_path,
            "-shortest",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            str(output_path)
        ]
        
        subprocess.run(cmd, check=True)
        
        return output_path


def generate_video_from_podcast(
    audio_path: str,
    script_path: str,
    output_path: str
) -> Path:
    """便捷函数：从播客音频生成视频"""
    generator = VideoGenerator()
    
    script_content = Path(script_path).read_text(encoding="utf-8")
    
    return generator.generate_full_video(
        Path(audio_path),
        script_content,
        Path(output_path)
    )


if __name__ == "__main__":
    print("VideoGenerator initialized")
