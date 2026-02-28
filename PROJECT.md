# ChronoCast 项目总览

## 🎙️ 项目介绍

**ChronoCast**（超时空电台）是一个全自动化内容工厂，实现「麦洛与船长的电台」从想法输入到多平台分发的全流程自动化。

> "嘿，欢迎来到麦洛与船长的电台。这里是一个爸爸和女儿，聊聊这个正在被 AI 改变的世界。"

## 📁 项目结构

```
chronocast-melo/
├── 📄 chronocast.py          # CLI 入口
├── 📄 README.md              # 项目简介
├── 📄 DEPLOY.md              # 部署指南
├── 📄 ARCHITECTURE.md        # 架构设计
├── 📄 PROJECT.md             # 本文档
├── 📄 requirements.txt       # Python 依赖
├── 📄 Makefile               # 快捷命令
├── 📄 Dockerfile             # 容器化配置
│
├── 📁 config/                # 配置文件
│   ├── config.example.yaml   # 配置模板（API密钥等）
│   └── writer/
│       ├── system_prompt.md  # AI编剧核心Prompt
│       └── inspector_prompt.md # 质检Prompt
│
├── 📁 src/                   # 源代码
│   ├── core/                 # 核心模块
│   │   ├── config.py         # 配置管理
│   │   └── pipeline.py       # 内容流水线
│   ├── writer/               # AI编剧
│   │   ├── generator.py      # 文稿生成
│   │   └── inspector.py      # 质检Agent
│   ├── voice/                # AI配音
│   │   ├── synthesizer.py    # TTS合成
│   │   └── mixer.py          # 混音后期
│   ├── studio/               # AI制片
│   │   └── video.py          # 视频生成
│   ├── publisher/            # 自动发行
│   │   └── dispatcher.py     # 分发调度
│   └── analytics/            # 数据监控
│       ├── collector.py      # 数据收集
│       └── reporter.py       # AI周报
│
├── 📁 examples/              # 示例输入
│   ├── input_template.txt    # 输入模板
│   ├── ep001_ai_glasses.txt  # 示例1：AI眼镜
│   └── ep002_world_model.txt # 示例2：世界模型
│
├── 📁 assets/                # 品牌资产
│   ├── voices/               # 声音样本（船长克隆）
│   ├── bgm/                  # 背景音乐
│   ├── templates/            # 视频模板
│   └── brand/                # Logo/头像/字体
│
├── 📁 output/                # 输出目录
│   ├── drafts/               # 文稿
│   ├── audio/                # 音频
│   ├── video/                # 视频
│   ├── clips/                # 短视频切片
│   └── cards/                # 图文卡片
│
├── 📁 scripts/               # 辅助脚本
│   └── quickstart.sh         # 快速启动脚本
│
├── 📁 data/                  # 数据存储
├── 📁 logs/                  # 日志文件
└── 📁 tests/                 # 测试代码
```

## 🚀 快速开始（3步）

### 1. 安装依赖
```bash
cd chronocast-melo
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 配置 API
```bash
cp config/config.example.yaml config/config.yaml
# 编辑 config.yaml，填入你的 API 密钥
```

### 3. 生成内容
```bash
# 生成单期文稿
python chronocast.py generate --input examples/ep001_ai_glasses.txt --episode 1

# 完整流水线（文稿+音频+视频）
python chronocast.py pipeline --input examples/ep001_ai_glasses.txt --episode 1 --mode semi
```

## 📋 核心功能

| 功能模块 | 说明 | 输出 |
|---------|------|------|
| **AI 编剧** | 基于输入生成父女对话文稿 | Markdown 文稿（2000-3000字）|
| **AI 配音** | 船长（克隆音）+ 麦洛（童声）| MP3 音频（10-15分钟）|
| **AI 制片** | 生成多种格式视频 | 横屏完整版 + 竖屏切片 |
| **自动发行** | 分发到10+平台 | 播客/视频/图文 |
| **数据监控** | 回收数据，AI周报 | 周报 + Prompt进化建议 |

## 💰 成本估算

以每周1期为例：

| 项目 | 月成本 | 说明 |
|------|--------|------|
| DeepSeek API | ¥20-50 | 文稿生成 |
| Fish Audio TTS | ¥50-100 | 语音合成 |
| 其他 | ¥30-50 | 视频合成等 |
| **月总计** | **¥100-200** | |

## 🔧 技术栈

- **Python 3.10+**
- **LLM**: Claude / DeepSeek / OpenAI
- **TTS**: Fish Audio / Minimax / ElevenLabs
- **视频**: MoviePy + FFmpeg
- **数据**: SQLite
- **CLI**: Click + Rich

## 📖 详细文档

| 文档 | 内容 |
|------|------|
| [README.md](README.md) | 项目简介和快速开始 |
| [DEPLOY.md](DEPLOY.md) | 完整部署指南 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 架构设计说明 |
| [PROJECT.md](PROJECT.md) | 项目总览（本文档） |

## 🎯 内容格式

### 输入格式（idea.txt）
```markdown
【本期主题】为什么 AI 眼镜会取代手机

【核心判断】
1. 不是取代，是"隐身"
2. 真正的杀手应用是"看懂世界"
3. 2028年会有iPhone时刻

【情绪基调】兴奋但克制

【参考素材】Meta Orion发布会

【想让麦洛问的问题】
- 眼镜不会很重吗？
- 那玩游戏是不是更爽？
```

### 输出格式
- **文稿**: `output/EP001/drafts/EP001_script.md`
- **音频**: `output/EP001/audio/EP001_full.mp3`
- **视频**: `output/EP001/video/EP001_full.mp4`
- **切片**: `output/EP001/video/clips/clip_01.mp4`

## 🔄 发布节奏

| 时间 | 内容 | 平台 |
|------|------|------|
| 周三早 8:00 | 完整播客 | 小宇宙/Apple/Spotify |
| 周三晚 20:00 | 完整视频 | B站/YouTube |
| 周三晚 21:00 | 图文文稿 | 公众号/知乎 |
| 周四-周六 | 短视频切片×3 | 抖音/视频号/小红书 |

## 🛠️ 常用命令

```bash
# 查看帮助
python chronocast.py --help

# 初始化项目
python chronocast.py init

# 生成文稿
python chronocast.py generate -i input.txt -e 1

# 完整流水线
python chronocast.py pipeline -i input.txt -e 1 -m semi

# 克隆声音
python chronocast.py clone-voice -n captain -s samples/

# 查看配置
python chronocast.py config

# Makefile 快捷命令
make install    # 安装依赖
make test       # 运行测试
make generate   # 生成示例
make format     # 格式化代码
make clean      # 清理临时文件
```

## 📝 定制开发

### 修改编剧风格
编辑 `config/writer/system_prompt.md`

### 更换 TTS 服务
编辑 `config/config.yaml` 中的 `api_keys`

### 添加新平台
在 `src/publisher/dispatcher.py` 添加 PlatformPublisher 子类

## 🔮 未来规划

- [ ] AI 动漫风格视频（AnimateDiff）
- [ ] 多语言自动翻译
- [ ] 实时热点追踪选题
- [ ] 听众互动投稿
- [ ] 品牌周边自动生成

## 📞 支持

遇到问题？
1. 查看日志：`tail -f logs/chronocast.log`
2. 检查配置：`python chronocast.py config`
3. 阅读 [DEPLOY.md](DEPLOY.md) 常见问题

---

**ChronoCast** © 2024 | 麦洛与船长的超时空电台

*"在时间的河流里，我们用对话刻下坐标。"*
