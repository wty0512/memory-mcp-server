# Memory MCP Server - Claude Code 設定指南

## 🚀 快速設定

### 1. 資料庫目錄設定

預設情況下，系統會在用戶主目錄下創建 `~/.memory_mcp/` 目錄：

```bash
# 預設路徑結構
~/.memory_mcp/
├── memory.db          # SQLite 資料庫
├── memories/          # Markdown 備份目錄
├── logs/             # 系統日誌
└── exports/          # 匯出檔案
```

### 2. Claude Code 配置檔設定

#### 方法一：使用預設路徑（最簡單）

在 Claude Code 配置檔中添加：

**macOS/Linux**: `~/.config/claude/claude_desktop_config.json`
```json
{
  "mcpServers": {
    "memory": {
      "command": "python3",
      "args": ["/Users/wangziyan/mcp-servers/memory_mcp_server/memory_mcp_server.py"]
    }
  }
}
```

#### 方法二：自定義資料庫路徑

```json
{
  "mcpServers": {
    "memory": {
      "command": "python3",
      "args": [
        "/Users/wangziyan/mcp-servers/memory_mcp_server/memory_mcp_server.py",
        "--db-path", "/Users/wangziyan/Documents/ClaudeMemory/database"
      ]
    }
  }
}
```

#### 方法三：使用環境變數

```json
{
  "mcpServers": {
    "memory": {
      "command": "python3",
      "args": ["/Users/wangziyan/mcp-servers/memory_mcp_server/memory_mcp_server.py"],
      "env": {
        "MEMORY_DB_PATH": "/Users/wangziyan/Documents/ClaudeMemory/database"
      }
    }
  }
}
```

### 3. 建議的資料庫路徑設定

根據不同需求選擇：

```bash
# 預設隱藏目錄（推薦新手）
~/.memory_mcp/memory.db

# 文件目錄（方便管理）
~/Documents/ClaudeMemory/memory.db

# 專案相關目錄（方便備份）
~/Projects/ClaudeMemory/memory.db

# 雲端同步目錄（多裝置同步）
~/OneDrive/ClaudeMemory/memory.db
~/Dropbox/ClaudeMemory/memory.db
~/Google Drive/ClaudeMemory/memory.db
```

### 4. 權限設定

確保 Claude Code 可以存取資料庫目錄：

```bash
# 創建目錄並設定權限
mkdir -p ~/Documents/ClaudeMemory
chmod 755 ~/Documents/ClaudeMemory

# 如果使用預設目錄
mkdir -p ~/.memory_mcp
chmod 755 ~/.memory_mcp
```

## 🔧 完整配置範例

### 基本配置（推薦）

```json
{
  "mcpServers": {
    "memory": {
      "command": "python3",
      "args": [
        "/Users/wangziyan/mcp-servers/memory_mcp_server/memory_mcp_server.py",
        "--db-path", "/Users/wangziyan/Documents/ClaudeMemory/memory.db",
        "--backend", "sqlite",
        "--log-level", "INFO"
      ],
      "env": {
        "PYTHONPATH": "/Users/wangziyan/mcp-servers/memory_mcp_server"
      }
    }
  }
}
```

### 進階配置

```json
{
  "mcpServers": {
    "memory": {
      "command": "python3",
      "args": [
        "/Users/wangziyan/mcp-servers/memory_mcp_server/memory_mcp_server.py",
        "--db-path", "/Users/wangziyan/Documents/ClaudeMemory/memory.db",
        "--backend", "sqlite",
        "--log-level", "DEBUG",
        "--max-retries", "5",
        "--timeout", "60"
      ],
      "env": {
        "PYTHONPATH": "/Users/wangziyan/mcp-servers/memory_mcp_server",
        "MEMORY_LOG_LEVEL": "DEBUG"
      }
    }
  }
}
```

## 📱 使用方式

設定完成後，重啟 Claude Code，然後可以開始使用：

### 基本操作

```
# 儲存記憶
"請幫我儲存這個專案的架構決策..."
# Claude 會自動使用 save_project_memory 工具

# 搜尋記憶  
"幫我找這個專案中關於認證的記憶"
# Claude 會使用 search_project_memory 工具

# 智能問答
"這個專案的主要技術棧是什麼？"
# Claude 會使用 rag_query 工具
```

### 可用工具清單

1. **記憶管理**:
   - `save_project_memory` - 儲存記憶
   - `get_project_memory` - 讀取記憶
   - `search_project_memory` - 搜尋記憶
   - `delete_project_memory` - 刪除專案

2. **AI 協助**:
   - `rag_query` - 智能問答
   - `generate_project_summary` - 生成摘要
   - `semantic_search` - 語義搜尋
   - `suggest_tags` - 標籤建議
   - `analyze_content_relations` - 關聯分析

3. **資料管理**:
   - `export_memory_json` - 匯出 JSON
   - `import_memory_json` - 匯入 JSON
   - `list_memory_projects` - 列出專案

## 🐛 疑難排解

### 問題 1: Claude Code 找不到 MCP Server

**檢查方法**:
```bash
# 1. 確認 Python 路徑
which python3

# 2. 測試腳本執行
python3 /Users/wangziyan/mcp-servers/memory_mcp_server/memory_mcp_server.py --help

# 3. 檢查權限
ls -la /Users/wangziyan/mcp-servers/memory_mcp_server/memory_mcp_server.py
```

**解決方案**:
- 使用絕對路徑
- 確保 Python 可執行
- 檢查檔案權限

### 問題 2: 資料庫無法創建

**檢查方法**:
```bash
# 檢查目錄權限
ls -la ~/Documents/
ls -la ~/.memory_mcp/
```

**解決方案**:
```bash
# 手動創建目錄
mkdir -p ~/Documents/ClaudeMemory
chmod 755 ~/Documents/ClaudeMemory
```

### 問題 3: 工具無法使用

**檢查日誌**:
```bash
# 查看系統日誌
cat ~/.memory_mcp/logs/memory_mcp.log

# 即時監控日誌
tail -f ~/.memory_mcp/logs/memory_mcp.log
```

## 💡 最佳實踐

### 1. 資料庫位置建議

- **單機使用**: `~/Documents/ClaudeMemory/`
- **多機同步**: `~/OneDrive/ClaudeMemory/` 
- **開發者**: `~/Projects/ClaudeMemory/`
- **輕量用戶**: 使用預設路徑 `~/.memory_mcp/`

### 2. 專案命名規範

```
專案 ID 建議格式:
- my-web-project
- mobile-app-2024
- data-analysis-q1
- personal-notes
```

### 3. 記憶分類建議

```
推薦分類:
- architecture  (架構設計)
- decision     (決策記錄) 
- bug          (問題修復)
- feature      (功能開發)
- learning     (學習筆記)
- config       (配置記錄)
```

### 4. 定期備份

```bash
# 每週備份
cp ~/Documents/ClaudeMemory/memory.db ~/Documents/ClaudeMemory/backup/memory_$(date +%Y%m%d).db

# 或使用內建匯出功能
# 在 Claude Code 中執行: "請幫我匯出所有記憶為 JSON 格式"
```

## 📊 系統需求

- **Python**: 3.8+
- **磁碟空間**: 最少 100MB（含日誌和匯出檔案）
- **記憶體**: 最少 512MB
- **作業系統**: macOS, Linux, Windows

設定完成後，你就可以在 Claude Code 中享受智能記憶管理功能了！🎉