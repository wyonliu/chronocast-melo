"""配置管理模块"""
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


class CharacterConfig(BaseModel):
    """角色配置"""
    name: str
    english_name: str
    age: int
    role: str
    personality: str
    catchphrases: list[str] = []
    voice_id: str


class LLMConfig(BaseModel):
    """LLM API 配置"""
    api_key: str = ""
    model: str = ""
    base_url: str = ""


class TTSConfig(BaseModel):
    """TTS API 配置"""
    api_key: str = ""
    base_url: str = ""
    voice_id: Optional[str] = None


class APIKeys(BaseModel):
    """API 密钥配置"""
    anthropic: LLMConfig = Field(default_factory=LLMConfig)
    deepseek: LLMConfig = Field(default_factory=LLMConfig)
    openai: LLMConfig = Field(default_factory=LLMConfig)
    fish_audio: TTSConfig = Field(default_factory=TTSConfig)
    minimax: TTSConfig = Field(default_factory=TTSConfig)
    elevenlabs: TTSConfig = Field(default_factory=TTSConfig)


class ContentConfig(BaseModel):
    """内容生成配置"""
    target_length: int = 2500
    audio_duration: int = 12
    max_retries: int = 2
    temperature: float = 0.8


class VoiceConfig(BaseModel):
    """配音配置"""
    captain_speed: float = 0.95
    captain_emotion: str = "calm"
    melo_speed: float = 1.05
    melo_emotion: str = "cheerful"
    bgm_volume: float = 0.15


class VideoConfig(BaseModel):
    """视频配置"""
    resolution: str = "1920x1080"
    fps: int = 30
    bitrate: str = "5000k"


class ClipConfig(BaseModel):
    """短视频切片配置"""
    count: int = 3
    duration_range: list[int] = [30, 60]
    resolution: str = "1080x1920"


class CardConfig(BaseModel):
    """图文卡片配置"""
    count: int = 5
    size: list[int] = [1080, 1080]


class StorageConfig(BaseModel):
    """存储配置"""
    output_base: str = "./output"
    retention_days: int = 90


class WorkflowConfig(BaseModel):
    """工作流配置"""
    mode: str = "semi"  # manual, semi, auto


class SchedulerConfig(BaseModel):
    """调度器配置"""
    enabled: bool = False
    mode: str = "schedule"  # schedule 或 celery
    weekly_episode: Dict[str, Any] = Field(default_factory=dict)
    data_collection: Dict[str, Any] = Field(default_factory=dict)
    weekly_report: Dict[str, Any] = Field(default_factory=dict)


class NotificationConfig(BaseModel):
    """通知配置"""
    enabled: bool = False
    webhook: Dict[str, Any] = Field(default_factory=dict)
    dingtalk: Dict[str, Any] = Field(default_factory=dict)
    feishu: Dict[str, Any] = Field(default_factory=dict)


class PublishRetryConfig(BaseModel):
    """发布重试配置"""
    max_attempts: int = 3
    backoff_multiplier: int = 5


class PublishConfig(BaseModel):
    """发布配置"""
    retry: PublishRetryConfig = Field(default_factory=PublishRetryConfig)
    rate_limit: Dict[str, Any] = Field(default_factory=dict)


class ProjectConfig(BaseModel):
    """项目主配置"""
    name: str = "ChronoCast"
    chinese_name: str = "超时空电台"
    tagline: str = "麦洛与船长的超时空电台"
    version: str = "1.0.0"


class Config(BaseModel):
    """全局配置"""
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    characters: Dict[str, CharacterConfig] = Field(default_factory=dict)
    api_keys: APIKeys = Field(default_factory=APIKeys)
    content: ContentConfig = Field(default_factory=ContentConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)
    clips: ClipConfig = Field(default_factory=ClipConfig)
    cards: CardConfig = Field(default_factory=CardConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    notification: NotificationConfig = Field(default_factory=NotificationConfig)
    publish: PublishConfig = Field(default_factory=PublishConfig)
    
    @classmethod
    def from_yaml(cls, path: str) -> "Config":
        """从 YAML 文件加载配置"""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**data)
    
    def get_active_llm(self) -> tuple[str, LLMConfig]:
        """获取当前激活的 LLM 配置
        
        优先级：anthropic > deepseek > openai
        """
        for name in ["anthropic", "deepseek", "openai"]:
            config = getattr(self.api_keys, name)
            if config.api_key and config.api_key != f"YOUR_{name.upper()}_API_KEY":
                return name, config
        raise ValueError("No valid LLM API key configured")
    
    def get_active_tts(self) -> tuple[str, TTSConfig]:
        """获取当前激活的 TTS 配置
        
        优先级：fish_audio > minimax > elevenlabs
        """
        for name in ["fish_audio", "minimax", "elevenlabs"]:
            config = getattr(self.api_keys, name)
            if config.api_key and config.api_key != f"YOUR_{name.upper().replace('_', '_')}_API_KEY":
                return name, config
        raise ValueError("No valid TTS API key configured")


# 全局配置实例
_config: Optional[Config] = None


def get_config() -> Config:
    """获取全局配置实例（单例模式）"""
    global _config
    if _config is None:
        # 尝试从默认路径加载
        config_paths = [
            os.environ.get("CHRONOCAST_CONFIG", ""),
            "config/config.yaml",
            "config/config.yml",
            "../config/config.yaml",
        ]
        
        for path in config_paths:
            if path and Path(path).exists():
                _config = Config.from_yaml(path)
                break
        else:
            # 使用默认配置
            _config = Config()
    
    return _config


def reload_config(path: Optional[str] = None) -> Config:
    """重新加载配置"""
    global _config
    if path:
        _config = Config.from_yaml(path)
    else:
        _config = None
        _config = get_config()
    return _config
