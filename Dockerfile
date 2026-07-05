# ─── Python Version ───
FROM python:3.12-slim AS base

# ─── Environment ───
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ─── Dependencies ───
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ─── Application Code ───
COPY . .

# ─── Data Volume (for SQLite) ───
RUN mkdir -p /data
ENV DB_PATH=/data/github_store_bot.db

# ─── Expose Port (for Webhook mode) ───
EXPOSE 8080

# ─── Start Command ───
CMD ["python", "-m", "main"]