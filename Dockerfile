# ChronoCast Dockerfile

FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY src/ ./src/
COPY config/ ./config/
COPY assets/ ./assets/ 2>/dev/null || true
COPY chronocast.py .

# 创建输出目录
RUN mkdir -p output logs data

# 设置环境变量
ENV PYTHONPATH=/app
ENV CHRONOCAST_CONFIG=/app/config/config.yaml

ENTRYPOINT ["python", "chronocast.py"]
CMD ["--help"]
