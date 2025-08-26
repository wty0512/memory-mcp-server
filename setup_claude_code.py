#!/usr/bin/env python3
"""
Memory MCP Server - Claude Code 自動設定腳本

自動生成 Claude Code 配置檔案，簡化設定流程。
"""

import json
import os
import sys
from pathlib import Path


def get_claude_config_path():
    """取得 Claude Code 配置檔案路徑"""
    if sys.platform == "darwin":  # macOS
        return Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
    elif sys.platform.startswith("linux"):  # Linux
        return Path.home() / ".config/claude/claude_desktop_config.json"
    elif sys.platform == "win32":  # Windows
        return Path(os.getenv('APPDATA')) / "claude" / "claude_desktop_config.json"
    else:
        print(f"⚠️  不支援的作業系統: {sys.platform}")
        return None


def get_script_path():
    """取得當前腳本的絕對路徑"""
    current_script = Path(__file__).resolve()
    server_script = current_script.parent / "memory_mcp_server.py"
    return str(server_script)


def get_default_db_path():
    """取得預設資料庫路徑"""
    return str(Path.home() / ".memory_mcp/memory.db")


def get_user_preferences():
    """取得用戶偏好設定"""
    print("🔧 Memory MCP Server - Claude Code 設定精靈")
    print("=" * 50)
    
    # 1. 資料庫路徑選擇
    print("\n📁 選擇資料庫存放位置:")
    print("1. 使用預設路徑 (推薦): ~/.memory_mcp/")
    print("2. 文件目錄: ~/Documents/ClaudeMemory/")
    print("3. 自定義路徑")
    
    while True:
        choice = input("\n請選擇 (1-3): ").strip()
        if choice == "1":
            db_path = get_default_db_path()
            break
        elif choice == "2":
            db_path = str(Path.home() / "Documents/ClaudeMemory/memory.db")
            break
        elif choice == "3":
            db_path = input("請輸入完整資料庫路徑: ").strip()
            if not db_path:
                print("❌ 路徑不能為空")
                continue
            break
        else:
            print("❌ 請選擇 1-3")
    
    # 2. 日誌等級
    print("\n📊 選擇日誌詳細程度:")
    print("1. 基本 (INFO) - 推薦")
    print("2. 詳細 (DEBUG) - 除錯用")
    print("3. 最簡 (WARNING) - 只顯示警告")
    
    while True:
        choice = input("\n請選擇 (1-3): ").strip()
        if choice == "1":
            log_level = "INFO"
            break
        elif choice == "2":
            log_level = "DEBUG"
            break
        elif choice == "3":
            log_level = "WARNING"
            break
        else:
            print("❌ 請選擇 1-3")
    
    return db_path, log_level


def create_config(script_path, db_path, log_level):
    """創建 MCP 配置"""
    
    # 基本配置
    config = {
        "mcpServers": {
            "memory": {
                "command": "python3",
                "args": [
                    script_path,
                    "--backend", "sqlite",
                    "--log-level", log_level
                ]
            }
        }
    }
    
    # 如果不是預設路徑，添加 db-path 參數
    default_path = get_default_db_path()
    if db_path != default_path:
        config["mcpServers"]["memory"]["args"].extend([
            "--db-path", db_path
        ])
    
    return config


def backup_existing_config(config_path):
    """備份現有配置檔案"""
    if config_path.exists():
        backup_path = config_path.with_suffix('.json.backup')
        try:
            config_path.rename(backup_path)
            print(f"✅ 已備份現有配置到: {backup_path}")
            return True
        except Exception as e:
            print(f"⚠️  備份配置失敗: {e}")
            return False
    return True


def merge_with_existing_config(config_path, new_config):
    """與現有配置合併"""
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                existing_config = json.load(f)
            
            # 合併配置
            if "mcpServers" not in existing_config:
                existing_config["mcpServers"] = {}
            
            existing_config["mcpServers"]["memory"] = new_config["mcpServers"]["memory"]
            return existing_config
        except Exception as e:
            print(f"⚠️  讀取現有配置失敗: {e}")
            return new_config
    
    return new_config


def save_config(config_path, config):
    """儲存配置檔案"""
    try:
        # 確保目錄存在
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 寫入配置
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        print(f"❌ 儲存配置失敗: {e}")
        return False


def test_configuration(script_path):
    """測試配置是否正確"""
    print("\n🧪 測試配置...")
    
    try:
        import subprocess
        result = subprocess.run([
            "python3", script_path, "--info"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ 配置測試成功！")
            return True
        else:
            print(f"❌ 配置測試失敗:")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"⚠️  測試過程中發生錯誤: {e}")
        return False


def main():
    """主程式"""
    try:
        # 1. 檢查作業系統支援
        config_path = get_claude_config_path()
        if not config_path:
            sys.exit(1)
        
        # 2. 取得腳本路徑
        script_path = get_script_path()
        if not Path(script_path).exists():
            print(f"❌ 找不到 MCP Server 腳本: {script_path}")
            sys.exit(1)
        
        # 3. 取得用戶偏好
        db_path, log_level = get_user_preferences()
        
        # 4. 創建配置
        new_config = create_config(script_path, db_path, log_level)
        
        # 5. 處理現有配置
        print(f"\n💾 準備寫入配置到: {config_path}")
        
        if config_path.exists():
            print("發現現有 Claude Code 配置檔案")
            choice = input("要合併到現有配置嗎？(Y/n): ").strip().lower()
            if choice in ['', 'y', 'yes']:
                final_config = merge_with_existing_config(config_path, new_config)
                backup_existing_config(config_path)
            else:
                final_config = new_config
        else:
            final_config = new_config
        
        # 6. 儲存配置
        if save_config(config_path, final_config):
            print("✅ 配置檔案已成功創建！")
            
            # 7. 測試配置
            test_configuration(script_path)
            
            # 8. 顯示設定摘要
            print("\n" + "=" * 50)
            print("🎉 設定完成！")
            print("=" * 50)
            print(f"📍 配置檔案: {config_path}")
            print(f"🗄️  資料庫路徑: {db_path}")
            print(f"📊 日誌等級: {log_level}")
            print(f"🔧 MCP Server: {script_path}")
            
            # 確保資料庫目錄存在
            db_dir = Path(db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            print(f"📁 已創建資料庫目錄: {db_dir}")
            
            print("\n📝 使用說明:")
            print("1. 重啟 Claude Code 應用程式")
            print("2. 開始使用記憶管理功能")
            print('3. 範例: "請幫我儲存這個專案的架構筆記..."')
            
            print("\n🆘 如需幫助:")
            print(f"- 查看詳細指南: {Path(__file__).parent}/SETUP_GUIDE.md")
            print("- 測試配置: python3 memory_mcp_server.py --info")
        else:
            print("❌ 配置設定失敗！")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n👋 設定已取消")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 設定過程中發生錯誤: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()