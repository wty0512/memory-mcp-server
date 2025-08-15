# Python Memory MCP Server
# Python 記憶管理 MCP 伺服器

一個基於 Python 的 Model Context Protocol (MCP) 伺服器，提供智能記憶管理功能，支援 SQLite 和 Markdown 雙後端儲存。

A Python-based Model Context Protocol (MCP) server providing intelligent memory management with SQLite and Markdown dual backend storage support.

**[English Version / 英文版本](README_EN.md)**

## 🚀 功能特色 / Features

### 🏗️ **全新架構 2.0** / **New Architecture 2.0**
- ✨ **簡化架構**：從 25+ 個表簡化為 7 個表（簡化 72%）  
  **Simplified Architecture**: Reduced from 25+ tables to 7 tables (72% reduction)
- 🚀 **統一資料模型**：單一主表設計，邏輯清晰易維護  
  **Unified Data Model**: Single main table design, clear and maintainable logic
- ⚡ **高效能搜尋**：SQLite FTS5 全文搜尋 + Trigram 分詞器，完美支援中文搜尋  
  **High-Performance Search**: SQLite FTS5 full-text search + Trigram tokenizer, perfect Chinese search support
- 🔒 **資料完整性**：100% 資料遷移保證，無資料遺失  
  **Data Integrity**: 100% data migration guarantee, no data loss

### 💾 **雙後端支援** / **Dual Backend Support**
- 🗄️ **SQLite 後端**（預設）：高效能資料庫儲存，支援複雜查詢  
  **SQLite Backend** (Default): High-performance database storage with complex query support
- 📝 **Markdown 後端**：人類可讀的檔案格式，便於版本控制  
  **Markdown Backend**: Human-readable file format, version control friendly
- 🔄 **智能同步**：自動將 Markdown 專案同步到 SQLite  
  **Intelligent Sync**: Automatically sync Markdown projects to SQLite

### 🎯 **核心功能** / **Core Features**
- 📤 **多格式匯出**：支援 Markdown、JSON、CSV、TXT 格式匯出  
  **Multi-format Export**: Support export to Markdown, JSON, CSV, TXT formats
- 🔍 **智能搜尋**：全文搜尋、分類篩選、專案內搜尋  
  **Intelligent Search**: Full-text search, category filtering, project-specific search
- 📊 **專案管理**：分類管理、統計分析、專案重命名  
  **Project Management**: Category management, statistical analysis, project renaming
- 🕒 **時間追蹤**：創建時間、更新時間自動記錄  
  **Time Tracking**: Automatic creation and update timestamp recording
- ✏️ **條目管理**：新增、編輯、刪除特定記憶條目  
  **Entry Management**: Add, edit, delete specific memory entries
- 🎯 **精確定位**：根據ID、時間戳、標題、分類、內容匹配  
  **Precise Targeting**: By ID, timestamp, title, category, content matching
- 📋 **條目列表**：方便查看和管理所有記憶條目  
  **Entry Listing**: Easy viewing and management of all memory entries

### 🌐 **整合支援** / **Integration Support**
- 🚀 **啟動時自動顯示專案列表**，提升使用體驗  
  **Auto project list display on startup** for enhanced user experience
- 🎯 與 Claude Desktop / Claude Code / Cursor / Rovo Dev 完美整合  
  Perfect integration with Claude Desktop / Claude Code / Cursor / Rovo Dev
- 🚀 支援 Rovo Dev 的 `acli` 命令管理  
  Support for Rovo Dev's `acli` command management
- 🌐 **全局記憶**：跨專案共享的知識庫，儲存通用規範和最佳實踐  
  **Global Memory**: Cross-project knowledge base for storing universal standards and best practices
- 🐍 純 Python 實作，無額外依賴  
  Pure Python implementation with no additional dependencies

## 🛠️ 安裝和設定 / Installation and Setup

### 1. 環境需求 / System Requirements

- Python 3.8+
- Claude Code 或 Cursor IDE / Claude Code or Cursor IDE
- 作業系統：Windows、macOS、Linux / Operating Systems: Windows, macOS, Linux

### 2. 快速安裝 / Quick Installation

