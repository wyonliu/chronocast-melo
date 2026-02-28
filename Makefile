# ChronoCast Makefile

.PHONY: help install init test clean format lint

help: ## 显示帮助信息
	@echo "ChronoCast - 超时空电台"
	@echo ""
	@echo "可用命令:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## 安装依赖
	pip install -r requirements.txt

init: ## 初始化项目
	python chronocast.py init
	@echo "请编辑 config/config.yaml 添加你的 API 密钥"

test: ## 运行测试
	pytest tests/ -v

test-writer: ## 测试编剧模块
	python -m src.writer.generator

test-voice: ## 测试配音模块
	python -m src.voice.synthesizer

test-pipeline: ## 测试完整流水线
	python chronocast.py pipeline --input examples/ep001_ai_glasses.txt --episode 1 --mode manual

generate: ## 生成示例节目（需配置API）
	python chronocast.py generate --input examples/ep001_ai_glasses.txt --episode 1

format: ## 格式化代码
	black src/ tests/ chronocast.py
	ruff check --fix src/ tests/ chronocast.py

lint: ## 代码检查
	ruff check src/ tests/ chronocast.py
	mypy src/

clean: ## 清理临时文件
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/

clean-output: ## 清理输出目录
	rm -rf output/*

docker-build: ## 构建 Docker 镜像
	docker build -t chronocast:latest .

docker-run: ## 运行 Docker 容器
	docker run -it --rm -v $(PWD)/config:/app/config -v $(PWD)/output:/app/output chronocast:latest
