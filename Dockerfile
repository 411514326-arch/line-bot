# ==============================================================================
# Google Cloud Run 生產環境 Dockerfile
# ==============================================================================
FROM python:3.12-slim

# 設定 Python 環境變數，確保日誌即時輸出且不產生 pyc 垃圾檔
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

# 設定容器內工作目錄
WORKDIR /app

# 安裝基本系統工具 (curl 用於健康檢查探針)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 先複製 requirements.txt 利用 Docker 快取層加速建置
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製專案應用程式程式碼
COPY . .

# 建立對話紀錄目錄與非 root 使用者，提升容器安全性
RUN mkdir -p /app/chat_history && \
    useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# 開放 Cloud Run 預設通訊埠
EXPOSE 8080

# 健康檢查 (Health Check)
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# 使用 Google Cloud Run 官方推薦的 Gunicorn 生產級啟動命令：
# --workers 1 --threads 8：最適合 Cloud Run 異步併發處理與自動水平伸縮架構
# --timeout 0：讓請求逾時完全由 Cloud Run 平台設定管理
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
