# ---------- Stage 1：安裝相依套件 ----------
FROM python:3.12-slim AS builder
WORKDIR /build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# ---------- Stage 2：執行環境（只含必要檔案，映像檔較小、攻擊面較少） ----------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080
WORKDIR /app

COPY --from=builder /install /usr/local
COPY app ./app

# 以非 root 使用者執行，降低容器被入侵時的影響範圍
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8080
# Cloud Run 透過 PORT 環境變數指定監聽埠；exec 讓 uvicorn 成為 PID 1，能正確接收關機訊號
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
