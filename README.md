# Python Markdown Memory MCP Server

一個基於 Python 的 Model Context Protocol (MCP) 伺服器，使用 Markdown 檔案管理 AI 對話記憶和專案上下文。

## 🚀 功能特色

- 📝 使用 Markdown 格式儲存和管理記憶
- 🔍 強大的搜尋功能
- 📊 專案分類管理
- 🕒 時間戳記跟蹤
- 🎯 與 Claude Desktop / Claude Code / Cursor / Rovo Dev 完美整合
- 🚀 支援 Rovo Dev 的 `acli` 命令管理
- 🐍 純 Python 實作，無額外依賴

## 🛠️ 安裝和設定

### 1. 環境需求

- Python 3.8+
- Claude Code 或 Cursor IDE
- 作業系統：Windows、macOS、Linux

### 2. 快速安裝

```bash
# 克隆專案
git clone https://github.com/wty0512/markdown-memory-mcp-server.git
cd markdown-memory-mcp-server

# 創建虛擬環境（可選但推薦）
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 檢查依賴（目前使用 Python 標準庫，無需額外依賴）
# pip install -r requirements.txt  # 目前無需執行此步驟

# 設定執行權限（macOS/Linux）
chmod +x memory_mcp_server.py
chmod +x start_server.sh
```

### 3. 設定 Claude Desktop

#### 步驟 1: 找到設定檔位置
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

#### 步驟 2: 編輯設定檔
打開設定檔並添加以下配置（**請替換路徑為你的實際路徑**）：

```json
{
  "mcpServers": {
    "markdown-memory": {
      "command": "python3",
      "args": ["/完整路徑/到/markdown-memory-mcp-server/memory_mcp_server.py"],
      "transport": "stdio",
      "env": {
        "PYTHONPATH": "/完整路徑/到/markdown-memory-mcp-server",
        "PYTHONIOENCODING": "utf-8"
      },
      "cwd": "/完整路徑/到/markdown-memory-mcp-server"
    }
  }
}
```

#### 步驟 3: 獲取完整路徑
在專案目錄中執行以下命令獲取完整路徑：

```bash
# 在 markdown-memory-mcp-server 目錄中執行
pwd
# 複製輸出的路徑，替換上面配置中的 "/完整路徑/到/markdown-memory-mcp-server"
```

#### Claude Code / Cursor 設定

**設定檔位置**：
- **macOS/Linux**: `~/.cursor/mcp.json`
- **Windows**: `%USERPROFILE%\.cursor\mcp.json`

**方法 1: 全域設定**
編輯設定檔：
```json
{
  "mcpServers": {
    "markdown-memory": {
      "command": "python3",
      "args": ["/absolute/path/to/memory_mcp_server.py"],
      "transport": "stdio",
      "env": {
        "PYTHONPATH": "/absolute/path/to/markdown-memory-mcp-server"
      }
    }
  }
}
```

**方法 2: 專案設定**
在專案根目錄創建 `.cursor/mcp.json`（所有作業系統相同）：
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

#### Rovo Dev 設定 🚀

**設定檔位置**：
- **macOS/Linux**: `~/.rovodev/mcp.json`
- **Windows**: `%USERPROFILE%\.rovodev\mcp.json`

**為什麼 Rovo Dev 需要這個記憶伺服器？**
- 🔄 Rovo Dev 每個資料夾都是獨立的工作環境
- 💾 內建記憶功能不會持久化儲存到檔案
- 🚫 無法跨專案或跨資料夾記住開發歷程和知識
- 🧠 需要外部記憶系統來維持長期記憶和學習積累

**快速設定（推薦方法）**
```bash
# 開啟 MCP 設定檔
acli rovodev mcp

# 查看 Rovo Dev 日誌
acli rovodev log

# 啟動 Rovo Dev（設定完成後）
acli rovodev run
```

**手動設定方式**
編輯 `~/.rovodev/mcp.json`：
```json
{
  "mcpServers": {
    "markdown-memory": {
      "command": "python3",
      "args": ["/absolute/path/to/memory_mcp_server.py"],
      "transport": "stdio",
      "env": {
        "PYTHONPATH": "/absolute/path/to/markdown-memory-mcp-server",
        "PYTHONIOENCODING": "utf-8",
        "PATH": "/usr/local/bin:/usr/bin:/bin"
      },
      "cwd": "/absolute/path/to/markdown-memory-mcp-server"
    }
  }
}
```

**Rovo Dev 專用配置範例**
```json
{
  "mcpServers": {
    "markdown-memory": {
      "command": "python3",
      "args": ["/absolute/path/to/memory_mcp_server.py"],
      "transport": "stdio",
      "env": {
        "PYTHONPATH": "/absolute/path/to/markdown-memory-mcp-server",
        "PYTHONIOENCODING": "utf-8"
      },
      "cwd": "/absolute/path/to/markdown-memory-mcp-server",
      "capabilities": {
        "tools": true,
        "resources": false,
        "prompts": false
      }
    }
  },
  "globalSettings": {
    "logLevel": "info",
    "timeout": 30000
  }
}
```

**驗證 Rovo Dev 設定**
```bash
# 檢查設定檔是否正確
acli rovodev mcp --validate

# 測試 MCP 伺服器連接
acli rovodev test-mcp markdown-memory

# 查看所有已配置的 MCP 伺服器
acli rovodev list-mcp
```

## 📖 使用說明

