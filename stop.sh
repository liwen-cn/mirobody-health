#!/usr/bin/env bash

echo "=========================================================="
echo " 正在停止 Mirobody 统一健康报告服务..."
echo "=========================================================="

PID_18060=$(lsof -ti:18060 2>/dev/null || true)
if [ -n "$PID_18060" ]; then
  kill -9 $PID_18060 2>/dev/null || true
  echo "已停止 18060 统一网关进程 (PID: $PID_18060)"
else
  echo "18060 网关未在运行"
fi

PID_18065=$(lsof -ti:18065 2>/dev/null || true)
if [ -n "$PID_18065" ]; then
  kill -9 $PID_18065 2>/dev/null || true
  echo "已停止 18065 进程 (PID: $PID_18065)"
fi

echo "✅ 停止完成！"
