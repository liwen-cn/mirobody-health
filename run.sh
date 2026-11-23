#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "=========================================================="
echo " 正在启动 Mirobody × AI 主动健康与食养报告统一服务..."
echo "=========================================================="

# 1. 确保 Mirobody Docker 容器运行在内部端口 18061
if [ -d "$DIR/mirobody" ]; then
  cd "$DIR/mirobody"
  if ! grep -q "MIROBODY_HOST_PORT=18061" .env 2>/dev/null; then
    echo "MIROBODY_HOST_PORT=18061" >> .env
  fi
  echo "[1/2] 重启 Mirobody 容器以生效内部端口 18061..."
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose up -d mirobody
  else
    docker compose up -d mirobody
  fi
  cd "$DIR"
fi

# 2. 释放旧的 18060 和 18065 网关/工作台进程
OLD_PID=$(lsof -ti:18060 2>/dev/null || true)
if [ -n "$OLD_PID" ]; then
  kill -9 $OLD_PID 2>/dev/null || true
  sleep 1
fi
OLD_STUDIO_PID=$(lsof -ti:18065 2>/dev/null || true)
if [ -n "$OLD_STUDIO_PID" ]; then
  kill -9 $OLD_STUDIO_PID 2>/dev/null || true
fi

# 3. 后台守护启动 nohup，随时可以关闭终端
LOG_FILE="$DIR/gateway.log"
echo "[2/2] 启动统一网关与报告工作台 (后台运行，日志输出至 gateway.log)..."
nohup python3 -u "$DIR/start_unified_server.py" < /dev/null > "$LOG_FILE" 2>&1 &
NEW_PID=$!

sleep 1.2
if ps -p $NEW_PID > /dev/null 2>&1; then
  echo "=========================================================="
  echo "✅ 服务已成功在后台运行 (PID: $NEW_PID)！"
  echo "👉 访问地址: http://localhost:18060"
  echo "👉 提示: 现在你可以直接关闭这个终端窗口了。"
  echo "=========================================================="
else
  echo "❌ 启动失败，请检查 gateway.log 查看详情。"
  exit 1
fi
