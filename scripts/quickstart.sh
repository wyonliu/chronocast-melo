#!/bin/bash
# ChronoCast 快速启动脚本

set -e

echo "🎙️  ChronoCast - 超时空电台 快速启动"
echo "========================================"
echo ""

# 检查 Python 版本
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then 
    echo "❌ 需要 Python 3.10+，当前版本: $PYTHON_VERSION"
    exit 1
fi

echo "✅ Python 版本: $PYTHON_VERSION"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "🔄 创建虚拟环境..."
    python3 -m venv venv
fi

echo "🔄 激活虚拟环境..."
source venv/bin/activate

# 安装依赖
echo "🔄 安装依赖..."
pip install -q -r requirements.txt

echo "✅ 依赖安装完成"
echo ""

# 初始化项目
echo "🔄 初始化项目结构..."
python chronocast.py init

# 检查配置文件
if [ ! -f "config/config.yaml" ]; then
    echo ""
    echo "⚠️  配置文件不存在"
    echo "📝 请执行以下命令创建配置文件:"
    echo "    cp config/config.example.yaml config/config.yaml"
    echo "    vim config/config.yaml  # 添加你的 API 密钥"
    echo ""
    echo "获取 API 密钥:"
    echo "  - DeepSeek: https://platform.deepseek.com/"
    echo "  - Fish Audio: https://fish.audio/"
    echo ""
    exit 0
fi

echo ""
echo "🎉 初始化完成！"
echo ""
echo "可用命令:"
echo "  生成文稿:  python chronocast.py generate --input examples/ep001_ai_glasses.txt --episode 1"
echo "  完整流水线: python chronocast.py pipeline --input examples/ep001_ai_glasses.txt --episode 1 --mode semi"
echo "  查看配置:  python chronocast.py config"
echo ""
echo "更多信息请查看 DEPLOY.md"
