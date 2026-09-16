FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

# 生产建议多 worker；WebSocket 需 uvicorn 原生支持（--ws websockets 默认开启）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
