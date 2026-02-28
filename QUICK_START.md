# ChronoCast 快速开始指南

## 🚀 5分钟上手

### 1. 环境准备

```bash
cd chronocast-melo

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置设置

```bash
# 复制配置模板
cp config/config.example.yaml config/config.yaml

# 编辑配置文件
vi config/config.yaml
```

**最小配置** (至少需要配置以下项):
```yaml
# 选择一个 LLM API
api_keys:
  deepseek:  # 推荐,性价比高
    api_key: "YOUR_DEEPSEEK_API_KEY"
    model: "deepseek-chat"

  # 或使用 Claude
  anthropic:
    api_key: "YOUR_CLAUDE_API_KEY"
    model: "claude-3-5-sonnet-20241022"

# 选择一个 TTS API
  fish_audio:
    api_key: "YOUR_FISH_AUDIO_API_KEY"
```

### 3. 初始化项目

```bash
# 初始化目录结构
python chronocast.py init

# 验证配置
python chronocast.py config
```

### 4. 生成第一期内容

```bash
# 准备输入文件
cat > input/ep001.txt << EOF
【本期主题】AI 如何改变我们的生活

【核心判断】
1. AI 不会取代人类,而是增强人类能力
2. 真正的挑战在于如何与 AI 协作
3. 每个人都应该学会使用 AI 工具

【情绪基调】乐观且务实

【参考素材】GPT-4、Claude、Midjourney 的应用案例

【想让麦洛问的问题】
- AI 真的会让人失业吗?
- 小朋友应该怎么学 AI?
- AI 能帮我写作业吗?
EOF

# 生成内容 (仅文稿)
python chronocast.py generate --input input/ep001.txt --episode 1

# 完整流水线 (文稿+音频+视频)
python chronocast.py pipeline --input input/ep001.txt --episode 1 --mode semi

# 查看输出
ls -lh output/EP001/
```

## 📅 启用自动化调度

### 1. 配置调度器

编辑 `config/config.yaml`:

```yaml
scheduler:
  enabled: true
  mode: "schedule"

  weekly_episode:
    enabled: true
    cron: "0 6 * * 1"  # 每周一早上6点
    input_file: "input/weekly_topic.txt"
    auto_publish: true
    platforms: ["rss", "bilibili"]
```

### 2. 准备每周输入文件

```bash
# 创建每周主题文件
cat > input/weekly_topic.txt << EOF
【本期主题】本周科技热点

【核心判断】
1. ...
2. ...
3. ...

【情绪基调】兴奋

【参考素材】本周新闻
EOF
```

### 3. 启动调度器

```bash
# 前台运行 (适合测试)
python chronocast.py scheduler

# 后台运行 (生产环境)
nohup python chronocast.py scheduler --daemon > logs/scheduler.log 2>&1 &

# 查看日志
tail -f logs/scheduler.log
```

### 4. 使用 systemd (推荐)

创建服务文件 `/etc/systemd/system/chronocast.service`:

```ini
[Unit]
Description=ChronoCast Scheduler
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/chronocast-melo
ExecStart=/path/to/chronocast-melo/venv/bin/python chronocast.py scheduler --daemon
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务:
```bash
sudo systemctl enable chronocast
sudo systemctl start chronocast
sudo systemctl status chronocast
```

## 🔧 常用命令

### 内容生成

```bash
# 仅生成文稿
python chronocast.py generate -i input/topic.txt -e 1

# 完整流水线
python chronocast.py pipeline -i input/topic.txt -e 1 -m auto

# 半自动模式 (生成后暂停,等待审阅)
python chronocast.py pipeline -i input/topic.txt -e 1 -m semi
```

### 发布管理

```bash
# 发布到所有平台
python chronocast.py publish -e 1

# 发布到指定平台
python chronocast.py publish -e 1 -p rss -p bilibili

# 查看发布历史
sqlite3 data/analytics.db "SELECT * FROM publish_tasks WHERE episode_number=1;"
```

### 数据收集

```bash
# 收集最新数据
python chronocast.py collect

# 收集指定期号数据
python chronocast.py collect -e 1

# 生成周报
python chronocast.py report
```

