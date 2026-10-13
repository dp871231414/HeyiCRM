#!/usr/bin/env sh
# 单容器启动脚本：初始化种子数据 → 启动服务（由后端同源托管前端 SPA）
set -e

# 前端构建产物目录（默认 ./static；不存在时自动退化为纯 API 服务）
export STATIC_DIR="${STATIC_DIR:-./static}"
# 演示库（可用 DATABASE_URL 覆盖为 PostgreSQL）
export DATABASE_URL="${DATABASE_URL:-sqlite:///./app.db}"
# 监听端口（发布沙箱注入 PORT）
PORT="${PORT:-3000}"

echo "[start] python=$(python -V 2>&1) port=${PORT} cwd=$(pwd)"
echo "[start] static_dir=${STATIC_DIR} exists=$([ -d "${STATIC_DIR}" ] && echo yes || echo no)"
echo "[start] database_url=${DATABASE_URL}"

python -c "import fastapi, uvicorn, sqlalchemy; print('[start] deps ok')" || echo "[start] deps check failed"

# 种子数据。
#   默认：幂等补齐（已有数据不动，仅新增缺失项与内置角色权限对齐）
#   SEED_RESET=1：先清空业务表再重新灌入，用于把演示环境恢复到初始状态
# 例如部署时以 `SEED_RESET=1 sh start.sh` 启动一次即可完成重置，之后正常启动即可。
if [ "${SEED_RESET}" = "1" ]; then
  echo "[start] SEED_RESET=1 → 清空并重建种子数据"
  python -m app.seed --reset || echo "[start] reset skipped or failed (non-fatal)"
else
  python -m app.seed || echo "[start] seed skipped or failed (non-fatal)"
fi

# 一次性数据清理（可选，默认不执行）。
#   用法：PURGE_KEEP="admin,huguohai" sh start.sh
#   执行一次后改回 `sh start.sh` 正常启动即可，不必每次带着它。
# 注意：必须走本脚本，才能复用上面那份 DATABASE_URL；直接在外面跑
#       `python -m app.maintenance` 会拿到代码里的默认值，连到的不是这里在用的库。
if [ -n "${PURGE_KEEP}" ]; then
  echo "[start] PURGE_KEEP=${PURGE_KEEP} → 执行数据清理（保留这些账号）"
  python -m app.maintenance purge --keep "${PURGE_KEEP}" || echo "[start] purge failed (non-fatal)"
fi

# 一次性账号改名（可选，默认不执行）。同样必须走本脚本才能用对连接串。
#   用法：RENAME_FROM="旧账号名" RENAME_TO="新账号名" RENAME_PASSWORD="新密码" sh start.sh
#   RENAME_PASSWORD 不传则密码不变。
if [ -n "${RENAME_FROM}" ] && [ -n "${RENAME_TO}" ]; then
  echo "[start] RENAME_FROM=${RENAME_FROM} RENAME_TO=${RENAME_TO} → 执行账号改名"
  if [ -n "${RENAME_PASSWORD}" ]; then
    python -m app.maintenance rename --account "${RENAME_FROM}" --to "${RENAME_TO}" --password "${RENAME_PASSWORD}" \
      || echo "[start] rename failed (non-fatal)"
  else
    python -m app.maintenance rename --account "${RENAME_FROM}" --to "${RENAME_TO}" \
      || echo "[start] rename failed (non-fatal)"
  fi
fi

# 用 python -m 调用，避免 uvicorn 可执行文件不在 PATH 上
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --log-level info
