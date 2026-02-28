# ChronoCast · 超时空电台

> "嘿，欢迎来到麦洛与船长的电台。这里是一个爸爸和女儿，聊聊这个正在被 AI 改变的世界。"

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 项目简介

ChronoCast 是一个**全自动化内容工厂**，基于「麦洛与船长」父女对话体的科技人文播客 IP。只需输入你的想法（5-10分钟），系统自动完成：

```
你的想法输入 → AI编剧 → AI配音 → AI制片 → 自动发行 → 数据监控
    (5分钟)      (2分钟)   (5分钟)   (10分钟)   (自动)    (持续)
```

## 核心特性

- 🤖 **AI 编剧**：生成 2000-3000 字自然对话文稿，含短视频切片标注
- 🎙️ **AI 配音**：船长（克隆音色）+ 麦洛（童声），情绪自然
- 🎬 **AI 制片**：一鱼多吃——完整音频/视频/短视频切片/图文卡片
- 📡 **自动发行**：小宇宙/B站/抖音/视频号/小红书/公众号等 10+ 平台
- 📊 **数据监控**：自动回收数据，AI 生成周报，驱动 Prompt 进化

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API 密钥
cp config/config.example.yaml config/config.yaml
# 编辑 config.yaml，填入你的 API 密钥

# 3. 录制船长声音样本（用于克隆）
python scripts/record_captain_voice.py

# 4. 生成第一期内容
python -m src.core.pipeline --input "你的想法.txt" --output-dir ./output/ep001

# 5. 启动完整流水线（全自动）
python -m src.core.orchestrator --mode auto
```

## 项目结构

```
chronocast-melo/
├── config/                 # 配置文件
│   ├── config.yaml         # 主配置（API密钥等）
│   ├── writer/             # 编剧 Prompts
│   ├── voice/              # 配音配置
│   └── studio/             # 制片模板
├── src/
│   ├── core/               # 核心编排
│   │   ├── pipeline.py     # 内容流水线
│   │   └── orchestrator.py # 主控调度
│   ├── writer/             # AI 编剧
│   │   ├── generator.py    # 文稿生成
│   │   └── inspector.py    # 质检Agent
│   ├── voice/              # AI 配音
│   │   ├── synthesizer.py  # TTS合成
│   │   └── mixer.py        # 混音/后期
│   ├── studio/             # AI 制片
│   │   ├── video.py        # 视频合成
│   │   ├── clips.py        # 短视频切片
│   │   └── cards.py        # 图文卡片
│   ├── publisher/          # 自动发行
│   │   ├── platforms/      # 各平台适配器
│   │   └── dispatcher.py   # 分发调度
│   └── analytics/          # 数据监控
│       ├── collector.py    # 数据回收
│       └── reporter.py     # AI周报
├── assets/                 # 品牌资产
│   ├── voices/             # 声音样本
│   ├── bgm/                # 背景音乐
│   ├── templates/          # 视频模板
│   └── brand/              # Logo/字体/配色
├── output/                 # 输出目录
│   ├── drafts/             # 文稿
│   ├── audio/              # 音频
│   ├── video/              # 视频
│   ├── clips/              # 短视频切片
│   └── cards/              # 图文卡片
├── scripts/                # 辅助脚本
└── tests/                  # 测试
```

## 输入格式

```markdown
【本期主题】AI 眼镜会取代手机吗？

【核心判断】
1. 不是取代，是"隐身"——手机让你低头，眼镜让你抬头
2. 真正的杀手应用不是显示信息，而是"看懂世界"
3. 2028年会有一个iPhone时刻

【情绪基调】兴奋但克制

【参考素材】Meta Orion最新发布会

【想让麦洛问的问题】
- 眼镜不会很重吗？
- 那玩游戏是不是更爽？
```

## 发布节奏

| 日期 | 内容 | 平台 |
|------|------|------|
| 周三早 8:00 | 完整播客 | 小宇宙/喜马拉雅/Apple/Spotify |
| 周三晚 20:00 | 完整视频 | B站/YouTube |
| 周三晚 21:00 | 图文文稿 | 公众号/知乎 |
| 周四-周六 | 短视频切片×3 | 抖音/视频号/小红书 |
| 周四-周五 | 图文卡片×5 | 小红书/朋友圈 |

## 成本估算

每月4期，总计约 **¥200-500**：
- LLM API：¥50-100
- TTS API：¥100-200
- 其他：¥50-200

## 技术栈

- **LLM**: Claude API / DeepSeek API
- **TTS**: Fish Audio / Minimax TTS / ElevenLabs
- **视频**: Remotion / FFmpeg
- **编排**: Python + Celery / n8n
- **分发**: 各平台 API + RSS

## 许可证

MIT License

---

*"在时间的河流里，我们用对话刻下坐标。"*