### 重啟應用程式
設定完成後：
- **Claude Desktop**: 完全關閉並重新啟動 Claude Desktop
- **Rovo Dev**: 執行 `acli rovodev restart` 或 `acli rovodev run`
- **Cursor**: 重新載入視窗 (Ctrl/Cmd + Shift + P → "Developer: Reload Window")

### ⚠️ 重要說明

**記憶功能需要主動指令才會記錄**：
- ❌ **不會自動記錄**：系統不會自動保存每次對話
- ✅ **需要明確指示**：你必須主動告訴 AI 要記錄什麼內容
- 🔒 **隱私保護**：確保只有你想要的內容被保存
- 🎯 **精準記錄**：避免無用信息堆積，讓記憶更有價值

### 基本使用

1. **儲存記憶**
```
請幫我儲存這次討論的重點：
- 實作了 Python MCP 伺服器
- 使用 Markdown 管理記憶
- 支援搜尋和分類功能
專案ID: python-mcp-dev
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

4. **查看記憶統計**
```
顯示 "python-mcp-dev" 專案的記憶統計信息
```

### 可用功能
- `save_memory` - 保存記憶到指定專案
- `get_memory` - 獲取專案的完整記憶
- `search_memory` - 搜尋記憶內容
- `list_projects` - 列出所有專案
- `get_recent_memory` - 獲取最近的記憶條目
- `get_memory_stats` - 獲取記憶統計信息
- `delete_memory` - 刪除專案記憶（謹慎使用）

## 🚀 部署和整合

### 與 Claude Desktop / Claude Code 整合

1. **安裝和設定**
```bash
cd /path/to/your/project
python3 memory_mcp_server.py
```

2. **設定 Claude Desktop**
編輯設定檔 `claude_desktop_config.json`：
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

3. **設定 Cursor/Claude Code**
編輯 `mcp.json`：
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

1. **Claude Desktop 沒有顯示記憶功能**
   - 確認設定檔路徑正確
   - 檢查 JSON 格式是否有效（使用 JSON 驗證器）
   - 完全重啟 Claude Desktop
   - 檢查路徑是否使用完整絕對路徑

2. **伺服器無法啟動**
```bash
# 檢查 Python 版本（需要 3.8+）
python3 --version

# 檢查檔案權限（macOS/Linux）
chmod +x memory_mcp_server.py

# 手動測試伺服器
cd markdown-memory-mcp-server
python3 memory_mcp_server.py
```

3. **路徑相關錯誤**
```bash
# 獲取當前完整路徑
pwd

# 檢查記憶目錄是否創建
ls -la ai-memory/

# 檢查檔案權限
ls -la memory_mcp_server.py
```

4. **Windows 用戶常見問題**
   - 路徑使用反斜線 `\` 或雙反斜線 `\\`
   - 設定檔位置：`%APPDATA%\Claude\claude_desktop_config.json`
   - Python 命令可能是 `python` 或 `python3`，取決於安裝方式
   
   **檢查 Windows Python 命令**：
   ```bash
   # 測試哪個命令可用
   python --version
   python3 --version
   ```
   
   **Windows 配置範例**：
   ```json
   {
     "mcpServers": {
       "markdown-memory": {
         "command": "python3",
         "args": ["C:\\path\\to\\memory_mcp_server.py"],
         "transport": "stdio",
         "env": {
           "PYTHONPATH": "C:\\path\\to\\markdown-memory-mcp-server",
           "PYTHONIOENCODING": "utf-8"
         },
         "cwd": "C:\\path\\to\\markdown-memory-mcp-server"
       }
     }
   }
   ```
   
   **如果 `python3` 不可用，改用 `python`**：
   ```json
   {
     "mcpServers": {
       "markdown-memory": {
         "command": "python",
         "args": ["C:\\path\\to\\memory_mcp_server.py"],
         "transport": "stdio",
         "env": {
           "PYTHONPATH": "C:\\path\\to\\markdown-memory-mcp-server",
           "PYTHONIOENCODING": "utf-8"
         },
         "cwd": "C:\\path\\to\\markdown-memory-mcp-server"
       }
     }
   }
   ```

5. **Rovo Dev 專用故障排除**
   ```bash
   # 檢查 Rovo Dev 是否正確安裝
   acli --version
   
   # 驗證 MCP 設定檔格式
   acli rovodev mcp --validate
   
   # 查看詳細日誌
   acli rovodev log --tail
   
   # 重啟 Rovo Dev 服務
   acli rovodev restart
   
   # 測試記憶伺服器連接
   acli rovodev test-mcp markdown-memory
   ```
   
   **常見 Rovo Dev 錯誤**：
   - ❌ `MCP server not found`: 檢查路徑是否正確
   - ❌ `Python command failed`: 確認 Python 環境設定
   - ❌ `Permission denied`: 檢查檔案執行權限
   - ❌ `Connection timeout`: 增加 timeout 設定值

### 驗證安裝

1. **測試伺服器啟動**
```bash
cd markdown-memory-mcp-server
python3 -c "from memory_mcp_server import MCPServer; print('✅ 伺服器可以正常導入')"
```

2. **檢查設定檔**
```bash
# macOS
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Windows
type %APPDATA%\Claude\claude_desktop_config.json
```

### 獲取幫助
如果遇到問題，請在 GitHub Issues 中提供：
- 作業系統版本
- Python 版本
- 錯誤訊息
- Claude Desktop 設定檔內容

---

**享受您的 AI 記憶管理系統！** 🚀

有任何問題或建議，請隨時提出！