### 调度器管理

```bash
# 查看待处理任务
sqlite3 data/analytics.db "SELECT * FROM tasks WHERE status='pending';"

# 执行待处理任务
python chronocast.py scheduler --once

# 启动调度器
python chronocast.py scheduler

# 查看任务历史
sqlite3 data/analytics.db "SELECT id, task_type, status, episode_number, created_at FROM tasks ORDER BY id DESC LIMIT 10;"
```

## 🎯 典型工作流

### 每周工作流 (自动化)

1. **周日晚上**: 准备下周主题,更新 `input/weekly_topic.txt`
2. **周一早上 6:00**: 调度器自动生成内容
3. **周一早上 8:00**: 收到通知,检查生成结果
4. **周一上午**: 审阅文稿,必要时手动调整
5. **周一中午**: 自动发布到各平台
6. **周二-周五**: 自动收集数据
7. **下周一早上**: 收到上周数据周报

### 手动工作流

1. **准备输入**: 创建 `input/ep{N}.txt`
2. **生成内容**: `python chronocast.py pipeline -i input/ep{N}.txt -e {N} -m semi`
3. **审阅结果**: 检查 `output/EP{N}/` 目录
4. **发布**: `python chronocast.py publish -e {N}`
5. **收集数据**: `python chronocast.py collect -e {N}`

## 📊 监控和维护

### 检查系统状态

```bash
# 查看最近任务
sqlite3 data/analytics.db "SELECT * FROM tasks ORDER BY id DESC LIMIT 5;"

# 查看失败任务
sqlite3 data/analytics.db "SELECT * FROM tasks WHERE status='failed';"

# 查看发布状态
sqlite3 data/analytics.db "SELECT platform, status, COUNT(*) as count FROM publish_tasks GROUP BY platform, status;"

# 查看日志
tail -f logs/chronocast.log
```

### 数据库维护

```bash
# 备份数据库
cp data/analytics.db data/analytics.db.backup

# 清理旧任务 (保留90天)
python -c "from src.core.task_manager import TaskManager; TaskManager().cleanup_old_tasks(90)"

# 查看数据库大小
du -h data/analytics.db
```

### 磁盘空间管理

```bash
# 查看输出目录大小
du -sh output/*

# 清理旧期号 (保留最近10期)
ls -t output/ | tail -n +11 | xargs -I {} rm -rf output/{}

# 压缩旧内容
tar -czf archive/EP001-010.tar.gz output/EP00{1..9} output/EP010
```

## ⚠️ 常见问题

### 1. API 调用失败

**问题**: `ValueError: No valid LLM API key configured`

**解决**:
```bash
# 检查配置
python chronocast.py config

# 确认 API key 不是占位符
grep -A 3 "api_keys:" config/config.yaml
```

### 2. 调度器未触发

**问题**: 定时任务没有执行

**解决**:
```bash
# 检查配置
grep -A 10 "scheduler:" config/config.yaml

# 确认 enabled: true
# 确认 cron 格式正确

# 手动触发测试
python chronocast.py scheduler --once
```

### 3. 数据库锁定

**问题**: `sqlite3.OperationalError: database is locked`

**解决**:
```bash
# 检查是否有多个进程
ps aux | grep chronocast

# 停止重复进程
kill <PID>

# 如果数据库损坏,恢复备份
cp data/analytics.db.backup data/analytics.db
```

### 4. 内存不足

**问题**: 视频生成时内存溢出

**解决**:
```yaml
# 降低视频分辨率
video:
  resolution: "1280x720"  # 从 1920x1080 降低
  bitrate: "3000k"        # 从 5000k 降低
```

## 📚 更多资源

- **完整文档**: 查看 `ARCHITECTURE.md` 了解系统架构
- **配置说明**: 查看 `config/config.example.yaml` 的注释
- **开发指南**: 查看 `DEPLOY.md` 了解部署细节
- **API文档**: 查看各模块的 docstring

## 🆘 获取帮助

```bash
# 查看帮助
python chronocast.py --help

# 查看子命令帮助
python chronocast.py generate --help
python chronocast.py scheduler --help
```

---

祝你使用愉快! 🎙️✨
