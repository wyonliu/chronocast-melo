"""数据监控 - 数据收集器

回收各平台数据，用于后续分析和反馈迭代
"""
import json
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from loguru import logger

from ..core.config import get_config, Config


@dataclass
class EpisodeMetrics:
    """单期节目数据指标"""
    episode_number: int
    date: str
    
    # 播客数据
    podcast_plays: int = 0
    podcast_likes: int = 0
    podcast_comments: int = 0
    
    # B站数据
    bili_views: int = 0
    bili_likes: int = 0
    bili_coins: int = 0
    bili_favorites: int = 0
    bili_shares: int = 0
    bili_comments: int = 0
    
    # 短视频数据（汇总）
    short_views: int = 0
    short_likes: int = 0
    short_shares: int = 0
    short_comments: int = 0
    
    # 公众号数据
    wechat_reads: int = 0
    wechat_likes: int = 0
    wechat_shares: int = 0
    
    # 计算指标
    @property
    def total_reach(self) -> int:
        """总触达"""
        return self.podcast_plays + self.bili_views + self.short_views + self.wechat_reads
    
    @property
    def engagement_rate(self) -> float:
        """互动率"""
        total_interactions = (
            self.podcast_likes + self.podcast_comments +
            self.bili_likes + self.bili_comments +
            self.short_likes + self.short_comments +
            self.wechat_likes + self.wechat_shares
        )
        total_views = self.bili_views + self.short_views + self.wechat_reads
        if total_views == 0:
            return 0.0
        return total_interactions / total_views


class MetricsDatabase:
    """指标数据库"""
    
    def __init__(self, db_path: str = "./data/analytics.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS episode_metrics (
                episode_number INTEGER PRIMARY KEY,
                date TEXT,
                podcast_plays INTEGER DEFAULT 0,
                podcast_likes INTEGER DEFAULT 0,
                podcast_comments INTEGER DEFAULT 0,
                bili_views INTEGER DEFAULT 0,
                bili_likes INTEGER DEFAULT 0,
                bili_coins INTEGER DEFAULT 0,
                bili_favorites INTEGER DEFAULT 0,
                bili_shares INTEGER DEFAULT 0,
                bili_comments INTEGER DEFAULT 0,
                short_views INTEGER DEFAULT 0,
                short_likes INTEGER DEFAULT 0,
                short_shares INTEGER DEFAULT 0,
                short_comments INTEGER DEFAULT 0,
                wechat_reads INTEGER DEFAULT 0,
                wechat_likes INTEGER DEFAULT 0,
                wechat_shares INTEGER DEFAULT 0,
                updated_at TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS platform_data_raw (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_number INTEGER,
                platform TEXT,
                metric_type TEXT,
                metric_value INTEGER,
                collected_at TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def save_metrics(self, metrics: EpisodeMetrics):
        """保存指标数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        data = asdict(metrics)
        data['updated_at'] = datetime.now().isoformat()
        
        # 检查是否已存在
        cursor.execute(
            "SELECT episode_number FROM episode_metrics WHERE episode_number = ?",
            (metrics.episode_number,)
        )
        
        if cursor.fetchone():
            # 更新
            sets = ", ".join([f"{k} = ?" for k in data.keys() if k != 'episode_number'])
            values = [v for k, v in data.items() if k != 'episode_number']
            values.append(metrics.episode_number)
            
            cursor.execute(
                f"UPDATE episode_metrics SET {sets} WHERE episode_number = ?",
                values
            )
        else:
            # 插入
            columns = ", ".join(data.keys())
            placeholders = ", ".join(["?" for _ in data])
            cursor.execute(
                f"INSERT INTO episode_metrics ({columns}) VALUES ({placeholders})",
                list(data.values())
            )
        
        conn.commit()
        conn.close()
    
    def get_metrics(self, episode_number: int) -> Optional[EpisodeMetrics]:
        """获取单期指标"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM episode_metrics WHERE episode_number = ?",
            (episode_number,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            # 转换为 EpisodeMetrics
            columns = [desc[0] for desc in cursor.description]
            data = dict(zip(columns, row))
            return EpisodeMetrics(**{k: v for k, v in data.items() 
                                    if k in EpisodeMetrics.__dataclass_fields__})
        return None
    
    def get_all_metrics(self, limit: int = 10) -> List[EpisodeMetrics]:
        """获取最近的多期指标"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM episode_metrics ORDER BY episode_number DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        conn.close()
        
        metrics_list = []
        for row in rows:
            data = dict(zip(columns, row))
            metrics_list.append(EpisodeMetrics(**{k: v for k, v in data.items() 
                                                  if k in EpisodeMetrics.__dataclass_fields__}))
        return metrics_list


class DataCollector:
    """数据收集器"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.db = MetricsDatabase()
    
    async def collect_all(self, episode_number: int) -> EpisodeMetrics:
        """收集单期所有平台数据
        
        注意：大部分平台需要手动或半自动收集数据
        这里提供框架和示例实现
        """
        metrics = EpisodeMetrics(
            episode_number=episode_number,
            date=datetime.now().strftime("%Y-%m-%d")
        )
        
        # 收集各平台数据
        # 实际实现需要对接各平台 API 或爬虫
        
        # B站数据（示例）
        bili_data = await self._collect_bilibili(episode_number)
        metrics.bili_views = bili_data.get("views", 0)
        metrics.bili_likes = bili_data.get("likes", 0)
        metrics.bili_coins = bili_data.get("coins", 0)
        
        # 保存到数据库
        self.db.save_metrics(metrics)
        
        logger.info(f"数据收集完成 EP{episode_number:03d}: 触达 {metrics.total_reach}")
        
        return metrics
    
    async def _collect_bilibili(self, episode_number: int) -> Dict[str, int]:
        """收集 B站数据（需要实现）"""
        # 示例：使用 bilibili-api 库
        # from bilibili_api import video
        # ...
        return {"views": 0, "likes": 0, "coins": 0}
    
    async def _collect_xiaoyuzhou(self, episode_number: int) -> Dict[str, int]:
        """收集小宇宙数据"""
        # 小宇宙暂无官方 API，需要手动录入或爬虫
        return {"plays": 0, "likes": 0, "comments": 0}
    
    def manual_input(self, episode_number: int, platform: str, data: Dict[str, int]):
        """手动录入数据"""
        metrics = self.db.get_metrics(episode_number) or EpisodeMetrics(
            episode_number=episode_number,
            date=datetime.now().strftime("%Y-%m-%d")
        )
        
        # 更新对应平台数据
        if platform == "bilibili":
            metrics.bili_views = data.get("views", metrics.bili_views)
            metrics.bili_likes = data.get("likes", metrics.bili_likes)
        elif platform == "xiaoyuzhou":
            metrics.podcast_plays = data.get("plays", metrics.podcast_plays)
        # ... 其他平台
        
        self.db.save_metrics(metrics)
        logger.info(f"手动录入完成 EP{episode_number:03d} {platform}")


if __name__ == "__main__":
    # 测试
    import asyncio
    
    async def test():
        collector = DataCollector()
        metrics = await collector.collect_all(1)
        print(f"Total reach: {metrics.total_reach}")
    
    asyncio.run(test())
