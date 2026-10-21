# =============================================================================
# DemBase v3 — Dockerfile (Flet 1.0.1 em modo servidor web)
# Usado pelo Koyeb (ou Northflank/Render) para rodar o app a partir do GitHub.
# O Python roda no servidor; o celular apenas exibe a interface via WebSocket.
# =============================================================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PORT=8000

WORKDIR /app

COPY dembase_flet/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY dembase_flet/ /app/

EXPOSE 8000

CMD ["python", "main.py"]
