"""AI 配音 - 语音合成器"""
import re
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field
from loguru import logger
import httpx

from ..core.config import get_config, Config


@dataclass
class DialogueLine:
    """对话行"""
    speaker: str  # "captain" 或 "melo"
    text: str
    emotion: Optional[str] = None
    pause_before: float = 0.0  # 前停顿（秒）


@dataclass
class AudioSegment:
    """音频片段"""
    speaker: str
    text: str
    audio_path: Path
    duration: float


class TTSSynthesizer:
    """TTS 合成器"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.tts_provider, self.tts_config = self.config.get_active_tts()
        
        # 角色音色配置
        self.voice_configs = {
            "captain": {
                "voice_id": self.config.characters.get("captain", {}).voice_id 
                           if "captain" in self.config.characters else "captain_cloned",
                "speed": self.config.voice.captain_speed,
                "emotion": self.config.voice.captain_emotion,
            },
            "melo": {
                "voice_id": self.config.characters.get("melo", {}).voice_id 
                           if "melo" in self.config.characters else "melo_child",
                "speed": self.config.voice.melo_speed,
                "emotion": self.config.voice.melo_emotion,
            }
        }
    
    def parse_script(self, script_content: str) -> List[DialogueLine]:
        """从文稿解析对话行"""
        lines = []
        
        for line in script_content.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # 解析船长台词
            if line.startswith('船长：') or line.startswith('船长:'):
                text = line[3:].strip()
                # 去除动作描述 [轻笑] 等
                text = re.sub(r'\[.+?\]', '', text).strip()
                if text:
                    lines.append(DialogueLine(
                        speaker="captain",
                        text=text,
                        emotion=self._detect_emotion(line)
                    ))
            
            # 解析麦洛台词
            elif line.startswith('麦洛：') or line.startswith('麦洛:'):
                text = line[3:].strip()
                text = re.sub(r'\[.+?\]', '', text).strip()
                if text:
                    lines.append(DialogueLine(
                        speaker="melo",
                        text=text,
                        emotion=self._detect_emotion(line)
                    ))
        
        logger.info(f"解析到 {len(lines)} 行对话")
        return lines
    
    def _detect_emotion(self, line: str) -> Optional[str]:
        """检测情绪标记"""
        if '[轻笑]' in line or '[笑]' in line:
            return "happy"
        elif '[叹气]' in line or '[低声]' in line:
            return "sad"
        elif '[兴奋]' in line:
            return "excited"
        elif '[思考]' in line:
            return "thinking"
        return None
    
    async def synthesize_dialogue(
        self,
        dialogue_lines: List[DialogueLine],
        output_dir: Path,
        episode_number: int
    ) -> List[AudioSegment]:
        """合成对话音频
        
        Args:
            dialogue_lines: 对话行列表
            output_dir: 输出目录
            episode_number: 期号
            
        Returns:
            List[AudioSegment]: 音频片段列表
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        segments = []
        
        logger.info(f"开始合成 {len(dialogue_lines)} 段对话音频")
        
        for i, line in enumerate(dialogue_lines):
            output_path = output_dir / f"segment_{i:03d}_{line.speaker}.mp3"
            
            try:
                duration = await self._synthesize_line(line, output_path)
                segments.append(AudioSegment(
                    speaker=line.speaker,
                    text=line.text,
                    audio_path=output_path,
                    duration=duration
                ))
                logger.debug(f"合成完成 [{i+1}/{len(dialogue_lines)}]: {line.text[:30]}...")
            except Exception as e:
                logger.error(f"合成失败 [{i+1}]: {e}")
                raise
        
        logger.info(f"对话音频合成完成: {len(segments)} 段")
        return segments
    
    async def _synthesize_line(
        self,
        line: DialogueLine,
        output_path: Path
    ) -> float:
        """合成单句"""
        if self.tts_provider == "fish_audio":
            return await self._synthesize_fish_audio(line, output_path)
        elif self.tts_provider == "minimax":
            return await self._synthesize_minimax(line, output_path)
        elif self.tts_provider == "elevenlabs":
            return await self._synthesize_elevenlabs(line, output_path)
        else:
            raise ValueError(f"Unknown TTS provider: {self.tts_provider}")
    
    async def _synthesize_fish_audio(
        self,
        line: DialogueLine,
        output_path: Path
    ) -> float:
        """使用 Fish Audio API 合成"""
        voice_config = self.voice_configs[line.speaker]
        
        headers = {
            "Authorization": f"Bearer {self.tts_config.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "text": line.text,
            "reference_id": voice_config["voice_id"],
            "format": "mp3",
            "speed": voice_config["speed"],
        }
        
        if line.emotion:
            payload["emotion"] = line.emotion
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.tts_config.base_url or 'https://api.fish.audio'}/v1/tts",
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            # 保存音频
            output_path.write_bytes(response.content)
        
        # 估算时长 (粗略计算: 中文约每秒 4 字)
        duration = len(line.text) / 4 * voice_config["speed"]
        return duration
    
    async def _synthesize_minimax(
        self,
        line: DialogueLine,
        output_path: Path
    ) -> float:
        """使用 Minimax TTS API 合成"""
        voice_config = self.voice_configs[line.speaker]
        
        headers = {
            "Authorization": f"Bearer {self.tts_config.api_key}",
            "Content-Type": "application/json"
        }
        
        # Minimax 语音合成 API 格式
        payload = {
            "model": "speech-01",
            "text": line.text,
            "voice_setting": {
                "voice_id": voice_config["voice_id"],
                "speed": voice_config["speed"],
            },
            "audio_setting": {
                "format": "mp3",
                "sample_rate": 32000
            }
        }
        
        if hasattr(self.tts_config, 'group_id') and self.tts_config.group_id:
            url = f"https://api.minimax.chat/v1/t2a_pro?GroupId={self.tts_config.group_id}"
        else:
            url = "https://api.minimax.chat/v1/t2a_pro"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            # 假设返回 base64 编码的音频
            import base64
            audio_data = base64.b64decode(result["data"]["audio"])
            output_path.write_bytes(audio_data)
        
        duration = len(line.text) / 4 * voice_config["speed"]
        return duration
    
    async def _synthesize_elevenlabs(
        self,
        line: DialogueLine,
        output_path: Path
    ) -> float:
        """使用 ElevenLabs API 合成"""
        voice_config = self.voice_configs[line.speaker]
        
        headers = {
            "xi-api-key": self.tts_config.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "text": line.text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "speed": voice_config["speed"]
            }
        }
        
        voice_id = voice_config["voice_id"]
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            output_path.write_bytes(response.content)
        
        duration = len(line.text) / 4 * voice_config["speed"]
        return duration


