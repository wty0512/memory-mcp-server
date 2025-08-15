# 使用範例

## 專案記憶使用範例

### 1. 儲存專案記憶
```
請幫我儲存這次討論的重點：
- 實作了 Python MCP 伺服器
- 使用 Markdown 管理記憶
- 支援搜尋和分類功能
專案: python-mcp-dev
標題: 伺服器實作完成
分類: development
```

### 2. 搜尋專案記憶
```
搜尋 "python-mcp-dev" 專案中關於 "MCP 伺服器" 的記錄
```

### 3. 查看專案列表
```
列出所有有記憶的專案
```

### 4. 查看最近記憶
```
顯示 "python-mcp-dev" 專案的最近 3 筆記憶
```

### 5. 取得專案統計
```
顯示 "python-mcp-dev" 專案的記憶統計資訊
```

## 全局記憶使用範例

全局記憶用於儲存跨專案共享的知識，如開發規範、最佳實踐、常用模板等。

### 1. 儲存全局記憶
```
請將這個 Git commit message 規範儲存到全局記憶：

[TAG] module_name: 簡短描述變更內容 (≤ 50 字元)

標籤說明：
- [FIX] 修正錯誤
- [ADD] 新增功能  
- [IMP] 改進功能
- [REF] 重構程式碼
- [REM] 移除功能
- [DOC] 文件更新
- [TEST] 測試相關

標題：Git Commit Message 規範
分類：開發規範
```

### 2. 儲存程式碼模板到全局記憶
```
請將這個 Python 函數模板儲存到全局記憶：

def function_name(param1: type, param2: type) -> return_type:
    """
    Brief description of the function.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ExceptionType: Description of when this exception is raised
    """
    # Implementation here
    pass

標題：Python 函數文檔模板
分類：程式碼模板
```

### 3. 查詢全局記憶
```
請查看全局記憶中的所有內容
```

### 4. 搜尋全局記憶
```
在全局記憶中搜尋關於 "Git" 的內容
```

### 5. 取得全局記憶統計
```
顯示全局記憶的統計資訊
```

### 6. 參考全局記憶進行工作
```
請參考全局記憶中的 Git commit 規範，幫我寫一個 commit message：
- 修正了用戶登入驗證的問題
- 影響的模組是 auth_service
```

## 🔍 智能搜尋功能範例

### 1. 使用智能索引搜尋
```
使用智能搜尋在 "python-mcp-dev" 專案中查找關於 "API 設計" 的內容
```

### 2. 查看專案階層結構
```
顯示 "python-mcp-dev" 專案的內容階層樹狀結構
```

### 3. 重建專案索引
```
為 "python-mcp-dev" 專案重建智能索引
```

### 4. 查看索引統計
```
顯示 "python-mcp-dev" 專案的索引統計資訊
```

### 5. 更新索引條目資訊
```
更新索引條目的階層和分類資訊
```

## 進階使用範例

### 專案記憶分類建議
- `development` - 開發相關
- `meeting` - 會議記錄
- `ideas` - 想法和靈感
- `bugs` - 錯誤和問題
- `solutions` - 解決方案

### 全局記憶分類建議
- `開發規範` / `development-standards` - 程式碼規範、Git 規範等
- `程式碼模板` / `code-templates` - 常用程式碼模板
- `最佳實踐` / `best-practices` - 開發最佳實踐
- `工具配置` / `tool-configs` - 開發工具配置
- `參考資料` / `references` - 技術參考資料

### 搜尋技巧
- 使用關鍵字搜尋內容
- 搜尋結果按相關性排序
- 支援部分匹配和模糊搜尋
- **智能索引搜尋**：基於結構化索引表的高效搜尋
- **階層化瀏覽**：按重要性和階層查看內容結構

### 記憶管理最佳實踐
- 🎯 **專案記憶**：儲存特定專案的討論、決策、進度
- 🌐 **全局記憶**：儲存通用的規範、模板、最佳實踐
- 📝 **明確分類**：使用有意義的分類標籤
- 🔍 **定期整理**：定期檢視和更新記憶內容
- 💡 **主動參考**：在需要時明確要求 AI 參考相關記憶

## 📤 匯出功能範例

### 6. 匯出專案記憶
```
# 預設 Markdown 格式匯出
請將 "python-mcp-dev" 專案的記憶匯出為 Markdown 格式

# 匯出為 JSON 檔案
請將 "python-mcp-dev" 專案匯出為 JSON 格式，儲存到 "backup/project-backup.json"

# 匯出為 CSV 格式（適合數據分析）
請將 "python-mcp-dev" 專案匯出為 CSV 格式，包含所有元數據

# 匯出為純文字格式
請將 "python-mcp-dev" 專案匯出為純文字格式，不包含元數據
```

### 匯出格式說明
- **Markdown**: 保持原始格式，適合文檔和版本控制
- **JSON**: 結構化資料，適合程式處理和 API 整合
- **CSV**: 表格化資料，適合 Excel 和數據分析
- **TXT**: 純文字格式，適合簡單閱讀和列印

### 備份建議
- 定期匯出重要專案記憶作為備份
- 使用 JSON 格式進行完整備份（包含所有元數據）
- 使用 Markdown 格式進行可讀性備份
- 使用 CSV 格式進行數據分析和統計