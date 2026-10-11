#!/bin/bash
# 合一重卡经营看板 · 一键启动
# 用法：在访达里双击本文件；或终端执行 ./启动看板.command
#
# 启动内容：
#   1. 后端（8000，同源托管前端构建产物）—— 生产形态，单端口即可访问
#   2. 前端开发服务（5173，热更新）—— 改前端代码时用
# 就绪后自动打开浏览器。

cd "$(dirname "$0")" || exit 1
ROOT="$(pwd)"
BE="$ROOT/backend"
FE="$ROOT/frontend"

say() { printf "\033[1;36m[启动]\033[0m %s\n" "$1"; }
warn() { printf "\033[1;33m[注意]\033[0m %s\n" "$1"; }
die() { printf "\033[1;31m[失败]\033[0m %s\n" "$1"; if [ -t 0 ]; then read -r -p "按回车关闭窗口…" _; fi; exit 1; }

echo "════════════════════════════════════════════"
echo "  合一重卡生态经营看板 · 启动器"
echo "════════════════════════════════════════════"

# ---------- 0. 端口占用检查 ----------
for p in 8000 5173; do
  if lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1; then
    warn "端口 $p 已被占用，将复用已在运行的服务。"
  fi
done

# ---------- 1. 后端环境 ----------
[ -d "$BE" ] || die "找不到 backend 目录：$BE"

if [ ! -x "$BE/.venv/bin/python" ]; then
  say "未找到 Python 虚拟环境，正在创建（首次约需 30 秒）…"
  PY=""
  for c in /Users/gavin/.workbuddy/binaries/python/versions/3.13.12/bin/python3 python3.13 python3; do
    command -v "$c" >/dev/null 2>&1 && PY="$c" && break
    [ -x "$c" ] && PY="$c" && break
  done
  [ -n "$PY" ] || die "找不到可用的 Python 3。请先安装 Python 3.13。"
  "$PY" -m venv "$BE/.venv" || die "创建虚拟环境失败。"
  "$BE/.venv/bin/pip" install -q -r "$BE/requirements.txt" || die "安装后端依赖失败。"
  say "后端依赖安装完成。"
fi

# ---------- 2. 种子数据（幂等，已有数据则跳过）----------
say "检查数据库…"
( cd "$BE" && DATABASE_URL="sqlite:///./dev.db" .venv/bin/python -m app.seed >/dev/null 2>&1 ) \
  && say "数据库就绪。" || warn "种子数据检查跳过（不影响已存在的库）。"

# ---------- 3. 启动后端 ----------
if ! lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  say "启动后端（端口 8000）…"
  ( cd "$BE" && DATABASE_URL="sqlite:///./dev.db" STATIC_DIR=./static \
      nohup .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 \
      >"$ROOT/.backend.log" 2>&1 & )
else
  say "后端已在 8000 运行，跳过。"
fi

for i in $(seq 1 30); do
  curl -s -o /dev/null --max-time 1 http://127.0.0.1:8000/api/health && break
  sleep 1
done
curl -s --max-time 2 http://127.0.0.1:8000/api/health >/dev/null \
  && say "后端就绪：http://127.0.0.1:8000" \
  || warn "后端未在 30 秒内就绪，请查看 $ROOT/.backend.log"

# ---------- 4. 启动前端开发服务 ----------
if [ -d "$FE/node_modules" ]; then
  if ! lsof -nP -iTCP:5173 -sTCP:LISTEN >/dev/null 2>&1; then
    say "启动前端开发服务（端口 5173）…"
    ( cd "$FE" && nohup npm run dev >"$ROOT/.frontend.log" 2>&1 & )
    for i in $(seq 1 30); do
      curl -s -o /dev/null --max-time 1 http://127.0.0.1:5173/ && break
      sleep 1
    done
    curl -s -o /dev/null --max-time 2 http://127.0.0.1:5173/ \
      && say "前端就绪：http://127.0.0.1:5173" \
      || warn "前端未在 30 秒内就绪，请查看 $ROOT/.frontend.log"
  else
    say "前端已在 5173 运行，跳过。"
  fi
else
  warn "未找到 frontend/node_modules，跳过前端开发服务（不影响 8000 的生产形态）。"
  warn "如需热更新：cd frontend && npm install"
fi

# ---------- 5. 打开浏览器 ----------
say "打开浏览器…"
open "http://127.0.0.1:8000" 2>/dev/null || true

echo
echo "────────────────────────────────────────────"
echo "  生产形态（推荐）  http://127.0.0.1:8000"
echo "  开发形态（热更新） http://127.0.0.1:5173"
echo "  登录账号          chenzm / Demo#2026"
echo "────────────────────────────────────────────"
echo "  日志：$ROOT/.backend.log"
echo "        $ROOT/.frontend.log"
echo "  本窗口可以关闭，服务已在后台运行。"
echo "────────────────────────────────────────────"
sleep 2
