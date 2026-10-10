#!/usr/bin/env sh
# 单容器启动脚本：初始化种子数据 → 启动服务（由后端同源托管前端 SPA）
set -e

# 前端构建产物目录（默认 ./static；不存在时自动退化为纯 API 服务）
export STATIC_DIR="${STATIC_DIR:-./static}"
# 演示库（可用 DATABASE_URL 覆盖为 PostgreSQL）
export DATABASE_URL="${DATABASE_URL:-sqlite:///./app.db}"
# 监听端口（发布沙箱注入 PORT）
PORT="${PORT:-3000}"

python -m app.seed || true

exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
