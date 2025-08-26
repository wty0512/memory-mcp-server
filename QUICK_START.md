# Memory MCP Server - 5分鐘快速開始

## 🚀 超簡單設定

### 方法一：自動設定（推薦）

```bash
# 1. 執行自動設定腳本
python3 setup_claude_code.py

# 2. 按照提示選擇設定
# 3. 重啟 Claude Code
# 4. 開始使用！
```

### 方法二：手動設定

1. **編輯 Claude Code 配置檔**:
   
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

2. **重啟 Claude Code**

3. **開始使用**

## 📍 預設設定

- **資料庫位置**: `~/.memory_mcp/memory.db`
- **後端類型**: SQLite
- **日誌等級**: INFO
- **日誌位置**: `~/.memory_mcp/logs/memory_mcp.log`

## 🎯 立即試用

重啟 Claude Code 後，試試這些指令：

```
# 儲存記憶
"請幫我記住：這個專案使用 React + TypeScript + Node.js"

# 搜尋記憶
"這個專案用什麼技術棧？"

# 生成摘要
"幫我生成這個專案的摘要"

# 智能標籤
"幫我為這段內容建議標籤：實作了用戶認證系統..."
```

## 🔧 進階設定

### 自定義資料庫路徑

```json
{
  "mcpServers": {
    "memory": {
      "command": "python3",
      "args": [
        "/Users/wangziyan/mcp-servers/memory_mcp_server/memory_mcp_server.py",
        "--db-path", "/your/custom/path/memory.db"
      ]
    }
  }
}
```

### 雲端同步設定

```json
{
  "mcpServers": {
    "memory": {
      "command": "python3",
      "args": [
        "/Users/wangziyan/mcp-servers/memory_mcp_server/memory_mcp_server.py",
        "--db-path", "~/OneDrive/ClaudeMemory/memory.db"
      ]
    }
  }
}
```

## ✅ 驗證設定

```bash
# 測試 MCP Server
python3 memory_mcp_server.py --info

# 檢查資料庫
ls -la ~/.memory_mcp/

# 查看日誌
tail -f ~/.memory_mcp/logs/memory_mcp.log
```

## 🆘 常見問題

**Q: Claude Code 找不到工具**
- 檢查配置檔案路徑是否正確
- 確保 Python 可執行: `which python3`
- 重啟 Claude Code

**Q: 權限錯誤**
```bash
mkdir -p ~/.memory_mcp
chmod 755 ~/.memory_mcp
```

**Q: 想要重新設定**
```bash
# 刪除配置重新開始
rm ~/.config/claude/claude_desktop_config.json
python3 setup_claude_code.py
```

## 🎉 開始享受智能記憶管理！

設定完成後，Memory MCP Server 會為你提供：

- 🧠 智能記憶存儲和檢索
- 🔍 強大的語義搜索
- 📝 自動內容摘要
- 🏷️ 智能標籤建議
- 🔗 內容關聯發現
- 💡 RAG 智能問答

現在就開始記錄你的專案知識吧！