```bash
# 克隆專案 / Clone the project
git clone https://github.com/wty0512/memory-mcp-server.git
cd memory-mcp-server

# 創建虛擬環境（可選但推薦）/ Create virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 檢查依賴（目前使用 Python 標準庫，無需額外依賴）
# Check dependencies (currently uses Python standard library, no additional dependencies needed)
# pip install -r requirements.txt  # 目前無需執行此步驟 / Currently not needed

# 設定執行權限（macOS/Linux）/ Set execution permissions (macOS/Linux)
chmod +x memory_mcp_server.py
chmod +x start_server.sh

# 🚀 首次啟動會自動同步現有 Markdown 專案到 SQLite
# 🚀 First startup will automatically sync existing Markdown projects to SQLite
# 如果您有現有的 Markdown 記憶檔案，系統會自動處理
# If you have existing Markdown memory files, the system will handle them automatically
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

## 📊 架構說明 / Architecture

### 🏗️ **新架構 2.0** / **New Architecture 2.0**

經過全面重構，Memory MCP Server 現在採用簡化且高效的架構：

After comprehensive refactoring, Memory MCP Server now uses a simplified and efficient architecture:

```
Memory MCP Server 2.0 (SQLite)
├── 🗄️ 核心資料表 / Core Data Table
│   └── memory_entries        # 統一記憶條目表 / Unified memory entries table
│       ├── id               # 唯一識別碼 / Unique identifier
│       ├── project          # 專案名稱 / Project name
│       ├── category         # 分類標籤 / Category tag
│       ├── entry_type       # 條目類型 / Entry type
│       ├── title            # 標題 / Title
│       ├── summary          # 摘要 / Summary
│       ├── entry            # 內容 / Content
│       ├── created_at       # 創建時間 / Creation time
│       └── updated_at       # 更新時間 / Update time
├── 🔍 全文搜尋系統 / Full-Text Search System
│   ├── memory_fts           # FTS5 搜尋表 / FTS5 search table
│   └── 自動觸發器 / Auto triggers (INSERT/UPDATE/DELETE)
├── 📊 索引系統 / Index System
│   ├── idx_memory_project   # 專案索引 / Project index
│   ├── idx_memory_category  # 分類索引 / Category index
│   └── idx_memory_created   # 時間索引 / Time index
└── ⚡ 效能優化 / Performance Optimization
    ├── 單表查詢 / Single table queries
    ├── 高效索引 / Efficient indexing
    └── FTS5 全文搜尋 / FTS5 full-text search
```

### 🎯 **架構優勢** / **Architecture Advantages**

- **📉 複雜度降低 72%**：從 25+ 個表簡化為 7 個表  
  **72% Complexity Reduction**: From 25+ tables to 7 tables
- **🚀 查詢效能提升**：單表查詢，無複雜關聯  
  **Enhanced Query Performance**: Single table queries, no complex joins
- **🔧 維護性提升**：統一的資料模型，邏輯清晰  
  **Improved Maintainability**: Unified data model, clear logic
- **💾 儲存效率**：獨立欄位儲存，節省 tokens  
  **Storage Efficiency**: Independent field storage, token savings
- 🔍 **搜尋優化**：FTS5 + Trigram 分詞器，完美支援中文全文搜尋  
  **Search Optimization**: FTS5 + Trigram tokenizer, perfect Chinese full-text search support

### 🔄 **資料遷移** / **Data Migration**

系統會自動檢測並遷移舊版本的資料：

The system automatically detects and migrates data from older versions:

- ✅ **自動檢測**：啟動時自動檢查是否需要遷移  
  **Auto Detection**: Automatically checks for migration needs on startup
- 🔒 **安全遷移**：100% 資料完整性保證  
  **Safe Migration**: 100% data integrity guarantee
- 📊 **遷移報告**：詳細的遷移狀態和統計  
  **Migration Report**: Detailed migration status and statistics
- 🚀 **無縫升級**：用戶無需手動操作  
  **Seamless Upgrade**: No manual intervention required

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

#### 專案記憶操作

1. **儲存專案記憶**
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

#### 全局記憶操作

全局記憶用於儲存跨專案共享的知識，如開發規範、最佳實踐、常用模板等。

1. **儲存全局記憶**
```
請將這個 Git commit message 規範儲存到全局記憶：

[TAG] module_name: 簡短描述變更內容 (≤ 50 字元)

標籤說明：
- [FIX] 修正錯誤
- [ADD] 新增功能  
- [IMP] 改進功能
- [REF] 重構程式碼

標題：Git Commit 規範
分類：開發規範
```

2. **查詢全局記憶**
```
請查看全局記憶中的所有內容
```

3. **搜尋全局記憶**
```
在全局記憶中搜尋關於 "Git" 的內容
```

**使用建議**：
- 🎯 **專案記憶**：儲存特定專案的討論、決策、進度
- 🌐 **全局記憶**：儲存通用的規範、模板、最佳實踐
- 💡 **主動參考**：在需要時明確要求 AI 參考相關記憶

### 可用功能

#### 專案記憶功能
- `save_project_memory` - 保存記憶到指定專案
- `get_project_memory` - 獲取專案的完整記憶
- `search_project_memory` - 搜尋專案記憶內容
- `list_memory_projects` - 列出所有專案
- `get_recent_project_memory` - 獲取最近的記憶條目
- `get_project_memory_stats` - 獲取記憶統計信息
- `delete_project_memory` - 刪除專案記憶（謹慎使用）
- `🆕 list_project_memory_entries` - 列出專案中的所有記憶條目（帶ID編號）
- `🆕 delete_project_memory_entry` - 刪除特定的記憶條目
- `🆕 edit_project_memory_entry` - 編輯特定的記憶條目
- `📤 export_project_memory` - 匯出專案記憶為多種格式（Markdown、JSON、CSV、TXT）

#### 全局記憶功能
- `🌐 save_global_memory` - 儲存內容到全局記憶
- `🌐 get_global_memory` - 獲取所有全局記憶內容
- `🌐 search_global_memory` - 搜尋全局記憶內容
- `🌐 get_global_memory_stats` - 獲取全局記憶統計信息

## 🔍 智能搜尋使用指南

### 智能索引搜尋
```
# 使用智能搜尋查找內容
使用智能搜尋在 "專案名稱" 中查找關於 "關鍵字" 的內容