class VoiceCloner:
    """声音克隆工具"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.tts_provider, self.tts_config = self.config.get_active_tts()
    
    async def clone_voice(
        self,
        audio_samples: List[Path],
        voice_name: str,
        description: str = ""
    ) -> str:
        """克隆声音
        
        Args:
            audio_samples: 声音样本文件列表（3-5分钟清晰录音）
            voice_name: 声音名称
            description: 声音描述
            
        Returns:
            str: 克隆后的 voice_id
        """
        if self.tts_provider == "fish_audio":
            return await self._clone_fish_audio(audio_samples, voice_name, description)
        elif self.tts_provider == "elevenlabs":
            return await self._clone_elevenlabs(audio_samples, voice_name, description)
        else:
            raise NotImplementedError(f"Voice cloning not supported for {self.tts_provider}")
    
    async def _clone_fish_audio(
        self,
        audio_samples: List[Path],
        voice_name: str,
        description: str
    ) -> str:
        """使用 Fish Audio 克隆声音"""
        headers = {
            "Authorization": f"Bearer {self.tts_config.api_key}"
        }
        
        # 准备文件
        files = []
        for sample in audio_samples[:5]:  # 最多5个样本
            files.append(("files", (sample.name, sample.read_bytes(), "audio/mpeg")))
        
        data = {
            "name": voice_name,
            "description": description or f"Cloned voice for {voice_name}"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.tts_config.base_url or 'https://api.fish.audio'}/v1/voices",
                headers=headers,
                data=data,
                files=files,
                timeout=120
            )
            response.raise_for_status()
            
            result = response.json()
            voice_id = result["id"]
            logger.info(f"声音克隆成功: {voice_name} -> {voice_id}")
            return voice_id
    
    async def _clone_elevenlabs(
        self,
        audio_samples: List[Path],
        voice_name: str,
        description: str
    ) -> str:
        """使用 ElevenLabs 克隆声音"""
        headers = {
            "xi-api-key": self.tts_config.api_key
        }
        
        files = []
        for sample in audio_samples:
            files.append(("files", (sample.name, sample.read_bytes(), "audio/mpeg")))
        
        data = {
            "name": voice_name,
            "description": description or f"Cloned voice for {voice_name}"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.elevenlabs.io/v1/voices/add",
                headers=headers,
                data=data,
                files=files,
                timeout=120
            )
            response.raise_for_status()
            
            result = response.json()
            voice_id = result["voice_id"]
            logger.info(f"声音克隆成功: {voice_name} -> {voice_id}")
            return voice_id


async def synthesize_podcast(
    script_content: str,
    output_dir: str,
    episode_number: int
) -> List[AudioSegment]:
    """便捷函数：合成播客音频"""
    synthesizer = TTSSynthesizer()
    dialogue_lines = synthesizer.parse_script(script_content)
    return await synthesizer.synthesize_dialogue(
        dialogue_lines,
        Path(output_dir),
        episode_number
    )


if __name__ == "__main__":
    # 测试
    test_script = """
船长：你可以这样理解，AI眼镜不是要取代手机，而是让技术"消失"。
麦洛：消失？那怎么看东西呀？
船长：[轻笑]我是说，好的技术会让你忘记它的存在。
"""
    
    async def test():
        segments = await synthesize_podcast(test_script, "./output/test_audio", 1)
        for seg in segments:
            print(f"{seg.speaker}: {seg.audio_path} ({seg.duration:.1f}s)")
    
    asyncio.run(test())
