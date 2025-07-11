# 故障排除

## 常見問題

### 1. 伺服器無法啟動

**問題**：執行 `python3 memory_mcp_server.py` 時出現錯誤

**解決方案**：
```bash
# 檢查 Python 版本
python3 --version

# 確認版本 >= 3.8
# 如果版本過舊，請升級 Python

# 檢查檔案權限
chmod +x memory_mcp_server.py

# 檢查語法錯誤
python3 -m py_compile memory_mcp_server.py
```

### 2. Claude Code 無法連接

**問題**：IDE 顯示 MCP 伺服器連接失敗

**解決方案**：
```bash
# 確認設定檔案路徑
cat ~/.cursor/mcp.json

# 檢查路徑是否正確
ls -la /absolute/path/to/memory_mcp_server.py

# 測試伺服器手動啟動
python3 memory_mcp_server.py
```

### 3. 記憶檔案讀取錯誤

**問題**：無法讀取或寫入記憶檔案

**解決方案**：
```bash
# 檢查記憶目錄
ls -la ai-memory/

# 檢查檔案權限
chmod 755 ai-memory/
chmod 644 ai-memory/*.md

# 檢查檔案編碼
file ai-memory/*.md
```

### 4. UTF-8 編碼問題

**問題**：中文字符顯示異常

**解決方案**：
```bash
# 設定環境變數
export LANG=zh_TW.UTF-8
export LC_ALL=zh_TW.UTF-8

# 或在 Python 中設定
python3 -c "import sys; print(sys.stdout.encoding)"
```

## 偵錯模式

### 啟用詳細日誌

在 `memory_mcp_server.py` 開頭修改：

```python
logging.basicConfig(
    level=logging.DEBUG,  # 改為 DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### 手動測試

```bash
# 測試基本功能
python3 examples/test_client.py

# 檢查記憶目錄
ls -la ai-memory/

# 查看日誌
tail -f server.log
```

## 效能問題

### 記憶檔案過大

**問題**：單一記憶檔案過大導致讀取緩慢

**解決方案**：
1. 定期清理舊記憶
2. 分割大型專案記憶
3. 使用搜尋而非完整讀取

### 搜尋速度慢

**問題**：搜尋大量記憶時速度緩慢

**解決方案**：
1. 限制搜尋結果數量
2. 使用更精確的關鍵字
3. 考慮實作索引功能

## 聯絡支援

如果問題仍然存在，請：

1. 收集錯誤日誌
2. 記錄重現步驟
3. 提供系統資訊
4. 建立 GitHub Issue