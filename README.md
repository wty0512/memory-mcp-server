# Python Markdown Memory MCP Server

一個基於 Python 的 Model Context Protocol (MCP) 伺服器，使用 Markdown 檔案管理 AI 對話記憶和專案上下文。

## 🚀 功能特色

- 📝 使用 Markdown 格式儲存和管理記憶
- 🔍 強大的搜尋功能
- 📊 專案分類管理
- 🕒 時間戳記跟蹤
- 🎯 與 Claude Code / Cursor 完美整合
- 🐍 純 Python 實作，無額外依賴

## 🛠️ 安裝和設定

### 1. 環境需求

- Python 3.8+
- Claude Code 或 Cursor IDE
- 作業系統：Windows、macOS、Linux

### 2. 快速安裝

```bash
# 克隆或下載專案
git clone https://github.com/your-username/markdown-memory-mcp.git
cd markdown-memory-mcp

# 創建虛擬環境（可選但推薦）
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安裝依賴（目前無額外依賴）
pip install -r requirements.txt

# 設定執行權限
chmod +x memory_mcp_server.py
chmod +x start_server.sh
```

### 3. 設定 Claude Code / Cursor

#### 方法 1: 全域設定
編輯 `~/.cursor/mcp.json`：
```json
{
  "mcpServers": {
    "markdown-memory": {
      "command": "python3",
      "args": ["/absolute/path/to/memory_mcp_server.py"],
      "transport": "stdio",
      "env": {
        "PYTHONPATH": "/absolute/path/to/markdown-memory-mcp"
      }
    }
  }
}
```

#### 方法 2: 專案設定
在專案根目錄創建 `.cursor/mcp.json`：
```json
{
  "mcpServers": {
    "markdown-memory": {
      "command": "python3",
      "args": ["./memory_mcp_server.py"],
      "transport": "stdio"
    }
  }
}
```

## 📖 使用說明

### 基本使用

1. **儲存記憶**
```
請幫我儲存這次討論的重點：
- 實作了 Python MCP 伺服器
- 使用 Markdown 管理記憶
- 支援搜尋和分類功能
專案: python-mcp-dev
標題: 伺服器實作完成
分類: development
```

2. **搜尋記憶**
```
搜尋 "python-mcp-dev" 專案中關於 "MCP 伺服器" 的記錄
```

3. **查看專案列表**
```
列出所有有記憶的專案
```

## 🚀 部署和整合

### 與 Claude Code 整合

1. **安裝和設定**
```bash
cd /path/to/your/project
python3 memory_mcp_server.py
```

2. **設定 Cursor/Claude Code**
```json
{
  "mcpServers": {
    "memory": {
      "command": "python3",
      "args": ["/absolute/path/to/memory_mcp_server.py"],
      "transport": "stdio"
    }
  }
}
```

## 🔍 故障排除

### 常見問題

1. **伺服器無法啟動**
```bash
# 檢查 Python 版本
python3 --version

# 檢查檔案權限
chmod +x memory_mcp_server.py

# 檢查記憶目錄
ls -la ai-memory/
```

2. **Claude Code 無法連接**
```bash
# 確認設定檔案路徑
cat ~/.cursor/mcp.json

# 測試伺服器手動啟動
python3 memory_mcp_server.py
```

---

**享受您的 AI 記憶管理系統！** 🚀

有任何問題或建議，請隨時提出！