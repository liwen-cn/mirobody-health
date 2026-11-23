#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "=========================================================="
echo " 正在后台启动 Mirobody × AI 主动健康与食养报告服务..."
echo "=========================================================="

# 1. 启动并切换 Mirobody Docker 容器到内部端口 18061
if [ -d "$DIR/mirobody" ]; then
  cd "$DIR/mirobody"
  if ! grep -q "MIROBODY_HOST_PORT=18061" .env 2>/dev/null; then
    echo "MIROBODY_HOST_PORT=18061" >> .env
  fi
  echo "[1/3] 检查/启动 Mirobody 容器..."
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose up -d mirobody pg >/dev/null 2>&1 || true
  else
    docker compose up -d mirobody pg >/dev/null 2>&1 || true
  fi
  cd "$DIR"
fi

# 2. 检查并清理旧进程
echo "[2/3] 清理旧端口占用..."
OLD_PID=$(lsof -ti:18060 2>/dev/null || true)
if [ -n "$OLD_PID" ]; then
  kill -9 $OLD_PID 2>/dev/null || true
  sleep 1
fi
OLD_STUDIO_PID=$(lsof -ti:18065 2>/dev/null || true)
if [ -n "$OLD_STUDIO_PID" ]; then
  kill -9 $OLD_STUDIO_PID 2>/dev/null || true
fi

# 3. 后台守护启动 nohup
LOG_FILE="$DIR/gateway.log"
echo "[3/3] 启动统一网关进程 (后台守护运行，日志存入 gateway.log)..."
nohup python3 -u "$DIR/start_unified_server.py" < /dev/null > "$LOG_FILE" 2>&1 &
NEW_PID=$!

sleep 1.5
if ps -p $NEW_PID > /dev/null 2>&1; then
  echo "=========================================================="
  echo "✅ 启动成功！进程 PID: $NEW_PID"
  echo "👉 访问地址: http://localhost:18060"
  echo "👉 提示: 现在你可以随时关闭这个终端窗口，服务会继续在后台运行！"
  echo "=========================================================="
else
  echo "❌ 启动失败，请检查 gateway.log 查看详细错误。"
  exit 1
fi
