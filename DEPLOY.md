# ChronoCast 部署指南

## 快速启动（三步走）

### 第一步：环境准备（5分钟）

```bash
# 克隆项目
cd /path/to/code-ai
git clone <your-repo> chronocast-melo  # 或使用本工程
cd chronocast-melo

# 安装 Python 依赖（需要 Python 3.10+）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 初始化项目结构
python chronocast.py init
```

### 第二步：配置 API 密钥（5分钟）

```bash
# 复制配置模板
cp config/config.example.yaml config/config.yaml

# 编辑配置文件
vim config/config.yaml  # 或使用你喜欢的编辑器
```

**必须配置的 API 密钥：**

1. **LLM API**（选择其一）：
   - Claude (Anthropic): https://console.anthropic.com/
   - DeepSeek: https://platform.deepseek.com/
   - OpenAI: https://platform.openai.com/

2. **TTS API**（选择其一）：
   - Fish Audio: https://fish.audio/ （推荐，中文效果好）
   - Minimax: https://www.minimaxi.com/ （中文自然）
   - ElevenLabs: https://elevenlabs.io/ （全球最强）

**配置示例：**
```yaml
api_keys:
  deepseek:
    api_key: "your-deepseek-api-key-here"
    model: "deepseek-chat"
    
  fish_audio:
    api_key: "your-fish-audio-api-key-here"
```

### 第三步：生成第一期内容（10分钟）

```bash
# 测试编剧模块（仅生成文稿）
python chronocast.py generate \
  --input examples/ep001_ai_glasses.txt \
  --episode 1

# 查看生成的文稿
cat output/EP001/drafts/EP001_script.md
```

如果文稿满意，继续完整流水线：

```bash
# 完整流水线（生成音频+视频）
python chronocast.py pipeline \
  --input examples/ep001_ai_glasses.txt \
  --episode 1 \
  --mode semi
```

## 声音克隆（船长音色）

如果你想使用自己的声音作为"船长"，需要先克隆声音：

```bash
# 1. 录制 3-5 分钟清晰的人声
# 建议：朗读一段科技文章，语速自然，环境安静
# 保存为 mp3/wav 格式到 samples/ 目录

# 2. 执行克隆
python chronocast.py clone-voice \
  --name captain \
  --samples ./samples/ \
  --description "船长声音，沉稳温和"

# 3. 将返回的 voice_id 添加到 config.yaml
# characters.captain.voice_id: "克隆得到的ID"
```

## 运行模式

### 1. 手动模式（推荐起步）

```bash
python chronocast.py pipeline --input idea.txt --episode 1 --mode manual
```

- 每步执行前会暂停等待确认
- 可以审阅/修改生成的文稿
- 适合调试和精细控制

### 2. 半自动模式（推荐日常使用）

```bash
python chronocast.py pipeline --input idea.txt --episode 2 --mode semi
```

- 自动生成文稿后等待审阅
- 确认后继续自动完成后续步骤
- 平衡效率和质量

### 3. 全自动模式

```bash
python chronocast.py pipeline --input idea.txt --episode 3 --mode auto
```

- 完全自动化，无需人工干预
- 适合稳定运行后的日常生产
- 建议先通过 semi 模式验证几期后再使用

## 发布到平台

### 播客平台（RSS）

播客平台（小宇宙、Apple Podcasts、Spotify）通过 RSS 订阅分发：

1. 设置 RSS URL（在 config.yaml 中）
2. 每次生成内容后更新 RSS feed
3. 各平台自动同步

### 视频平台

当前支持：
- B站（需配置 cookie）
- YouTube（需配置 API）

配置后：
```bash
# 发布单期到所有已配置平台
python -m src.publisher.dispatcher --episode 1
```

### 手动发布

对于抖音、视频号、小红书等暂无 API 的平台：

1. 从 `output/EPXXX/video/clips/` 获取短视频切片
2. 从 `output/EPXXX/drafts/` 获取图文内容
3. 手动上传到各平台

## 定时任务（可选）

使用 cron 或 systemd 设置定时发布：

```bash
# 编辑 crontab
crontab -e

# 每周一晚 8 点自动生成
0 20 * * 1 cd /path/to/chronocast-melo && \
  source venv/bin/activate && \
  python chronocast.py pipeline \
    --input weekly_input.txt \
    --auto-increment-episode \
    --mode semi
```

## Docker 部署

```bash
# 构建镜像
docker build -t chronocast .

# 运行容器
docker run -it --rm \
  -v $(PWD)/config:/app/config \
  -v $(PWD)/output:/app/output \
  -v $(PWD)/data:/app/data \
  chronocast pipeline \
  --input /app/config/input.txt \
  --episode 1
```

## 常见问题

### Q: 生成文稿质量不稳定？

A: 可以尝试：
1. 提供更详细的输入（核心判断 + 麦洛想问的问题）
2. 调整编剧 Prompt（config/writer/system_prompt.md）
3. 增加质检重试次数（config.yaml 中 content.max_retries）

### Q: TTS 合成效果不理想？

A: 
1. 尝试不同的 TTS 服务商
2. 确保声音克隆样本质量（3-5分钟清晰人声）
3. 调整语速和情绪参数（config.yaml 中 voice 部分）

### Q: 视频生成失败？

A:
1. 确保已安装 FFmpeg
2. 检查 assets/brand/ 下的头像文件是否存在
3. 查看 logs/ 目录的详细错误信息

### Q: 如何降低 API 成本？

A:
1. 使用 DeepSeek 替代 Claude（成本更低）
2. 调整目标文稿长度（config.yaml 中 content.target_length）
3. 批量生成时复用已克隆的声音

## 成本估算

以每周 1 期为例：

| 项目 | 月成本 |
|------|--------|
| DeepSeek API | ¥20-50 |
| Fish Audio TTS | ¥50-100 |
| 其他 | ¥30-50 |
| **月总计** | **¥100-200** |

## 下一步

1. ✅ 验证第一期内容生成
2. ✅ 配置声音克隆
3. ✅ 设置发布平台
4. ✅ 调整 Prompt 到满意
5. 🚀 开始自动化生产

有问题？查看日志：
```bash
tail -f logs/chronocast.log
```
