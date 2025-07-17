# 安裝說明

## 系統需求

- Python 3.8 或更高版本
- Claude Code 或 Cursor IDE
- 支援的作業系統：Windows、macOS、Linux

## 後端選擇

本系統支援兩種儲存後端：

- **SQLite**（預設推薦）：高效能資料庫，支援全文搜尋和複雜查詢
- **Markdown**：人類可讀格式，便於版本控制和手動編輯

系統會自動將現有 Markdown 專案同步到 SQLite，無需手動轉換。

## 安裝步驟

### 1. 下載專案

```bash
git clone https://github.com/your-username/markdown-memory-mcp.git
cd markdown-memory-mcp
```

### 2. 設定 Python 環境

```bash
# 創建虛擬環境（推薦）
python3 -m venv venv

# 啟動虛擬環境
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 安裝依賴（目前無額外依賴）
pip install -r requirements.txt
```

### 3. 設定執行權限

```bash
chmod +x memory_mcp_server.py
chmod +x start_server.sh
```

### 4. 測試安裝

```bash
python3 memory_mcp_server.py --help
```

## 設定 IDE

### Claude Code / Cursor 設定

#### 全域設定
編輯 `~/.cursor/mcp.json`：

```json
{
  "mcpServers": {
    "memory-server": {
      "command": "python3",
      "args": ["/absolute/path/to/memory_mcp_server.py", "--backend=sqlite"],
      "transport": "stdio",
      "env": {
        "PYTHONPATH": "/absolute/path/to/markdown-memory-mcp"
      }
    }
  }
}
```

#### 專案設定
在專案根目錄創建 `.cursor/mcp.json`：

```json
{
  "mcpServers": {
    "memory-server": {
      "command": "python3",
      "args": ["./memory_mcp_server.py", "--backend=sqlite"],
      "transport": "stdio"
    }
  }
}
```

#### 後端選項
- 使用 SQLite（預設推薦）：`--backend=sqlite`
- 使用 Markdown：`--backend=markdown`
- 不指定參數時預設使用 Markdown（向後兼容）

## 驗證安裝

1. 啟動伺服器：
```bash
./start_server.sh
```

2. 在 Claude Code 中測試：
```
列出所有有記憶的專案
```

如果看到回應，表示安裝成功！