# 查看專案階層結構
顯示 "專案名稱" 的內容階層樹狀結構

# 重建專案索引
為 "專案名稱" 重建智能索引

# 查看索引統計
顯示 "專案名稱" 的索引統計資訊
```

## 🆕 新功能使用指南


### 精確的記憶條目管理

#### 1. 列出所有記憶條目
```
使用 list_memory_entries 工具查看專案中的所有記憶條目，每個條目都有唯一的ID編號：

參數：
- project_id: 專案識別碼

範例回應：
1. 2025-01-15 10:30:00 - 會議記錄 #工作
   今天的團隊會議討論了新功能開發...

2. 2025-01-15 14:20:00 - 程式碼筆記 #開發
   實作了新的API端點...
```

#### 2. 刪除特定記憶條目
```
使用 delete_memory_entry 工具可以根據多種條件刪除特定條目：

參數：
- project_id: 專案識別碼（必需）
- entry_id: 條目ID（1-based索引）
- timestamp: 時間戳模式匹配
- title: 標題模式匹配
- category: 分類模式匹配
- content_match: 內容模式匹配

範例：
- 刪除第2個條目：entry_id="2"
- 刪除所有包含"測試"分類的條目：category="測試"
- 刪除標題包含"會議"的條目：title="會議"
- 刪除特定日期的條目：timestamp="2025-01-15"
- 刪除內容包含特定關鍵字的條目：content_match="API"
```

#### 3. 編輯記憶條目
```
使用 edit_memory_entry 工具編輯現有條目的內容：

參數：
- project_id: 專案識別碼（必需）
- entry_id: 條目ID（1-based索引）
- timestamp: 時間戳模式匹配（用於查找條目）
- new_title: 新標題
- new_category: 新分類
- new_content: 新內容

範例：
- 編輯第1個條目的標題：entry_id="1", new_title="更新的標題"
- 修改條目內容：entry_id="2", new_content="這是更新後的內容"
- 更改分類：entry_id="3", new_category="已完成"
```

#### 4. 匯出專案記憶
```
使用 export_project_memory 工具將專案記憶匯出為不同格式：

參數：
- project_id: 專案識別碼（必需）
- format: 匯出格式（可選，預設：markdown）
  - "markdown" - Markdown 格式，保持原始格式
  - "json" - JSON 格式，結構化資料
  - "csv" - CSV 格式，適合數據分析
  - "txt" - 純文字格式，移除標記
- output_path: 輸出檔案路徑（可選，不指定則直接顯示內容）
- include_metadata: 是否包含元數據（可選，預設：true）

範例：
- 預設 Markdown 格式：export_project_memory(project_id="my-project")
- 匯出為 JSON 檔案：export_project_memory(project_id="my-project", format="json", output_path="backup.json")
- 匯出為 CSV：export_project_memory(project_id="my-project", format="csv")
- 純文字格式：export_project_memory(project_id="my-project", format="txt", include_metadata=false)
```

### 使用建議

1. **先列出條目**：使用 `list_memory_entries` 查看所有條目和它們的ID
2. **精確刪除**：使用條目ID進行精確刪除，或使用模式匹配批量刪除
3. **安全編輯**：編輯前建議先備份重要資料
4. **分類管理**：善用分類功能來組織和管理記憶條目
5. **📤 定期備份**：使用匯出功能定期備份重要專案記憶

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

## 📋 更新日誌 / Changelog

### 🎉 **版本 2.0.0 - 架構重構完成** / **Version 2.0.0 - Architecture Refactoring Complete**

- ✨ **全新架構**：從 25+ 個表簡化為 7 個表（簡化 72%）
- 🚀 **效能提升**：FTS5 + Trigram 全文搜尋，查詢速度提升 3-5 倍
- 🔒 **資料安全**：100% 自動資料遷移，無資料遺失
- 🔧 **維護性**：統一資料模型，邏輯清晰易維護
- 🎯 **完美測試**：43/43 測試通過（100%），混合搜尋策略確保準確性

詳細更新內容請查看 [CHANGELOG.md](CHANGELOG.md)

For detailed update information, please see [CHANGELOG.md](CHANGELOG.md)

---

有任何問題或建議，請隨時提出！