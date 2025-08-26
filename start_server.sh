#!/bin/bash
# Markdown Memory MCP Server 啟動腳本

# 檢查 Python 版本
python3 --version

# 檢查記憶目錄
if [ ! -d "ai-memory" ]; then
    echo "Creating ai-memory directory..."
    mkdir -p ai-memory
fi

# 設定執行權限
chmod +x memory_mcp_server.py

# 啟動伺服器
echo "Starting Markdown Memory MCP Server..."
python3 memory_mcp_server.py --backend=sqlite --db-path="$1"