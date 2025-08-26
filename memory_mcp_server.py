#!/usr/bin/env python3
"""
Python Memory MCP Server
一個基於 Python 的 Model Context Protocol 伺服器，提供記憶管理功能，支援 SQLite 和 Markdown 雙後端儲存

A Python-based Model Context Protocol server providing memory management 
with SQLite and Markdown dual backend storage support.

Features / 功能特色:
- SQLite Backend (Default): High-performance database with full-text search
  SQLite 後端（預設）：高效能資料庫，支援全文搜尋
- Markdown Backend: Human-readable format for version control
  Markdown 後端：人類可讀格式，便於版本控制
- Auto Sync: Auto-sync Markdown projects to SQLite
  自動同步：自動將 Markdown 專案同步到 SQLite
- Auto Project Display: Show project list on startup
  自動專案顯示：啟動時顯示專案列表
"""

import asyncio
import json
import logging
import os
import sys
import sqlite3
import time
import csv
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from abc import ABC, abstractmethod
from contextlib import contextmanager
import difflib
import re

# 跨平台檔案鎖定支援
try:
    import fcntl  # Unix/Linux/macOS
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

try:
    import msvcrt  # Windows
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

# 結構化日誌系統
class StructuredLogger:
    """結構化日誌記錄器"""
    
    def __init__(self, name: str = __name__, config_manager=None):
        self.logger = logging.getLogger(name)
        self.config = config_manager
        self._setup_logging()
    
    def _setup_logging(self):
        """設定日誌配置"""
        if self.config:
            level_str = self.config.get('logging', 'level', 'INFO')
            level = getattr(logging, level_str.upper(), logging.INFO)
            format_str = self.config.get('logging', 'format', 
                                       '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        else:
            level = logging.INFO
            format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        # 如果已經有 handler 就不重複設定
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(format_str)
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(level)
    
    def _format_structured(self, message: str, context: dict = None, **kwargs) -> str:
        """格式化結構化訊息"""
        parts = [message]
        
        # 合併 context 和 kwargs
        all_context = {}
        if context:
            all_context.update(context)
        all_context.update(kwargs)
        
        if all_context:
            context_str = " | ".join([f"{k}={v}" for k, v in all_context.items()])
            parts.append(f"[{context_str}]")
        
        return " ".join(parts)
    
    def debug(self, message: str, context: dict = None, **kwargs):
        """除錯級別日誌"""
        formatted = self._format_structured(message, context, **kwargs)
        self.logger.debug(formatted)
    
    def info(self, message: str, context: dict = None, **kwargs):
        """資訊級別日誌"""
        formatted = self._format_structured(message, context, **kwargs)
        self.logger.info(formatted)
    
    def warning(self, message: str, context: dict = None, **kwargs):
        """警告級別日誌"""
        formatted = self._format_structured(message, context, **kwargs)
        self.logger.warning(formatted)
    
    def error(self, message: str, context: dict = None, **kwargs):
        """錯誤級別日誌"""
        formatted = self._format_structured(message, context, **kwargs)
        self.logger.error(formatted)
    
    def critical(self, message: str, context: dict = None, **kwargs):
        """嚴重錯誤級別日誌"""
        formatted = self._format_structured(message, context, **kwargs)
        self.logger.critical(formatted)
    
    def operation(self, operation: str, status: str, context: dict = None, **kwargs):
        """操作日誌"""
        all_context = {'operation': operation, 'status': status}
        if context:
            all_context.update(context)
        all_context.update(kwargs)
        
        if status.lower() in ['success', 'completed', 'ok']:
            self.info(f"Operation {operation} completed", all_context)
        elif status.lower() in ['error', 'failed', 'failure']:
            self.error(f"Operation {operation} failed", all_context)
        else:
            self.info(f"Operation {operation} status: {status}", all_context)
    
    def performance(self, operation: str, duration: float, context: dict = None, **kwargs):
        """效能日誌"""
        all_context = {'operation': operation, 'duration_ms': round(duration * 1000, 2)}
        if context:
            all_context.update(context)
        all_context.update(kwargs)
        
        if duration > 5.0:  # 超過5秒記為警告
            self.warning(f"Slow operation: {operation}", all_context)
        elif duration > 1.0:  # 超過1秒記為資訊
            self.info(f"Performance: {operation}", all_context)
        else:
            self.debug(f"Performance: {operation}", all_context)

# 設定全域日誌記錄器（等配置管理器初始化後會重新配置）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = StructuredLogger(__name__)

# 自定義異常類別
class ValidationError(ValueError):
    """輸入驗證錯誤"""
    pass

class SecurityError(Exception):
    """安全性相關錯誤"""
    pass

class DatabaseError(Exception):
    """資料庫操作錯誤"""
    pass

class FileOperationError(Exception):
    """檔案操作錯誤"""
    pass

class ConfigurationError(Exception):
    """配置錯誤"""
    pass

# 輸入驗證工具
class InputValidator:
    """輸入參數驗證器"""
    
    # 專案ID規則：只允許字母、數字、底線、連字號，長度限制
    @classmethod
    def _get_project_id_pattern(cls):
        max_len = config.get('validation', 'max_project_id_length', 100)
        return re.compile(f'^[a-zA-Z0-9_-]{{1,{max_len}}}$')
    
    @classmethod
    def _get_limits(cls):
        return {
            'content': config.get('validation', 'max_content_length', 50 * 1024 * 1024),
            'title': config.get('validation', 'max_title_length', 500),
            'category': config.get('validation', 'max_category_length', 100),
            'query': config.get('validation', 'max_query_length', 1000),
        }
    
    @classmethod
    def validate_project_id(cls, project_id: str) -> str:
        """驗證專案ID格式"""
        if not project_id or not isinstance(project_id, str):
            raise ValidationError("專案ID不能為空且必須為字串")
        
        project_id = project_id.strip()
        if not project_id:
            raise ValidationError("專案ID不能為空白")
        
        pattern = cls._get_project_id_pattern()
        max_len = config.get('validation', 'max_project_id_length', 100)
        if not pattern.match(project_id):
            raise ValidationError(
                f"專案ID只能包含英文字母、數字、底線和連字號，長度不超過{max_len}字元"
            )
        
        # 檢查保留字
        reserved_words = {'global', 'system', 'admin', 'root', 'config'}
        if project_id.lower() in reserved_words:
            raise ValidationError(f"'{project_id}' 是保留字，不能作為專案ID")
        
        return project_id
    
    @classmethod
    def validate_content(cls, content: str) -> str:
        """驗證內容格式和長度"""
        if not isinstance(content, str):
            raise ValidationError("內容必須為字串")
        
        limits = cls._get_limits()
        if len(content) > limits['content']:
            raise ValidationError(f"內容長度不能超過 {limits['content'] // (1024*1024)} MB")
        
        # 檢查是否包含惡意內容
        if cls._contains_suspicious_patterns(content):
            raise SecurityError("內容包含可疑模式，可能存在安全風險")
        
        return content
    
    @classmethod
    def validate_title(cls, title: str) -> str:
        """驗證標題格式和長度"""
        if title is None:
            return ""
        
        if not isinstance(title, str):
            raise ValidationError("標題必須為字串")
        
        title = title.strip()
        limits = cls._get_limits()
        if len(title) > limits['title']:
            raise ValidationError(f"標題長度不能超過 {limits['title']} 字元")
        
        return title
    
    @classmethod
    def validate_category(cls, category: str) -> str:
        """驗證分類格式和長度"""
        if category is None:
            return ""
        
        if not isinstance(category, str):
            raise ValidationError("分類必須為字串")
        
        category = category.strip()
        limits = cls._get_limits()
        if len(category) > limits['category']:
            raise ValidationError(f"分類長度不能超過 {limits['category']} 字元")
        
        # 分類只允許特定字元
        if category and not re.match(r'^[a-zA-Z0-9_\-\u4e00-\u9fff\s]+$', category):
            raise ValidationError("分類只能包含英文字母、數字、中文、底線、連字號和空格")
        
        return category
    
    @classmethod
    def validate_query(cls, query: str) -> str:
        """驗證搜尋查詢"""
        if not isinstance(query, str):
            raise ValidationError("搜尋查詢必須為字串")
        
        query = query.strip()
        if not query:
            raise ValidationError("搜尋查詢不能為空")
        
        limits = cls._get_limits()
        if len(query) > limits['query']:
            raise ValidationError(f"搜尋查詢長度不能超過 {limits['query']} 字元")
        
        return query
    
    @classmethod
    def _contains_suspicious_patterns(cls, content: str) -> bool:
        """檢查內容是否包含可疑模式"""
        suspicious_patterns = [
            r'<script[^>]*>.*?</script>',  # JavaScript
            r'javascript:',  # JavaScript 協議
            r'vbscript:',   # VBScript 協議
            r'on\w+\s*=',   # 事件處理器
            r'eval\s*\(',   # eval 函數
            r'exec\s*\(',   # exec 函數
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, content, re.IGNORECASE | re.DOTALL):
                return True
        
        return False

# SQL 安全工具
class SQLSafetyUtils:
    """SQL 安全工具類別"""
    
    # SQL 關鍵字黑名單
    DANGEROUS_KEYWORDS = {
        'drop', 'delete', 'truncate', 'alter', 'create', 'insert', 'update',
        'exec', 'execute', 'sp_', 'xp_', 'union', 'select', 'from', 'where',
        'having', 'group', 'order', 'limit', 'offset', 'join', 'inner', 'outer',
        'left', 'right', 'full', 'cross', 'on', 'as', 'distinct', 'all', 'any',
        'exists', 'in', 'like', 'between', 'is', 'null', 'not', 'and', 'or',
        'case', 'when', 'then', 'else', 'end', 'cast', 'convert'
    }
    
    @classmethod
    def sanitize_sql_identifier(cls, identifier: str) -> str:
        """清理 SQL 識別符（表名、欄位名等）"""
        if not identifier:
            raise ValidationError("SQL 識別符不能為空")
        
        # 只允許字母、數字、底線
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', identifier):
            raise ValidationError(f"無效的 SQL 識別符: {identifier}")
        
        # 檢查長度
        if len(identifier) > 64:
            raise ValidationError("SQL 識別符長度不能超過 64 字元")
        
        # 檢查是否為 SQL 關鍵字
        if identifier.lower() in cls.DANGEROUS_KEYWORDS:
            raise ValidationError(f"'{identifier}' 是 SQL 保留字，不能作為識別符")
        
        return identifier
    
    @classmethod
    def build_safe_where_clause(cls, conditions: Dict[str, Any]) -> Tuple[str, List[Any]]:
        """安全地構建 WHERE 子句"""
        if not conditions:
            return "", []
        
        where_parts = []
        params = []
        
        for column, value in conditions.items():
            # 驗證欄位名稱
            safe_column = cls.sanitize_sql_identifier(column)
            where_parts.append(f"{safe_column} = ?")
            params.append(value)
        
        where_clause = " AND ".join(where_parts)
        return where_clause, params
    
    @classmethod
    def build_safe_update_clause(cls, updates: Dict[str, Any]) -> Tuple[str, List[Any]]:
        """安全地構建 UPDATE SET 子句"""
        if not updates:
            raise ValidationError("UPDATE 語句必須包含至少一個更新欄位")
        
        set_parts = []
        params = []
        
        for column, value in updates.items():
            # 驗證欄位名稱
            safe_column = cls.sanitize_sql_identifier(column)
            set_parts.append(f"{safe_column} = ?")
            params.append(value)
        
        set_clause = ", ".join(set_parts)
        return set_clause, params
    
    @classmethod
    def validate_sql_query(cls, query: str) -> bool:
        """驗證 SQL 查詢是否安全"""
        if not query:
            return False
        
        query_lower = query.lower().strip()
        
        # 檢查是否包含危險操作
        dangerous_patterns = [
            r';\s*(drop|delete|truncate|alter|create)\s',
            r'union\s+select',
            r'exec\s*\(',
            r'execute\s*\(',
            r'sp_\w+',
            r'xp_\w+',
            r'--',  # SQL 注釋
            r'/\*.*\*/',  # 多行注釋
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, query_lower):
                logger.warning(f"Detected dangerous SQL pattern: {pattern}")
                return False
        
        return True

# 檔案路徑安全工具
class PathSafetyUtils:
    """檔案路徑安全驗證工具"""
    
    @classmethod
    def validate_safe_path(cls, path: Path, base_path: Path, operation: str = "access") -> Path:
        """驗證路徑是否安全，防止目錄遍歷攻擊"""
        try:
            # 解析路徑為絕對路徑
            abs_path = path.resolve()
            abs_base = base_path.resolve()
            
            # 檢查路徑是否在基礎目錄內
            try:
                abs_path.relative_to(abs_base)
            except ValueError:
                raise SecurityError(
                    f"路徑 '{path}' 超出允許的基礎目錄 '{base_path}' 範圍"
                )
            
            # 檢查路徑長度
            max_path_len = config.get('paths', 'max_path_length', 4096)
            if len(str(abs_path)) > max_path_len:
                raise ValidationError(f"檔案路徑長度不能超過 {max_path_len} 字元")
            
            # 檢查危險的路徑組件（但排除根目錄的正常組件）
            dangerous_components = {'..', '~', '$'}
            for component in abs_path.parts[1:]:  # 跳過根路徑
                if component in dangerous_components:
                    raise SecurityError(f"路徑包含危險組件: '{component}'")
                
                # 檢查特殊字元
                if any(char in component for char in ['<', '>', ':', '|', '?', '*']):
                    raise SecurityError(f"路徑組件包含非法字元: '{component}'")
            
            # 檢查檔案名稱長度
            max_filename_len = config.get('paths', 'max_filename_length', 255)
            if abs_path.name and len(abs_path.name) > max_filename_len:
                raise ValidationError(f"檔案名稱長度不能超過 {max_filename_len} 字元")
            
            # 記錄安全操作
            logger.debug(f"Path validation passed for {operation}: {abs_path}")
            return abs_path
            
        except (OSError, ValueError) as e:
            raise SecurityError(f"路徑驗證失敗: {e}")
    
    @classmethod
    def validate_filename(cls, filename: str) -> str:
        """驗證檔案名稱是否安全"""
        if not filename or not isinstance(filename, str):
            raise ValidationError("檔案名稱不能為空")
        
        filename = filename.strip()
        if not filename:
            raise ValidationError("檔案名稱不能為空白")
        
        # 檢查長度
        if len(filename) > 255:
            raise ValidationError("檔案名稱過長")
        
        # 檢查非法字元
        illegal_chars = ['/', '\\', '<', '>', ':', '|', '?', '*', '"']
        for char in illegal_chars:
            if char in filename:
                raise SecurityError(f"檔案名稱包含非法字元: '{char}'")
        
        # 檢查保留名稱 (Windows)
        reserved_names = {
            'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 
            'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 
            'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        }
        if filename.upper() in reserved_names:
            raise SecurityError(f"'{filename}' 是系統保留名稱")
        
        # 檢查隱藏檔案模式
        if filename.startswith('.') and len(filename) > 1:
            logger.warning(f"Creating hidden file: {filename}")
        
        return filename
    
    @classmethod
    def sanitize_project_id_for_path(cls, project_id: str) -> str:
        """清理專案ID使其適合作為檔案路徑"""
        if not project_id:
            raise ValidationError("專案ID不能為空")
        
        # 移除或替換危險字元
        safe_chars = []
        for char in project_id:
            if char.isalnum() or char in '-_':
                safe_chars.append(char)
            elif char in ' \t':
                safe_chars.append('_')
            # 其他字元直接忽略
        
        safe_id = ''.join(safe_chars)
        if not safe_id:
            raise ValidationError("專案ID清理後為空")
        
        # 確保長度適中
        if len(safe_id) > 100:
            safe_id = safe_id[:100]
        
        return safe_id

# 配置管理系統
class ConfigManager:
    """配置管理器"""
    
    # 預設配置
    DEFAULT_CONFIG = {
        # 資料庫配置
        'database': {
            'timeout': 30.0,
            'check_same_thread': False,
            'text_factory': 'str',
            'encoding': 'UTF-8',
            'page_size': 4096,
            'cache_size': -2000,  # 2MB
        },
        
        # 檔案操作配置
        'file_operations': {
            'lock_timeout': 30.0,
            'lock_retry_delay': 0.1,
            'atomic_write': True,
            'backup_enabled': False,
        },
        
        # 搜尋配置
        'search': {
            'default_limit': 10,
            'max_limit': 100,
            'token_limit': 1500,
            'content_preview_length': 400,
        },
        
        # 驗證配置
        'validation': {
            'max_content_length': 50 * 1024 * 1024,  # 50MB
            'max_title_length': 500,
            'max_category_length': 100,
            'max_query_length': 1000,
            'max_project_id_length': 100,
        },
        
        # 路徑配置
        'paths': {
            'max_path_length': 4096,
            'max_filename_length': 255,
            'memory_dir': 'ai-memory',
        },
        
        # 日誌配置
        'logging': {
            'level': 'INFO',
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'max_file_size': 10 * 1024 * 1024,  # 10MB
            'backup_count': 5,
        },
        
        # 效能配置
        'performance': {
            'connection_pool_size': 5,
            'query_cache_size': 100,
            'enable_profiling': False,
        }
    }
    
    def __init__(self, config_file: str = None, config_dict: dict = None):
        """初始化配置管理器"""
        self.config = self.DEFAULT_CONFIG.copy()
        self.config_file = config_file
        
        if config_dict:
            self._merge_config(config_dict)
        elif config_file and Path(config_file).exists():
            self._load_from_file(config_file)
        
        # 載入環境變數覆寫
        self._load_from_env()
    
    def _merge_config(self, config_dict: dict):
        """合併配置字典"""
        def deep_merge(base, override):
            for key, value in override.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    deep_merge(base[key], value)
                else:
                    base[key] = value
        
        deep_merge(self.config, config_dict)
    
    def _load_from_file(self, config_file: str):
        """從檔案載入配置"""
        try:
            import json
            with open(config_file, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
            self._merge_config(file_config)
            logger.info(f"Configuration loaded from {config_file}")
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load config from {config_file}: {e}")
            raise ConfigurationError(f"配置檔案載入失敗: {e}")
    
    def _load_from_env(self):
        """從環境變數載入配置"""
        env_mappings = {
            'MEMORY_DB_TIMEOUT': ('database', 'timeout', float),
            'MEMORY_LOCK_TIMEOUT': ('file_operations', 'lock_timeout', float),
            'MEMORY_SEARCH_LIMIT': ('search', 'default_limit', int),
            'MEMORY_MAX_CONTENT_SIZE': ('validation', 'max_content_length', int),
            'MEMORY_LOG_LEVEL': ('logging', 'level', str),
            'MEMORY_DIR': ('paths', 'memory_dir', str),
        }
        
        for env_key, (section, key, type_func) in env_mappings.items():
            env_value = os.getenv(env_key)
            if env_value is not None:
                try:
                    self.config[section][key] = type_func(env_value)
                    logger.debug(f"Config override from env: {env_key}={env_value}")
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid env config {env_key}={env_value}: {e}")
    
    def get(self, section: str, key: str = None, default=None):
        """取得配置值"""
        try:
            if key is None:
                return self.config.get(section, default)
            return self.config.get(section, {}).get(key, default)
        except (KeyError, TypeError):
            return default
    
    def set(self, section: str, key: str, value):
        """設定配置值"""
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = value
    
    def save_to_file(self, filename: str):
        """儲存配置到檔案"""
        try:
            import json
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            logger.info(f"Configuration saved to {filename}")
        except IOError as e:
            logger.error(f"Failed to save config to {filename}: {e}")
            raise ConfigurationError(f"配置檔案儲存失敗: {e}")
    
    def validate(self):
        """驗證配置有效性"""
        required_sections = ['database', 'file_operations', 'search', 'validation']
        for section in required_sections:
            if section not in self.config:
                raise ConfigurationError(f"缺少必要配置區塊: {section}")
        
        # 驗證數值範圍
        if self.get('database', 'timeout', 0) <= 0:
            raise ConfigurationError("資料庫超時時間必須大於0")
        
        if self.get('search', 'max_limit', 0) <= 0:
            raise ConfigurationError("搜尋結果上限必須大於0")
        
        logger.info("Configuration validation passed")

# 全域配置實例
config = ConfigManager()

# 重新配置日誌記錄器使用配置管理器
logger = StructuredLogger(__name__, config)

# 效能測量裝飾器
def log_performance(operation_name: str = None):
    """效能測量裝飾器"""
    def decorator(func):
        import functools
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation_name or f"{func.__name__}"
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # 記錄成功的操作
                context = {
                    'function': func.__name__,
                    'args_count': len(args),
                    'kwargs_count': len(kwargs)
                }
                logger.performance(op_name, duration, context, status='success')
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                # 記錄失敗的操作
                context = {
                    'function': func.__name__,
                    'args_count': len(args),
                    'kwargs_count': len(kwargs),
                    'error_type': type(e).__name__,
                    'error_message': str(e)
                }
                logger.performance(op_name, duration, context, status='error')
                
                raise
        
        return wrapper
    return decorator

class FileLock:
    """跨平台檔案鎖定工具類"""
    
    def __init__(self, file_path: Path, timeout: float = None, retry_delay: float = None):
        self.file_path = file_path
        self.timeout = timeout or config.get('file_operations', 'lock_timeout', 30.0)
        self.retry_delay = retry_delay or config.get('file_operations', 'lock_retry_delay', 0.1)
        self.lock_file = None
        self.locked = False
    
    def __enter__(self):
        self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
    
    def acquire(self):
        """取得檔案鎖定"""
        if self.locked:
            return
        
        # 創建鎖定檔案路徑
        lock_file_path = self.file_path.with_suffix(self.file_path.suffix + '.lock')
        
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            try:
                # 嘗試創建鎖定檔案
                self.lock_file = open(lock_file_path, 'w')
                
                if HAS_FCNTL:
                    # Unix/Linux/macOS 使用 fcntl
                    fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                elif HAS_MSVCRT:
                    # Windows 使用 msvcrt
                    msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    # 降級方案：使用檔案存在性檢查
                    if lock_file_path.exists():
                        raise OSError("Lock file exists")
                
                # 寫入鎖定資訊
                self.lock_file.write(f"Locked by PID {os.getpid()} at {time.time()}\n")
                self.lock_file.flush()
                
                self.locked = True
                logger.debug(f"Acquired lock for {self.file_path}")
                return
                
            except (OSError, IOError) as e:
                # 鎖定失敗，清理並重試
                if self.lock_file:
                    try:
                        self.lock_file.close()
                    except:
                        pass
                    self.lock_file = None
                
                logger.debug(f"Lock acquisition failed for {self.file_path}: {e}")
                time.sleep(self.retry_delay)
                continue
        
        # 超時失敗
        raise TimeoutError(f"Failed to acquire lock for {self.file_path} within {self.timeout} seconds")
    
    def release(self):
        """釋放檔案鎖定"""
        if not self.locked or not self.lock_file:
            return
        
        try:
            if HAS_FCNTL:
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
            elif HAS_MSVCRT:
                msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            
            self.lock_file.close()
            
            # 刪除鎖定檔案
            lock_file_path = self.file_path.with_suffix(self.file_path.suffix + '.lock')
            try:
                lock_file_path.unlink()
            except FileNotFoundError:
                pass
            
            logger.debug(f"Released lock for {self.file_path}")
            
        except (OSError, IOError) as e:
            logger.warning(f"I/O error releasing lock for {self.file_path}: {e}")
        except PermissionError as e:
            logger.warning(f"Permission denied releasing lock for {self.file_path}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error releasing lock for {self.file_path}: {e}")
        finally:
            self.lock_file = None
            self.locked = False

class AtomicFileWriter:
    """原子檔案寫入工具類"""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.temp_path = file_path.with_suffix(file_path.suffix + '.tmp')
        self.temp_file = None
    
    def __enter__(self):
        # 確保目錄存在
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 開啟臨時檔案
        self.temp_file = open(self.temp_path, 'w', encoding='utf-8')
        return self.temp_file
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.temp_file:
            self.temp_file.close()
        
        if exc_type is None:
            # 成功：原子性重命名
            try:
                self.temp_path.replace(self.file_path)
                logger.debug(f"Atomic write completed for {self.file_path}")
            except (OSError, IOError) as e:
                logger.error(f"I/O error during atomic write for {self.file_path}: {e}")
                self._cleanup_temp_file()
                raise FileOperationError(f"原子性寫入失敗: {e}")
            except PermissionError as e:
                logger.error(f"Permission denied during atomic write for {self.file_path}: {e}")
                self._cleanup_temp_file()
                raise FileOperationError(f"檔案權限錯誤: {e}")
            except Exception as e:
                logger.error(f"Unexpected error during atomic write for {self.file_path}: {e}")
                self._cleanup_temp_file()
                raise
        else:
            # 失敗：清理臨時檔案
            self._cleanup_temp_file()
    
    def _cleanup_temp_file(self):
        """清理臨時檔案"""
        try:
            self.temp_path.unlink()
        except FileNotFoundError:
            pass
        except (OSError, IOError) as e:
            logger.warning(f"Failed to cleanup temp file {self.temp_path}: {e}")


class MemoryBackend(ABC):
    """
    記憶後端抽象基類
    Abstract base class for memory backends
    
    定義所有記憶後端必須實作的介面方法
    Defines interface methods that all memory backends must implement
    """
    
    @abstractmethod
    def save_memory(self, project_id: str, content: str, title: str = "", category: str = "") -> bool:
        """儲存記憶到後端"""
        pass
    
    @abstractmethod
    def get_memory(self, project_id: str) -> Optional[str]:
        """讀取完整專案記憶"""
        pass
    
    @abstractmethod
    def search_memory(self, project_id: str, query: str, limit: int = 10) -> List[Dict[str, str]]:
        """搜尋記憶內容"""
        pass
    
    def rag_query(self, project_id: str, question: str, context_limit: int = 5, max_tokens: int = 2000) -> Dict[str, Any]:
        """
        RAG 查詢：基於專案記憶回答問題
        檢索相關內容並構建用於回答的上下文
        """
        # 1. 檢索相關內容
        relevant_docs = self.search_memory(project_id, question, context_limit * 2)
        
        if not relevant_docs:
            return {
                'status': 'no_context',
                'answer': f'沒有找到與「{question}」相關的專案記憶內容。',
                'context_sources': [],
                'suggestions': [
                    f"使用 save_project_memory 記錄與「{question}」相關的資訊",
                    f"嘗試使用不同的關鍵字搜尋",
                    f"檢查專案ID「{project_id}」是否正確"
                ]
            }
        
        # 2. 選擇最相關的內容並控制 token 數量
        selected_docs = []
        total_tokens = 0
        
        for doc in relevant_docs[:context_limit]:
            content = doc.get('entry', doc.get('content', ''))
            content_tokens = len(content) // 4  # 粗略估計 token 數
            
            if total_tokens + content_tokens <= max_tokens:
                selected_docs.append({
                    'title': doc.get('title', '無標題'),
                    'category': doc.get('category', ''),
                    'timestamp': doc.get('timestamp', doc.get('created_at', '')),
                    'content': content,
                    'relevance': doc.get('similarity', doc.get('relevance', 0))
                })
                total_tokens += content_tokens
            else:
                break
        
        # 3. 構建結構化上下文
        context_parts = []
        for i, doc in enumerate(selected_docs, 1):
            context_part = f"【記憶 {i}】"
            if doc['title']:
                context_part += f" {doc['title']}"
            if doc['category']:
                context_part += f" #{doc['category']}"
            if doc['timestamp']:
                context_part += f" ({doc['timestamp'][:16]})"
            context_part += f"\n{doc['content']}\n"
            context_parts.append(context_part)
        
        context_text = "\n---\n\n".join(context_parts)
        
        # 4. 構建 RAG 提示詞
        rag_prompt = f"""基於以下專案記憶內容回答問題：

專案：{project_id}
問題：{question}

相關記憶內容：
{context_text}

---

請基於上述記憶內容提供準確的回答：
1. 如果記憶中有直接相關的資訊，請詳細回答
2. 如果只有部分相關資訊，請說明已知的部分並指出缺少什麼
3. 如果記憶內容不足以回答問題，請明確說明並建議下一步行動

請用專業但易懂的方式回答。"""

        return {
            'status': 'success',
            'prompt': rag_prompt,
            'context_sources': [
                {
                    'title': doc['title'],
                    'category': doc['category'],
                    'timestamp': doc['timestamp'],
                    'relevance': doc.get('relevance', 0),
                    'content_preview': doc['content'][:200] + ('...' if len(doc['content']) > 200 else '')
                }
                for doc in selected_docs
            ],
            'context_count': len(selected_docs),
            'estimated_tokens': total_tokens,
            'question': question
        }
    
    def _analyze_query_type(self, query: str) -> str:
        """
        智能查詢類型分析
        分析查詢意圖，決定使用哪種搜尋策略
        """
        query_lower = query.lower()
        
        # 簡單查找關鍵詞：只需要標題或摘要
        simple_keywords = [
            '列表', 'list', '有哪些', '找到', 'find', '搜尋', 'search',
            '顯示', 'show', '查看', 'view', '所有', 'all', '最新', 'recent'
        ]
        
        # 複雜問題關鍵詞：需要完整內容分析  
        complex_keywords = [
            '為什麼', 'why', '如何', 'how', '解釋', 'explain', '分析', 'analyze',
            '比較', 'compare', '差異', 'difference', '原因', 'reason', '方法', 'method',
            '建議', 'suggest', '推薦', 'recommend', '優缺點', 'pros and cons'
        ]
        
        # 檢查簡單查找模式
        if any(keyword in query_lower for keyword in simple_keywords):
            return 'simple_lookup'
        
        # 檢查複雜問題模式
        if any(keyword in query_lower for keyword in complex_keywords):
            return 'complex_question'
        
        # 根據長度判斷
        if len(query) > 50:
            return 'complex_question'
        elif len(query.split()) > 8:
            return 'complex_question'
        
        return 'simple_lookup'
    
    def smart_search(self, project_id: str, query: str, limit: int = 10) -> Dict[str, Any]:
        """
        智能搜索路由：根據查詢類型自動選擇最佳策略
        這個方法對用戶透明，自動優化 token 使用
        """
        query_type = self._analyze_query_type(query)
        
        logger.info(f"智能路由: 查詢類型={query_type}, 查詢='{query[:30]}...'")
        
        if query_type == 'simple_lookup':
            # 簡單查找：返回標題和摘要，大幅節省 token
            search_results = self.search_memory(project_id, query, limit)
            
            # 只返回關鍵資訊，節省 token
            simplified_results = []
            for result in search_results:
                content = result.get('entry', result.get('content', ''))
                # 只保留前 150 字符作為摘要
                summary = content[:150] + ('...' if len(content) > 150 else '')
                
                simplified_results.append({
                    'title': result.get('title', '無標題'),
                    'category': result.get('category', ''),
                    'timestamp': result.get('timestamp', result.get('created_at', '')),
                    'summary': summary,
                    'full_content_available': len(content) > 150
                })
            
            return {
                'strategy': 'simple_lookup',
                'token_saved': True,
                'results': simplified_results,
                'result_count': len(simplified_results),
                'message': f"找到 {len(simplified_results)} 條相關記憶（摘要模式，已節省 ~70% token）"
            }
            
        elif query_type == 'complex_question':
            # 複雜問題：使用 RAG 策略
            rag_result = self.rag_query(project_id, query, limit, max_tokens=1500)
            
            if rag_result['status'] == 'success':
                return {
                    'strategy': 'complex_question',
                    'token_optimized': True,
                    'results': rag_result['context_sources'],
                    'result_count': rag_result['context_count'],
                    'rag_prompt': rag_result['prompt'],
                    'message': f"已準備回答複雜問題（RAG模式，使用 {rag_result['estimated_tokens']} tokens）"
                }
            else:
                return {
                    'strategy': 'complex_question',
                    'results': [],
                    'result_count': 0,
                    'message': rag_result.get('answer', '無法處理此複雜問題')
                }
        
        else:
            # 預設：混合策略
            return {
                'strategy': 'hybrid',
                'results': self.search_memory(project_id, query, limit),
                'message': f"使用混合搜尋策略"
            }
    
    def summarize_project(self, project_id: str, summary_type: str = 'brief', max_entries: int = 20) -> Dict[str, Any]:
        """
        生成專案內容摘要
        根據不同類型提供專案概況
        """
        try:
            # 獲取專案統計資訊
            stats = self.get_memory_stats(project_id) if hasattr(self, 'get_memory_stats') else {'exists': False}
            
            if not stats.get('exists', False):
                return {
                    'status': 'not_found',
                    'message': f'專案 "{project_id}" 不存在或沒有內容',
                    'suggestions': [
                        f"使用 save_project_memory 開始記錄專案內容",
                        f"檢查專案ID拼寫是否正確",
                        f"使用 list_memory_projects 查看所有可用專案"
                    ]
                }
            
            # 獲取記憶內容進行分析
            recent_entries = self.get_recent_memory(project_id, max_entries) if hasattr(self, 'get_recent_memory') else []
            
            if summary_type == 'brief':
                return self._generate_brief_summary(project_id, stats, recent_entries[:5])
            elif summary_type == 'detailed':
                return self._generate_detailed_summary(project_id, stats, recent_entries[:15])
            elif summary_type == 'timeline':
                return self._generate_timeline_summary(project_id, stats, recent_entries)
            else:
                return self._generate_brief_summary(project_id, stats, recent_entries[:5])
                
        except Exception as e:
            logger.error(f"Error generating project summary: {e}")
            return {
                'status': 'error',
                'message': f'生成專案摘要時發生錯誤: {str(e)}'
            }
    
    def _generate_brief_summary(self, project_id: str, stats: Dict, entries: List[Dict]) -> Dict[str, Any]:
        """生成簡要摘要 (200-300 tokens)"""
        
        # 分析分類和主題
        categories = stats.get('categories', [])
        entry_count = stats.get('total_entries', 0)
        
        # 提取關鍵主題
        key_topics = []
        recent_activities = []
        
        for entry in entries[:3]:
            if entry.get('title'):
                key_topics.append(entry['title'])
            if entry.get('timestamp'):
                recent_activities.append(entry['timestamp'][:10])  # 日期部分
        
        summary = f"**{project_id}** 是一個包含 {entry_count} 條記憶的專案。"
        
        if categories:
            summary += f"\n\n**主要分類**: {', '.join(categories[:5])}"
        
        if key_topics:
            summary += f"\n**近期主題**: {', '.join(key_topics)}"
        
        if recent_activities:
            summary += f"\n**活動時間**: 最近更新於 {max(recent_activities)}"
        
        return {
            'status': 'success',
            'type': 'brief',
            'summary': summary,
            'key_metrics': {
                'total_entries': entry_count,
                'categories': len(categories),
                'recent_activity': max(recent_activities) if recent_activities else 'Unknown'
            }
        }
    
    def _generate_detailed_summary(self, project_id: str, stats: Dict, entries: List[Dict]) -> Dict[str, Any]:
        """生成詳細摘要 (800-1000 tokens)"""
        
        categories = stats.get('categories', [])
        entry_count = stats.get('total_entries', 0)
        total_words = stats.get('total_words', 0)
        
        # 分析內容結構
        category_analysis = {}
        timeline_analysis = {}
        key_topics = []
        
        for entry in entries:
            # 分類分析
            cat = entry.get('category', '未分類')
            if cat not in category_analysis:
                category_analysis[cat] = 0
            category_analysis[cat] += 1
            
            # 時間軸分析
            if entry.get('timestamp'):
                date = entry['timestamp'][:7]  # YYYY-MM
                if date not in timeline_analysis:
                    timeline_analysis[date] = 0
                timeline_analysis[date] += 1
            
            # 關鍵主題
            if entry.get('title'):
                key_topics.append(entry['title'])
        
        summary = f"## {project_id} 專案詳細分析\n\n"
        summary += f"這是一個活躍的專案，包含 {entry_count} 條記憶，總計約 {total_words} 個詞彙。\n\n"
        
        # 內容結構分析
        summary += "### 📊 內容結構\n"
        if category_analysis:
            summary += "**分類分佈**:\n"
            for cat, count in sorted(category_analysis.items(), key=lambda x: x[1], reverse=True)[:5]:
                percentage = (count / len(entries)) * 100
                summary += f"- {cat}: {count} 條 ({percentage:.1f}%)\n"
        
        # 活動時間軸
        if timeline_analysis:
            summary += "\n### 📅 活動時間軸\n"
            summary += "**月份活動**:\n"
            for month, count in sorted(timeline_analysis.items(), reverse=True)[:6]:
                summary += f"- {month}: {count} 條記憶\n"
        
        # 主要主題
        if key_topics:
            summary += f"\n### 🎯 主要主題\n"
            summary += f"最近關注的主題包括: {', '.join(key_topics[:8])}\n"
        
        return {
            'status': 'success',
            'type': 'detailed',
            'summary': summary,
            'analysis': {
                'category_distribution': category_analysis,
                'timeline': timeline_analysis,
                'key_topics': key_topics[:10]
            }
        }
    
    def _generate_timeline_summary(self, project_id: str, stats: Dict, entries: List[Dict]) -> Dict[str, Any]:
        """生成時間軸摘要 (500-700 tokens)"""
        
        # 按時間排序
        sorted_entries = sorted(entries, key=lambda x: x.get('timestamp', ''), reverse=True)
        
        summary = f"## {project_id} 專案發展時間軸\n\n"
        
        # 按月份分組
        monthly_groups = {}
        for entry in sorted_entries[:15]:
            if entry.get('timestamp'):
                month = entry['timestamp'][:7]  # YYYY-MM
                if month not in monthly_groups:
                    monthly_groups[month] = []
                monthly_groups[month].append(entry)
        
        # 生成時間軸
        for month in sorted(monthly_groups.keys(), reverse=True)[:6]:
            entries_in_month = monthly_groups[month]
            summary += f"### 📅 {month}\n"
            
            for entry in entries_in_month[:3]:  # 每月最多3條
                title = entry.get('title', '無標題')
                category = entry.get('category', '')
                day = entry.get('timestamp', '')[:10] if entry.get('timestamp') else ''
                
                summary += f"- **{day}** - {title}"
                if category:
                    summary += f" #{category}"
                summary += "\n"
            
            if len(entries_in_month) > 3:
                summary += f"  ... 還有 {len(entries_in_month) - 3} 條記憶\n"
            summary += "\n"
        
        return {
            'status': 'success',
            'type': 'timeline',
            'summary': summary,
            'timeline_data': monthly_groups
        }
    
    @abstractmethod
    def list_projects(self) -> List[Dict[str, Any]]:
        """列出所有專案及其統計資訊"""
        pass
    
    @abstractmethod
    def get_recent_memory(self, project_id: str, limit: int = 5) -> List[Dict[str, str]]:
        """取得最近的記憶條目"""
        pass
    
    @abstractmethod
    def delete_memory(self, project_id: str) -> bool:
        """刪除專案記憶檔案"""
        pass
    
    @abstractmethod
    def delete_memory_entry(self, project_id: str, entry_id: str = None, timestamp: str = None, 
                           title: str = None, category: str = None, content_match: str = None) -> Dict[str, Any]:
        """刪除特定的記憶條目"""
        pass
    
    @abstractmethod
    def edit_memory_entry(self, project_id: str, entry_id: str = None, timestamp: str = None,
                         new_title: str = None, new_category: str = None, new_content: str = None) -> Dict[str, Any]:
        """編輯特定的記憶條目"""
        pass
    
    @abstractmethod
    def list_memory_entries(self, project_id: str) -> Dict[str, Any]:
        """列出專案中的所有記憶條目，帶有索引"""
        pass
    
    @abstractmethod
    def get_memory_stats(self, project_id: str) -> Dict[str, Any]:
        """取得記憶統計資訊"""
        pass

    @abstractmethod
    def rename_project(self, old_project_id: str, new_project_id: str) -> bool:
        """重新命名專案"""
        raise NotImplementedError("Subclasses must implement rename_project method")



class MarkdownMemoryManager(MemoryBackend):
    """
    Markdown 記憶管理器
    Markdown Memory Manager
    
    使用 Markdown 檔案格式儲存和管理 AI 記憶，支援檔案鎖定和原子寫入
    Stores and manages AI memory using Markdown file format with file locking and atomic writes
    """
    
    def __init__(self, memory_dir: str = "ai-memory"):
        # 總是使用腳本所在目錄作為基準，確保路徑穩定性
        script_dir = Path(__file__).parent.resolve()  # 使用 resolve() 獲取絕對路徑
        
        if Path(memory_dir).is_absolute():
            # 如果提供絕對路徑，直接使用
            self.memory_dir = Path(memory_dir)
        else:
            # 相對路徑總是相對於腳本目錄
            self.memory_dir = script_dir / memory_dir
        
        # 確保使用絕對路徑
        self.memory_dir = self.memory_dir.resolve()
        
        # 記錄路徑信息用於調試
        logger.info(f"Script directory: {script_dir}")
        logger.info(f"Target memory directory: {self.memory_dir}")
        
        # 確保目錄存在
        try:
            self.memory_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Memory directory successfully initialized: {self.memory_dir}")
            
            # 驗證目錄是否可寫
            test_file = self.memory_dir / ".write_test"
            try:
                test_file.write_text("test")
                test_file.unlink()  # 刪除測試文件
                logger.info("Memory directory write test passed")
            except Exception as write_error:
                logger.error(f"Memory directory is not writable: {write_error}")
                raise OSError(f"Memory directory not writable: {self.memory_dir}")
                
        except OSError as e:
            logger.error(f"Failed to create memory directory at {self.memory_dir}: {e}")
            # 如果無法創建，嘗試在用戶主目錄創建
            import tempfile
            fallback_dir = Path.home() / ".ai-memory"
            try:
                fallback_dir.mkdir(parents=True, exist_ok=True)
                self.memory_dir = fallback_dir
                logger.warning(f"Using fallback directory in user home: {self.memory_dir}")
            except OSError:
                # 最後的備選方案：使用臨時目錄
                self.memory_dir = Path(tempfile.mkdtemp(prefix="ai-memory-"))
                logger.warning(f"Using temporary directory: {self.memory_dir}")

    def get_memory_file(self, project_id: str) -> Path:
        """取得專案記憶檔案路徑"""
        try:
            # 使用安全的專案ID清理
            clean_id = PathSafetyUtils.sanitize_project_id_for_path(project_id)
            
            # 驗證檔案名稱安全性
            filename = PathSafetyUtils.validate_filename(f"{clean_id}.md")
            
            # 建立完整路徑
            file_path = self.memory_dir / filename
            
            # 驗證路徑安全性
            safe_path = PathSafetyUtils.validate_safe_path(
                file_path, 
                self.memory_dir, 
                f"memory file access for project '{project_id}'"
            )
            
            return safe_path
            
        except (ValidationError, SecurityError) as e:
            logger.error(f"Path validation failed for project '{project_id}': {e}")
            raise

    def get_memory(self, project_id: str) -> Optional[str]:
        """讀取完整專案記憶"""
        logger.info(f"[MARKDOWN] Calling get_memory for project: {project_id}")
        try:
            memory_file = self.get_memory_file(project_id)
            if memory_file.exists():
                return memory_file.read_text(encoding='utf-8')
            return None
        except Exception as e:
            logger.error(f"Error reading memory for {project_id}: {e}")
            return None

    def save_memory(self, project_id: str, content: str, title: str = "", category: str = "") -> bool:
        """儲存記憶到 markdown 檔案（使用檔案鎖定）"""
        logger.info(f"[MARKDOWN] Calling save_memory for project: {project_id}")
        try:
            memory_file = self.get_memory_file(project_id)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 建立記憶條目
            entry_parts = [f"\n## {timestamp}"]
            if title:
                entry_parts.append(f" - {title}")
            if category:
                entry_parts.append(f" #{category}")
            
            entry = "".join(entry_parts) + f"\n\n{content}\n\n---\n"
            
            # 使用檔案鎖定進行安全寫入
            with FileLock(memory_file):
                if memory_file.exists():
                    # 追加到現有檔案
                    with open(memory_file, 'a', encoding='utf-8') as f:
                        f.write(entry)
                else:
                    # 創建新檔案（使用原子寫入）
                    header = f"# AI Memory for {project_id}\n\n"
                    header += f"Created: {timestamp}\n\n"
                    with AtomicFileWriter(memory_file) as f:
                        f.write(header + entry)
            
            logger.info(f"Memory saved for project: {project_id}")
            return True
            
        except TimeoutError as e:
            logger.error(f"Timeout acquiring lock for {project_id}: {e}")
            return False
        except (ValidationError, SecurityError) as e:
            logger.error(f"Validation error saving memory for {project_id}: {e}")
            return False
        except (OSError, IOError) as e:
            logger.error(f"I/O error saving memory for {project_id}: {e}")
            raise FileOperationError(f"檔案操作錯誤: {e}")
        except PermissionError as e:
            logger.error(f"Permission denied saving memory for {project_id}: {e}")
            raise FileOperationError(f"檔案權限錯誤: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving memory for {project_id}: {e}")
            return False

    def search_memory(self, project_id: str, query: str, limit: int = 10) -> List[Dict[str, str]]:
        """搜尋記憶內容"""
        logger.info(f"[MARKDOWN] Calling search_memory for project: {project_id}, query: {query}")
        try:
            memory = self.get_memory(project_id)
            if not memory:
                return []

            results = []
            sections = self._parse_memory_sections(memory)
            
            for section in sections:
                if query.lower() in section['content'].lower():
                    results.append({
                        'timestamp': section['timestamp'],
                        'title': section['title'],
                        'category': section['category'],
                        'content': section['content'][:500] + "..." if len(section['content']) > 500 else section['content'],
                        'relevance': section['content'].lower().count(query.lower())
                    })
            
            # 按相關性排序
            results.sort(key=lambda x: x['relevance'], reverse=True)
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Error searching memory for {project_id}: {e}")
            return []

    def _parse_memory_sections(self, memory: str) -> List[Dict[str, str]]:
        """解析記憶檔案的各個區段"""
        sections = []
        lines = memory.split('\n')
        current_section = None
        current_content = []

        for line in lines:
            if line.startswith('## '):
                # 儲存上一個區段
                if current_section:
                    sections.append({
                        'timestamp': current_section['timestamp'],
                        'title': current_section['title'],
                        'category': current_section['category'],
                        'content': '\n'.join(current_content).strip()
                    })
                
                # 解析新區段標題
                header = line[3:].strip()
                timestamp, title, category = self._parse_section_header(header)
                current_section = {
                    'timestamp': timestamp,
                    'title': title,
                    'category': category
                }
                current_content = []
                
            elif line.strip() == '---':
                # 區段結束
                continue
            else:
                current_content.append(line)

        # 處理最後一個區段
        if current_section:
            sections.append({
                'timestamp': current_section['timestamp'],
                'title': current_section['title'],
                'category': current_section['category'],
                'content': '\n'.join(current_content).strip()
            })

        return sections

    def _parse_section_header(self, header: str) -> Tuple[str, str, str]:
        """解析區段標題，提取時間戳、標題和分類"""
        timestamp = ""
        title = ""
        category = ""
        
        # 提取分類 (hashtag)
        if '#' in header:
            header, category = header.split('#', 1)
            category = category.strip()
        
        # 提取時間戳和標題
        if ' - ' in header:
            timestamp, title = header.split(' - ', 1)
            timestamp = timestamp.strip()
            title = title.strip()
        else:
            timestamp = header.strip()
        
        return timestamp, title, category

    def list_projects(self) -> List[Dict[str, Any]]:
        """列出所有專案及其統計資訊（排除全局記憶）"""
        logger.info(f"[MARKDOWN] Calling list_projects")
        projects = []
        for file in self.memory_dir.glob("*.md"):
            # 過濾掉全局記憶檔案
            if file.stem == "__global__":
                continue
                
            try:
                content = file.read_text(encoding='utf-8')
                sections = self._parse_memory_sections(content)
                projects.append({
                    'id': file.stem,
                    'name': file.stem.replace('-', ' ').title(),
                    'file_path': str(file),
                    'entries_count': len(sections),
                    'last_modified': datetime.fromtimestamp(file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    'categories': list(set(s['category'] for s in sections if s['category']))
                })
            except Exception as e:
                logger.error(f"Error reading project {file.stem}: {e}")
                continue
        
        return sorted(projects, key=lambda x: x['last_modified'], reverse=True)

    def get_recent_memory(self, project_id: str, limit: int = 5) -> List[Dict[str, str]]:
        """取得最近的記憶條目"""
        try:
            memory = self.get_memory(project_id)
            if not memory:
                return []

            sections = self._parse_memory_sections(memory)
            
            # 返回最近的條目
            return sections[-limit:] if len(sections) > limit else sections
            
        except Exception as e:
            logger.error(f"Error getting recent memory for {project_id}: {e}")
            return []

    def delete_memory(self, project_id: str) -> bool:
        """刪除專案記憶檔案（使用檔案鎖定）"""
        logger.info(f"[MARKDOWN] Calling delete_memory for project: {project_id}")
        try:
            memory_file = self.get_memory_file(project_id)
            
            # 使用檔案鎖定進行安全刪除
            with FileLock(memory_file):
                if memory_file.exists():
                    memory_file.unlink()
                    logger.info(f"Memory deleted for project: {project_id}")
                    return True
                return False
                
        except TimeoutError as e:
            logger.error(f"Timeout acquiring lock for deleting {project_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error deleting memory for {project_id}: {e}")
            return False

    def delete_memory_entry(self, project_id: str, entry_id: str = None, timestamp: str = None, 
                           title: str = None, category: str = None, content_match: str = None) -> Dict[str, Any]:
        """刪除特定的記憶條目"""
        logger.info(f"[MARKDOWN] Calling delete_memory_entry for project: {project_id}")
        try:
            memory = self.get_memory(project_id)
            if not memory:
                return {'success': False, 'message': f'No memory found for project: {project_id}'}

            sections = self._parse_memory_sections(memory)
            original_count = len(sections)
            
            # 根據不同條件篩選要刪除的條目
            sections_to_keep = []
            deleted_entries = []
            
            for i, section in enumerate(sections):
                should_delete = False
                
                # 根據索引刪除 (entry_id 是從1開始的索引)
                if entry_id is not None:
                    try:
                        entry_index = int(entry_id) - 1  # 轉換為0基索引
                        if i == entry_index:
                            should_delete = True
                    except ValueError:
                        pass
                
                # 根據時間戳刪除
                elif timestamp and timestamp in section['timestamp']:
                    should_delete = True
                
                # 根據標題刪除
                elif title and title.lower() in section['title'].lower():
                    should_delete = True
                
                # 根據分類刪除
                elif category and category.lower() in section['category'].lower():
                    should_delete = True
                
                # 根據內容匹配刪除
                elif content_match and content_match.lower() in section['content'].lower():
                    should_delete = True
                
                if should_delete:
                    deleted_entries.append(section)
                else:
                    sections_to_keep.append(section)
            
            if len(deleted_entries) == 0:
                return {'success': False, 'message': 'No matching entries found to delete'}
            
            # 重建記憶檔案
            success = self._rebuild_memory_file(project_id, sections_to_keep)
            
            if success:
                message = f"Deleted {len(deleted_entries)} entries from project {project_id}"
                return {
                    'success': True, 
                    'message': message,
                    'deleted_count': len(deleted_entries),
                    'remaining_count': len(sections_to_keep),
                    'deleted_entries': [{'timestamp': e['timestamp'], 'title': e['title']} for e in deleted_entries]
                }
            else:
                return {'success': False, 'message': 'Failed to update memory file'}
                
        except Exception as e:
            logger.error(f"Error deleting memory entry for {project_id}: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}

    def edit_memory_entry(self, project_id: str, entry_id: str = None, timestamp: str = None,
                         new_title: str = None, new_category: str = None, new_content: str = None) -> Dict[str, Any]:
        """編輯特定的記憶條目"""
        logger.info(f"[MARKDOWN] Calling edit_memory_entry for project: {project_id}")
        try:
            memory = self.get_memory(project_id)
            if not memory:
                return {'success': False, 'message': f'No memory found for project: {project_id}'}

            sections = self._parse_memory_sections(memory)
            
            # 找到要編輯的條目
            target_section = None
            target_index = -1
            
            for i, section in enumerate(sections):
                # 根據索引查找
                if entry_id is not None:
                    try:
                        entry_index = int(entry_id) - 1
                        if i == entry_index:
                            target_section = section
                            target_index = i
                            break
                    except ValueError:
                        pass
                
                # 根據時間戳查找
                elif timestamp and timestamp in section['timestamp']:
                    target_section = section
                    target_index = i
                    break
            
            if target_section is None:
                return {'success': False, 'message': 'No matching entry found to edit'}
            
            # 更新條目內容
            if new_title is not None:
                sections[target_index]['title'] = new_title
            if new_category is not None:
                sections[target_index]['category'] = new_category
            if new_content is not None:
                sections[target_index]['content'] = new_content
            
            # 重建記憶檔案
            success = self._rebuild_memory_file(project_id, sections)
            
            if success:
                return {
                    'success': True,
                    'message': f"Successfully edited entry in project {project_id}",
                    'edited_entry': {
                        'timestamp': sections[target_index]['timestamp'],
                        'title': sections[target_index]['title'],
                        'category': sections[target_index]['category']
                    }
                }
            else:
                return {'success': False, 'message': 'Failed to update memory file'}
                
        except Exception as e:
            logger.error(f"Error editing memory entry for {project_id}: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}

    def list_memory_entries(self, project_id: str) -> Dict[str, Any]:
        """列出專案中的所有記憶條目，帶有索引"""
        logger.info(f"[MARKDOWN] Calling list_memory_entries for project: {project_id}")
        try:
            memory = self.get_memory(project_id)
            if not memory:
                return {'success': False, 'message': f'No memory found for project: {project_id}'}

            sections = self._parse_memory_sections(memory)
            
            entries = []
            for i, section in enumerate(sections):
                entries.append({
                    'id': i + 1,  # 1-based index for user convenience
                    'timestamp': section['timestamp'],
                    'title': section['title'],
                    'category': section['category'],
                    'content_preview': section['content'][:100] + "..." if len(section['content']) > 100 else section['content']
                })
            
            return {
                'success': True,
                'total_entries': len(entries),
                'entries': entries
            }
            
        except Exception as e:
            logger.error(f"Error listing memory entries for {project_id}: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}

    def _rebuild_memory_file(self, project_id: str, sections: List[Dict[str, str]]) -> bool:
        """重建記憶檔案（使用檔案鎖定）"""
        try:
            memory_file = self.get_memory_file(project_id)
            
            # 使用檔案鎖定進行安全重建
            with FileLock(memory_file):
                if not sections:
                    # 如果沒有條目，刪除檔案
                    if memory_file.exists():
                        memory_file.unlink()
                    return True
                
                # 重建檔案內容
                content_parts = [f"# AI Memory for {project_id}\n\n"]
                content_parts.append(f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                for section in sections:
                    # 重建條目
                    entry_parts = [f"## {section['timestamp']}"]
                    if section['title']:
                        entry_parts.append(f" - {section['title']}")
                    if section['category']:
                        entry_parts.append(f" #{section['category']}")
                    
                    entry = "".join(entry_parts) + f"\n\n{section['content']}\n\n---\n\n"
                    content_parts.append(entry)
                
                # 使用原子寫入
                with AtomicFileWriter(memory_file) as f:
                    f.write("".join(content_parts))
            
            logger.info(f"Memory file rebuilt for project: {project_id}")
            return True
            
        except TimeoutError as e:
            logger.error(f"Timeout acquiring lock for rebuilding {project_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error rebuilding memory file for {project_id}: {e}")
            return False

    def get_memory_stats(self, project_id: str) -> Dict[str, Any]:
        """取得記憶統計資訊"""
        logger.info(f"[MARKDOWN] Calling get_memory_stats for project: {project_id}")
        try:
            memory = self.get_memory(project_id)
            if not memory:
                return {'exists': False}

            sections = self._parse_memory_sections(memory)
            categories = [s['category'] for s in sections if s['category']]
            
            return {
                'exists': True,
                'total_entries': len(sections),
                'total_words': len(memory.split()),
                'total_characters': len(memory),
                'categories': list(set(categories)),
                'latest_entry': sections[-1]['timestamp'] if sections else None,
                'oldest_entry': sections[0]['timestamp'] if sections else None
            }
            
        except Exception as e:
            logger.error(f"Error getting memory stats for {project_id}: {e}")
            return {'exists': False, 'error': str(e)}

    def rename_project(self, project_id: str, new_name: str) -> bool:
        """重新命名專案（更新檔案中的專案名稱）"""
        logger.info(f"[MARKDOWN] Calling rename_project for project: {project_id} to: {new_name}")
        try:
            file_path = self.get_memory_file(project_id)
            
            # 檢查檔案是否存在
            if not file_path.exists():
                logger.error(f"Project {project_id} does not exist")
                return False
            
            # 使用檔案鎖定進行安全更新
            with FileLock(file_path):
                # 讀取原始內容
                content = file_path.read_text(encoding='utf-8')
                
                # 更新檔案標題
                lines = content.split('\n')
                if lines and lines[0].startswith('# AI Memory for '):
                    lines[0] = f"# AI Memory for {new_name}"
                    
                    updated_content = '\n'.join(lines)
                    
                    # 寫回檔案
                    with AtomicFileWriter(file_path) as f:
                        f.write(updated_content)
                
                logger.info(f"Project {project_id} renamed to '{new_name}'")
                return True
                
        except TimeoutError as e:
            logger.error(f"Timeout acquiring lock for renaming {project_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error renaming project {project_id} to '{new_name}': {e}")
            return False

class SQLiteBackend(MemoryBackend):
    """
    SQLite 記憶後端
    SQLite Memory Backend
    
    使用 SQLite 資料庫儲存和管理 AI 記憶，支援全文搜尋和高效能查詢
    Stores and manages AI memory using SQLite database with full-text search and high-performance queries
    
    Features / 功能:
    - FTS5 全文搜尋 / FTS5 full-text search
    - 事務安全 / Transaction safety  
    - 索引優化 / Index optimization
    - 自動備份 / Automatic backup
    """
    
    def __init__(self, db_path: str):
        if not db_path or not str(db_path).strip():
            raise ValueError("SQLiteBackend requires an explicit db_path. Use --db-path to specify the database file path.")
        # 展開家目錄並解析為絕對路徑
        resolved_path = Path(os.path.expanduser(str(db_path))).resolve()
        self.db_path = resolved_path
        # 準備目錄並驗證可寫
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # 驗證目錄可寫
        try:
            test_file = self.db_path.parent / ".write_test"
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write("test")
            test_file.unlink()
        except Exception as e:
            raise OSError(
                f"Database directory not writable: {self.db_path.parent}. "
                f"Please run with --db-path pointing to a writable location. Error: {e}"
            )
        # 啟動時檢測常見舊路徑，但不採用、不遷移，只警告
        try:
            candidates = [Path("ai-memory/memory.db"), Path("memory.db")]  # 相對於當前工作目錄
            for cand in candidates:
                try:
                    if cand.exists():
                        cand_abs = cand.resolve()
                        if cand_abs != self.db_path:
                            logger.warning(
                                f"Detected legacy database at '{cand_abs}', but current --db-path is '{self.db_path}'. "
                                f"The legacy DB will NOT be used. If you need it, pass --db-path explicitly.")
                except Exception:
                    continue
        except Exception:
            pass
        # 初始化資料庫
        self._init_database()
    
    @contextmanager
    def get_connection(self):
        """取得資料庫連接"""
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,
            check_same_thread=False
        )
        # 確保使用 UTF-8 編碼處理文本
        conn.text_factory = str
        conn.row_factory = sqlite3.Row
        # 設置 UTF-8 編碼
        conn.execute("PRAGMA encoding = 'UTF-8'")
        self._configure_connection(conn)
        try:
            yield conn
        finally:
            conn.close()
    
    def _configure_connection(self, conn):
        """配置連接最佳化參數"""
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA foreign_keys=ON")
    
    def _init_database(self):
        """初始化資料庫結構"""
        with self.get_connection() as conn:
            # 建立最終版記憶條目表（新結構，無 _new 後綴）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project TEXT NOT NULL,
                    category TEXT,
                    entry_type TEXT NOT NULL DEFAULT 'note',
                    title TEXT NOT NULL,
                    summary TEXT,
                    entry TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 建立索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_project ON memory_entries(project)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_category ON memory_entries(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_entry_type ON memory_entries(entry_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_created ON memory_entries(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_updated ON memory_entries(updated_at)")

            # 建立 FTS5 全文搜尋（對應最終版表）
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    title, summary, entry,
                    content='memory_entries',
                    content_rowid='id',
                    tokenize='trigram'
                )
            """)

            # 建立 FTS5 觸發器（對應最終版表）
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS memory_fts_insert AFTER INSERT ON memory_entries BEGIN
                    INSERT INTO memory_fts(rowid, title, summary, entry) 
                    VALUES (new.id, new.title, new.summary, new.entry);
                END
            """)

            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS memory_fts_delete AFTER DELETE ON memory_entries BEGIN
                    INSERT INTO memory_fts(memory_fts, rowid, title, summary, entry)
                    VALUES('delete', old.id, old.title, old.summary, old.entry);
                END
            """)

            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS memory_fts_update AFTER UPDATE ON memory_entries BEGIN
                    INSERT INTO memory_fts(memory_fts, rowid, title, summary, entry)
                    VALUES('delete', old.id, old.title, old.summary, old.entry);
                    INSERT INTO memory_fts(rowid, title, summary, entry)
                    VALUES (new.id, new.title, new.summary, new.entry);
                END
            """)

            # tree_entries 表已移除，直接使用 memory_entries 表
            
            
            # 資料遷移已完成，不再需要 v2 表格
            
            conn.commit()
            logger.info(f"SQLite database initialized at: {self.db_path}")
    
    
    
    @log_performance("sqlite_save_memory")
    def save_memory(self, project_id: str, content: str, title: str = "", category: str = "") -> bool:
        """儲存記憶到新的簡潔表結構"""
        context = {
            'project_id': project_id,
            'content_length': len(content),
            'has_title': bool(title),
            'has_category': bool(category)
        }
        logger.info("Starting save memory operation", context)
        
        try:
            # 輸入驗證
            project_id = InputValidator.validate_project_id(project_id)
            content = InputValidator.validate_content(content)
            title = InputValidator.validate_title(title)
            category = InputValidator.validate_category(category)
            
            # 使用最終表的 add_memory 方法
            entry_id = self.add_memory(
                project=project_id,
                title=title or "未命名條目",
                entry=content,
                category=category,
                entry_type="note",
                summary=None  # 讓 AI 自己理解內容，不預先生成摘要
            )
            
            logger.operation("save_memory", "success", {
                'project_id': project_id,
                'entry_id': entry_id,
                'content_length': len(content)
            })
            return True
            
        except (ValidationError, SecurityError) as e:
            logger.operation("save_memory", "validation_error", {
                'project_id': project_id,
                'error': str(e)
            })
            return False
        except Exception as e:
            logger.operation("save_memory", "error", {
                'project_id': project_id,
                'error_type': type(e).__name__,
                'error': str(e)
            })
            return False
    
    def get_memory(self, project_id: str) -> Optional[str]:
        """讀取完整專案記憶，轉換為 Markdown 格式（使用新表）"""
        logger.info(f"[SQLITE] Calling get_memory for project: {project_id}")
        try:
            # 使用最終表的 list_memories 方法取得所有條目
            entries = self.list_memories(project=project_id, limit=1000)
            
            if not entries:
                return None
                
            # 轉換為 Markdown 格式
            markdown_parts = [f"# AI Memory for {project_id}\n\n"]
            
            for entry in entries:
                # 格式化時間戳
                timestamp = entry['created_at']
                if isinstance(timestamp, str):
                    # SQLite 返回的可能是字串格式
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        formatted_time = timestamp
                else:
                    formatted_time = timestamp
                
                # 建立條目標題
                header_parts = [f"## {formatted_time}"]
                if entry['title']:
                    header_parts.append(f" - {entry['title']}")
                if entry['category']:
                    header_parts.append(f" #{entry['category']}")
                
                # 組合條目
                entry_md = "".join(header_parts) + f"\n\n{entry['entry']}\n\n---\n\n"
                markdown_parts.append(entry_md)
            
            return "".join(markdown_parts)
                
        except sqlite3.Error as e:
            logger.error(f"Database error reading memory for {project_id}: {e}")
            raise DatabaseError(f"資料庫讀取錯誤: {e}")
        except (ValidationError, SecurityError):
            raise  # 重新拋出驗證錯誤
        except Exception as e:
            logger.error(f"Unexpected error reading memory for {project_id}: {e}")
            return None
    
    @log_performance("sqlite_search_memory")
    def search_memory(self, project_id: str, query: str, limit: int = 10) -> List[Dict[str, str]]:
        """智能搜尋：自動選擇最省token的策略"""
        context = {
            'project_id': project_id,
            'query_length': len(query),
            'limit': limit
        }
        logger.info("Starting smart search operation", context)
        
        try:
            # 輸入驗證
            project_id = InputValidator.validate_project_id(project_id)
            query = InputValidator.validate_query(query)
            
            # 限制 limit 參數範圍
            if not isinstance(limit, int) or limit < 1 or limit > 100:
                limit = 10
                logger.warning(f"Invalid limit parameter, using default: {limit}")
            
            # 智能判斷查詢類型
            query_type = self._analyze_query_type(query)
            logger.info(f"[SQLITE] Query type detected: {query_type}")
            
            if query_type == 'simple_lookup':
                # 簡單查找：使用search_index（超省token）
                return self._simple_search(project_id, query, limit)
                
            elif query_type == 'complex_question':
                # 複雜問題：使用RAG策略（智能省token）
                return self._rag_search(project_id, query, limit)
                
            else:
                # 默認：混合策略
                return self._hybrid_search(project_id, query, limit)
                
        except (ValidationError, SecurityError) as e:
            logger.error(f"[SQLITE] Validation error in search_memory: {e}")
            return []
        except Exception as e:
            logger.error(f"Error in smart search for {project_id}: {e}")
            # 降級到原始搜索
            return self._fallback_search(project_id, query, limit)
    
    def _fts_search(self, project_id: str, query: str, limit: int) -> List[Dict[str, str]]:
        """使用 FTS5 全文搜尋"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT me.title, me.category, me.content, me.created_at,
                       rank
                FROM memory_fts 
                JOIN memory_entries me ON memory_fts.rowid = me.id
                WHERE memory_fts MATCH ? AND me.project_id = ?
                ORDER BY rank
                LIMIT ?
            """, (query, project_id, limit))
            
            results = []
            for row in cursor.fetchall():
                results.append(self._format_search_result(row, 1))
            
            return results
    
    def _like_search(self, project_id: str, query: str, limit: int) -> List[Dict[str, str]]:
        """使用 LIKE 查詢作為備用搜尋方案"""
        with self.get_connection() as conn:
            # 使用 LIKE 查詢搜尋標題、分類和內容
            like_pattern = f"%{query}%"
            cursor = conn.execute("""
                SELECT title, category, content, created_at
                FROM memory_entries 
                WHERE project_id = ? AND (
                    content LIKE ? OR 
                    title LIKE ? OR 
                    category LIKE ?
                )
                ORDER BY created_at DESC
                LIMIT ?
            """, (project_id, like_pattern, like_pattern, like_pattern, limit))
            
            results = []
            for row in cursor.fetchall():
                # 計算相關性（出現次數）
                content = row['content'] or ''
                title = row['title'] or ''
                category = row['category'] or ''
                
                relevance = (
                    content.lower().count(query.lower()) +
                    title.lower().count(query.lower()) * 2 +  # 標題權重更高
                    category.lower().count(query.lower()) * 1.5  # 分類權重中等
                )
                
                results.append(self._format_search_result(row, relevance))
            
            # 按相關性排序
            results.sort(key=lambda x: x['relevance'], reverse=True)
            return results
    
    def _analyze_query_type(self, query: str) -> str:
        """分析查詢類型，決定使用哪種策略"""
        query_lower = query.lower()
        
        # 簡單查找關鍵詞
        simple_keywords = [
            '列表', 'list', '有哪些', '找到', 'find', '搜尋', 'search',
            '顯示', 'show', '查看', 'view', '所有', 'all', '專案', 'project'
        ]
        if any(keyword in query_lower for keyword in simple_keywords):
            return 'simple_lookup'
        
        # 複雜問題關鍵詞
        complex_keywords = [
            '為什麼', 'why', '如何', 'how', '解釋', 'explain', '分析', 'analyze',
            '實現', 'implement', '原理', 'principle', '流程', 'process', '步驟', 'step'
        ]
        if any(keyword in query_lower for keyword in complex_keywords):
            return 'complex_question'
        
        # 根據長度判斷
        if len(query) > 50:
            return 'complex_question'
        elif len(query) < 15:
            return 'simple_lookup'
        
        return 'hybrid'
    
    def _simple_search(self, project_id: str, query: str, limit: int) -> List[Dict[str, str]]:
        """簡單搜索：使用search_index，超省token"""
        logger.info(f"[SQLITE] Using simple search (token-efficient)")
        
        if hasattr(self, 'search_index'):
            index_results = self.search_index(project_id, query, limit)
            
            # 轉換為標準格式
            formatted_results = []
            for result in index_results:
                formatted_results.append({
                    'timestamp': result.get('created_at', ''),
                    'title': result.get('title', ''),
                    'category': result.get('category', ''),
                    'content': result.get('summary', result.get('entry', ''))[:300] + '...',  # 限制內容長度
                    'relevance': result.get('match_type', 'index')
                })
            
            logger.info(f"Simple search returned {len(formatted_results)} results (token-optimized)")
            return formatted_results
        else:
            # 降級到基本搜索
            return self._fallback_search(project_id, query, limit)
    
    def _rag_search(self, project_id: str, query: str, limit: int) -> List[Dict[str, str]]:
        """RAG策略：智能選擇最相關內容，控制token使用"""
        logger.info(f"[SQLITE] Using RAG search (intelligent token control)")
        
        try:
            # 第一階段：輕量級篩選
            if hasattr(self, 'search_index'):
                candidates = self.search_index(project_id, query, limit * 3)
            else:
                candidates = self.search_mem_entries(project=project_id, query=query, limit=limit * 2)
            
            # 第二階段：智能選擇最相關的內容
            selected_results = []
            total_tokens = 0
            max_tokens = 1500  # 控制總token數
            
            for candidate in candidates[:limit * 2]:  # 限制候選數量
                if total_tokens >= max_tokens or len(selected_results) >= limit:
                    break
                
                # 獲取內容
                if 'entry' in candidate:
                    content = candidate['entry']
                else:
                    # 如果是索引結果，獲取完整內容
                    try:
                        full_entry = self.get_memory_entry(candidate.get('id'))
                        content = full_entry['entry'] if full_entry else candidate.get('summary', '')
                    except:
                        content = candidate.get('summary', '')
                
                # 智能截取相關內容
                relevant_content = self._extract_relevant_content(content, query)
                content_tokens = len(relevant_content) // 4  # 粗略估算token
                
                if total_tokens + content_tokens <= max_tokens:
                    selected_results.append({
                        'timestamp': candidate.get('created_at', ''),
                        'title': candidate.get('title', ''),
                        'category': candidate.get('category', ''),
                        'content': relevant_content,
                        'relevance': candidate.get('similarity', 0)
                    })
                    total_tokens += content_tokens
            
            logger.info(f"RAG search returned {len(selected_results)} results (~{total_tokens} tokens)")
            return selected_results
            
        except Exception as e:
            logger.error(f"Error in RAG search: {e}")
            return self._fallback_search(project_id, query, limit)
    
    def _hybrid_search(self, project_id: str, query: str, limit: int) -> List[Dict[str, str]]:
        """混合策略：結合索引和內容搜索"""
        logger.info(f"[SQLITE] Using hybrid search")
        
        try:
            # 先嘗試索引搜索
            index_results = self._simple_search(project_id, query, limit // 2)
            
            # 再補充一些完整內容搜索
            content_results = self._fallback_search(project_id, query, limit // 2)
            
            # 合併結果，去重
            all_results = index_results + content_results
            seen_titles = set()
            unique_results = []
            
            for result in all_results:
                title_key = f"{result['title']}_{result['timestamp']}"
                if title_key not in seen_titles:
                    seen_titles.add(title_key)
                    unique_results.append(result)
                    if len(unique_results) >= limit:
                        break
            
            logger.info(f"Hybrid search returned {len(unique_results)} results")
            return unique_results
            
        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            return self._fallback_search(project_id, query, limit)
    
    def _extract_relevant_content(self, content: str, query: str) -> str:
        """提取與問題最相關的內容片段"""
        if not content:
            return ""
        
        # 簡單實現：找包含問題關鍵詞的段落
        query_keywords = [word.lower() for word in query.split() if len(word) > 2]
        paragraphs = content.split('\n\n')
        
        relevant_paragraphs = []
        for paragraph in paragraphs:
            if any(keyword in paragraph.lower() for keyword in query_keywords):
                relevant_paragraphs.append(paragraph)
        
        if relevant_paragraphs:
            # 限制長度，保留最相關的部分
            result = '\n\n'.join(relevant_paragraphs)
            if len(result) > 800:  # 限制每個條目最大長度
                result = result[:800] + '...'
            return result
        else:
            # 如果沒有直接匹配，返回開頭部分
            return content[:400] + '...' if len(content) > 400 else content
    
    def _fallback_search(self, project_id: str, query: str, limit: int) -> List[Dict[str, str]]:
        """降級搜索：使用原始搜索方法"""
        logger.info(f"[SQLITE] Using fallback search")
        
        try:
            # 使用最終表的 search_mem_entries 方法
            results = self.search_mem_entries(project=project_id, query=query, limit=limit)
            
            # 轉換格式以符合原始 API
            formatted_results = []
            for result in results:
                formatted_results.append({
                    'timestamp': result.get('created_at', ''),
                    'title': result['title'] or '',
                    'category': result['category'] or '',
                    'content': result['entry'],
                    'relevance': 'fallback'
                })
            
            logger.info(f"Fallback search found {len(formatted_results)} results")
            return formatted_results
                
        except Exception as e:
            logger.error(f"Error in fallback search: {e}")
            return []

    def _format_search_result(self, row, relevance: float) -> Dict[str, str]:
        """格式化搜尋結果"""
        # 格式化時間戳
        timestamp = row['created_at']
        if isinstance(timestamp, str):
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                formatted_time = timestamp
        else:
            formatted_time = str(timestamp)
        
        content = row['content'] or ''
        return {
            'timestamp': formatted_time,
            'title': row['title'] or '',
            'category': row['category'] or '',
            'content': content[:500] + "..." if len(content) > 500 else content,
            'relevance': relevance
        }
    
    def list_projects(self) -> List[Dict[str, Any]]:
        """列出所有專案及其統計資訊（使用新表）"""
        logger.info(f"[SQLITE] Calling list_projects")
        try:
            # 使用最終表的 list_projects_stats 方法
            project_stats = self.list_projects_stats()
            
            # 轉換格式以符合原始 API
            projects = []
            for stat in project_stats:
                # 格式化時間
                updated_at = stat['last_updated']
                if isinstance(updated_at, str):
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        formatted_time = updated_at
                else:
                    formatted_time = str(updated_at)
                
                # 取得該專案的分類
                categories = []
                try:
                    with self.get_connection() as conn:
                        cursor = conn.execute("""
                            SELECT DISTINCT category 
                            FROM memory_entries 
                            WHERE project = ? AND category IS NOT NULL
                        """, (stat['project'],))
                        categories = [row[0] for row in cursor.fetchall()]
                except:
                    pass
                
                projects.append({
                    'id': stat['project'],
                    'name': stat['project'].replace('-', ' ').title(),
                    'file_path': f"SQLite: {self.db_path}",
                    'entries_count': stat['total_entries'],
                    'last_modified': formatted_time,
                    'categories': categories
                })
            
            # 只記錄簡化的專案資訊
            simplified_projects = [
                {
                    'id': p['id'],
                    'name': p['name'],
                    'entries_count': p['entries_count'],
                    'last_modified': p['last_modified']
                }
                for p in projects
            ]
            logger.info(f"[SQLITE] list_projects response : {simplified_projects}")
            return projects
                
        except Exception as e:
            logger.error(f"Error listing projects: {e}")
            return []
    
    def get_recent_memory(self, project_id: str, limit: int = 5) -> List[Dict[str, str]]:
        """取得最近的記憶條目（使用新表）"""
        logger.info(f"[SQLITE] Calling get_recent_memory for project: {project_id}")
        try:
            # 使用最終表的 list_memories 方法
            results = self.list_memories(project=project_id, limit=limit)
            
            # 轉換格式以符合原始 API
            formatted_results = []
            for result in results:
                # 格式化時間戳
                timestamp = result['created_at']
                if isinstance(timestamp, str):
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        formatted_time = timestamp
                else:
                    formatted_time = str(timestamp)
                
                formatted_results.append({
                    'timestamp': formatted_time,
                    'title': result['title'] or '',
                    'category': result['category'] or '',
                    'content': result['entry']
                })
            
            return list(reversed(formatted_results))  # 返回時間順序（舊到新）
                
        except Exception as e:
            logger.error(f"Error getting recent memory for {project_id}: {e}")
            return []
    
    def delete_memory(self, project_id: str) -> bool:
        """刪除專案記憶（使用新表）"""
        logger.info(f"[SQLITE] Calling delete_memory for project: {project_id}")
        try:
            with self.get_connection() as conn:
                # 刪除新表中的所有記憶條目（FTS 觸發器會自動清理）
                cursor = conn.execute("DELETE FROM memory_entries WHERE project = ?", (project_id,))
                deleted_entries = cursor.rowcount
                
                conn.commit()
                
                if deleted_entries > 0:
                    logger.info(f"Memory deleted for project: {project_id} ({deleted_entries} entries)")
                    return True
                else:
                    logger.warning(f"No entries found for project: {project_id}")
                    return False
                
        except Exception as e:
            logger.error(f"Error deleting memory for {project_id}: {e}")
            return False
    
    def delete_memory_entry(self, project_id: str, entry_id: str = None, timestamp: str = None, 
                           title: str = None, category: str = None, content_match: str = None) -> Dict[str, Any]:
        """刪除特定的記憶條目（使用新表）"""
        logger.info(f"[SQLITE] Calling delete_memory_entry for project: {project_id}")
        try:
            with self.get_connection() as conn:
                # 建立安全的查詢條件
                conditions = {"project": project_id}
                
                if entry_id is not None:
                    try:
                        conditions["id"] = int(entry_id)
                    except (ValueError, TypeError):
                        return {'success': False, 'message': 'Invalid entry_id format'}
                
                # 使用 LIKE 查詢的條件需要特殊處理
                like_conditions = []
                like_params = []
                
                if timestamp:
                    like_conditions.append("created_at LIKE ?")
                    like_params.append(f"%{timestamp}%")
                
                if title:
                    like_conditions.append("title LIKE ?") 
                    like_params.append(f"%{title}%")
                
                if category:
                    like_conditions.append("category LIKE ?")
                    like_params.append(f"%{category}%")
                
                if content_match:
                    like_conditions.append("entry LIKE ?")
                    like_params.append(f"%{content_match}%")
                
                # 建立安全的 WHERE 子句
                where_clause, where_params = SQLSafetyUtils.build_safe_where_clause(conditions)
                
                # 合併所有條件
                all_conditions = [where_clause] if where_clause else []
                all_conditions.extend(like_conditions)
                all_params = where_params + like_params
                
                final_where_clause = " AND ".join(all_conditions)
                
                # 先查詢要刪除的條目
                select_sql = f"""
                    SELECT id, title, created_at FROM memory_entries 
                    WHERE {final_where_clause}
                """
                cursor = conn.execute(select_sql, all_params)
                entries_to_delete = cursor.fetchall()
                
                if not entries_to_delete:
                    return {'success': False, 'message': 'No matching entries found to delete'}
                
                # 執行刪除
                delete_sql = f"DELETE FROM memory_entries WHERE {final_where_clause}"
                cursor = conn.execute(delete_sql, all_params)
                deleted_count = cursor.rowcount
                
                conn.commit()
                
                # 格式化回應
                deleted_entries = []
                for entry in entries_to_delete:
                    timestamp = entry['created_at']
                    if isinstance(timestamp, str):
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except:
                            formatted_time = timestamp
                    else:
                        formatted_time = str(timestamp)
                    
                    deleted_entries.append({
                        'timestamp': formatted_time,
                        'title': entry['title'] or ''
                    })
                
                # 計算剩餘條目數量
                cursor = conn.execute("SELECT COUNT(*) FROM memory_entries WHERE project = ?", (project_id,))
                remaining_count = cursor.fetchone()[0]
                
                return {
                    'success': True,
                    'message': f"Deleted {deleted_count} entries from project {project_id}",
                    'deleted_count': deleted_count,
                    'remaining_count': remaining_count,
                    'deleted_entries': deleted_entries
                }
                
        except Exception as e:
            logger.error(f"Error deleting memory entry for {project_id}: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    def edit_memory_entry(self, project_id: str, entry_id: str = None, timestamp: str = None,
                         new_title: str = None, new_category: str = None, new_content: str = None) -> Dict[str, Any]:
        """編輯特定的記憶條目（使用新表）"""
        logger.info(f"[SQLITE] Calling edit_memory_entry for project: {project_id}")
        try:
            with self.get_connection() as conn:
                # 建立查詢條件
                where_conditions = ["project = ?"]
                params = [project_id]
                
                if entry_id is not None:
                    try:
                        where_conditions.append("id = ?")
                        params.append(int(entry_id))
                    except ValueError:
                        return {'success': False, 'message': 'Invalid entry_id format'}
                
                if timestamp:
                    where_conditions.append("created_at LIKE ?")
                    params.append(f"%{timestamp}%")
                
                # 先查詢條目是否存在
                select_sql = f"""
                    SELECT id, title, category, created_at FROM memory_entries 
                    WHERE {' AND '.join(where_conditions)}
                    LIMIT 1
                """
                cursor = conn.execute(select_sql, params)
                entry = cursor.fetchone()
                
                if not entry:
                    return {'success': False, 'message': 'No matching entry found to edit'}
                
                # 使用最終表的 edit_memory 方法
                success = self.edit_memory(
                    entry_id=entry['id'],
                    title=new_title,
                    entry=new_content,
                    category=new_category
                )
                
                if not success:
                    return {'success': False, 'message': 'Failed to update entry'}
                
                # 取得更新後的條目
                updated_entry = self.get_memory_entry(entry['id'])
                
                if not updated_entry:
                    return {'success': False, 'message': 'Failed to retrieve updated entry'}
                
                # 格式化時間戳
                timestamp = updated_entry['created_at']
                if isinstance(timestamp, str):
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        formatted_time = timestamp
                else:
                    formatted_time = str(timestamp)
                
                return {
                    'success': True,
                    'message': f"Successfully edited entry in project {project_id}",
                    'edited_entry': {
                        'timestamp': formatted_time,
                        'title': updated_entry['title'] or '',
                        'category': updated_entry['category'] or ''
                    }
                }
                
        except Exception as e:
            logger.error(f"Error editing memory entry for {project_id}: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    def list_memory_entries(self, project_id: str) -> Dict[str, Any]:
        """列出專案中的所有記憶條目，帶有索引（使用最終表）"""
        logger.info(f"[SQLITE] Calling list_memory_entries for project: {project_id}")
        try:
            # 使用最終表的 list_memories 方法
            results = self.list_memories(project=project_id, limit=1000)
            
            entries = []
            for result in results:
                # 格式化時間戳
                timestamp = result['created_at']
                if isinstance(timestamp, str):
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        formatted_time = timestamp
                else:
                    formatted_time = str(timestamp)
                
                content = result['entry']
                entries.append({
                    'id': result['id'],
                    'timestamp': formatted_time,
                    'title': result['title'] or '',
                    'category': result['category'] or '',
                    'content_preview': content[:100] + "..." if len(content) > 100 else content
                })
            
            return {
                'success': True,
                'total_entries': len(entries),
                'entries': entries
            }
                
        except Exception as e:
            logger.error(f"Error listing memory entries for {project_id}: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    def get_memory_stats(self, project_id: str) -> Dict[str, Any]:
        """取得記憶統計資訊（使用最終表）"""
        logger.info(f"[SQLITE] Calling get_memory_stats for project: {project_id}")
        try:
            # 使用最終表的 get_project_stats 方法
            stats = self.get_project_stats(project_id)
            
            if not stats or stats.get('total_entries', 0) == 0:
                return {'exists': False}
            
            # 取得分類資訊
            categories = []
            try:
                with self.get_connection() as conn:
                    cursor = conn.execute("""
                        SELECT DISTINCT category 
                        FROM memory_entries 
                        WHERE project = ? AND category IS NOT NULL
                    """, (project_id,))
                    categories = [row[0] for row in cursor.fetchall()]
            except:
                pass
            
            # 取得內容統計
            total_characters = 0
            try:
                with self.get_connection() as conn:
                    cursor = conn.execute("""
                        SELECT SUM(LENGTH(entry)) as total_characters
                        FROM memory_entries 
                        WHERE project = ?
                    """, (project_id,))
                    result = cursor.fetchone()
                    total_characters = result[0] if result and result[0] else 0
            except:
                pass
            
            # 格式化時間
            def format_timestamp(ts):
                if not ts:
                    return None
                if isinstance(ts, str):
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                        return dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        return ts
                return str(ts)
            
            # 計算字數（簡單估算）
            total_words = total_characters // 5
            
            return {
                'exists': True,
                'total_entries': stats['total_entries'],
                'total_words': total_words,
                'total_characters': total_characters,
                'categories': categories,
                'latest_entry': format_timestamp(stats.get('last_updated')),
                'oldest_entry': format_timestamp(stats.get('first_entry'))
            }
                
        except Exception as e:
            logger.error(f"Error getting memory stats for {project_id}: {e}")
            return {'exists': False, 'error': str(e)}

    def rename_project(self, project_id: str, new_name: str) -> bool:
        """重新命名專案（使用最終表）"""
        logger.info(f"[SQLITE] Calling rename_project for project: {project_id} to: {new_name}")
        try:
            with self.get_connection() as conn:
                # 檢查專案是否存在（使用最終表）
                cursor = conn.execute("SELECT COUNT(*) FROM memory_entries WHERE project = ?", (project_id,))
                if cursor.fetchone()[0] == 0:
                    logger.error(f"Project {project_id} does not exist in memory_entries")
                    return False
                
                # 在最終表架構中，專案重命名實際上是更新所有條目的 project 欄位
                # 這相當於將專案從舊名稱遷移到新名稱
                cursor = conn.execute("""
                    UPDATE memory_entries 
                    SET project = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE project = ?
                """, (new_name, project_id,))
                
                updated_count = cursor.rowcount
                conn.commit()
                
                if updated_count > 0:
                    logger.info(f"Project {project_id} renamed to '{new_name}' ({updated_count} entries updated)")
                    return True
                else:
                    logger.warning(f"No entries found for project {project_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error renaming project {project_id} to '{new_name}': {e}")
            return False
    
    def _count_entries(self, conn, project_id: str) -> int:
        """計算專案的記憶條目數量"""
        cursor = conn.execute("SELECT COUNT(*) FROM memory_entries WHERE project_id = ?", (project_id,))
        return cursor.fetchone()[0]
    
    def _generate_summary(self, content: str, title: str = None) -> str:
        """生成內容摘要，大幅減少 token 使用"""
        if not content:
            return title or "Empty content"
        
        # 清理內容
        content = content.strip()
        
        # 如果有標題，優先使用標題作為摘要基礎
        if title and title.strip():
            title_clean = title.strip()
            # 如果標題已經很好地概括了內容，直接使用
            if len(title_clean) > 10 and len(title_clean) < 100:
                return title_clean
        
        # 提取前200字元，但在句子邊界截斷
        if len(content) <= 200:
            return content
        
        summary = content[:200]
        
        # 在句子邊界截斷
        sentence_endings = ['. ', '。', '！', '!', '？', '?', '\n\n']
        best_cut = 0
        
        for ending in sentence_endings:
            pos = summary.rfind(ending)
            if pos > 50:  # 確保摘要有足夠長度
                best_cut = max(best_cut, pos + len(ending))
        
        if best_cut > 0:
            return summary[:best_cut].strip()
        
        # 如果找不到好的截斷點，在詞邊界截斷
        words = summary.split()
        if len(words) > 1:
            return ' '.join(words[:-1]) + '...'
        
        return summary + '...'
    
    def _extract_keywords(self, content: str, title: str = None, category: str = None) -> str:
        """提取關鍵字，提升搜尋精度"""
        keywords = set()
        
        # 從標題提取
        if title:
            title_words = title.replace('-', ' ').replace('_', ' ').split()
            keywords.update([w.lower() for w in title_words if len(w) > 2])
        
        # 從分類提取
        if category:
            category_words = category.replace('-', ' ').replace('_', ' ').split()
            keywords.update([w.lower() for w in category_words if len(w) > 2])
        
        # 從內容提取技術關鍵字
        if content:
            # 常見技術術語
            tech_terms = ['api', 'sql', 'database', 'index', 'table', 'function', 'class', 'method', 
                         'bug', 'fix', 'error', 'issue', 'feature', 'implement', 'design', 'architecture',
                         'mcp', 'server', 'client', 'backend', 'frontend', 'token', 'memory', 'search',
                         'sqlite', 'markdown', 'hierarchy', 'optimization', 'performance']
            
            content_lower = content.lower()
            for term in tech_terms:
                if term in content_lower:
                    keywords.add(term)
        
        # 限制關鍵字數量，避免過長
        keywords_list = list(keywords)[:10]
        return ', '.join(sorted(keywords_list))
    
    def _detect_hierarchy_level(self, content: str, title: str = None) -> int:
        """檢測階層級別，支援階層結構"""
        if not content:
            return 0
        
        # 檢查標題中的 Markdown 標記
        if title:
            if title.startswith('###'):
                return 2  # 小標題
            elif title.startswith('##'):
                return 1  # 中標題
            elif title.startswith('#'):
                return 0  # 大標題
        
        # 檢查內容中的標記
        lines = content.split('\n')
        for line in lines[:5]:  # 只檢查前5行
            line = line.strip()
            if line.startswith('###'):
                return 2
            elif line.startswith('##'):
                return 1
            elif line.startswith('#'):
                return 0
        
        # 根據內容特徵判斷
        if any(keyword in content.lower() for keyword in ['實作', 'implementation', '步驟', 'step', '細節', 'detail']):
            return 2  # 實作細節
        elif any(keyword in content.lower() for keyword in ['功能', 'feature', '模組', 'module', '階段', 'phase']):
            return 1  # 功能模組
        
        return 0  # 預設為根級別
    
    def _generate_content_hash(self, content: str) -> str:
        """生成內容雜湊，用於檢測變更"""
        import hashlib
        return hashlib.md5(content.encode('utf-8')).hexdigest()[:16]
    
    
    # ==================== INDEX TABLE METHODS ====================
    
    def search_index(self, project_id: str, query: str, limit: int = 10, 
                    entry_type: str = None, status: str = None, need_full_content: bool = False) -> List[Dict]:
        """結構化搜尋 - 直接使用 memory_entries 表"""
        try:
            with self.get_connection() as conn:
                # 直接搜尋 memory_entries 表
                where_conditions = ["project = ?"]
                params = [project_id]
                
                # 文字搜尋條件
                if query:
                    where_conditions.append("(title LIKE ? OR entry LIKE ?)")
                    params.extend([f"%{query}%", f"%{query}%"])
                
                # 執行搜尋
                cursor = conn.execute(f"""
                    SELECT id, project, title, category, entry_type, entry, created_at, updated_at
                    FROM memory_entries
                    WHERE {' AND '.join(where_conditions)}
                    ORDER BY created_at DESC
                    LIMIT ?
                """, params + [limit])
                
                # 轉換結果為字典格式
                results = []
                for row in cursor.fetchall():
                    result = dict(row)
                    result['match_type'] = 'content'
                    results.append(result)
                
                logger.info(f"✅ Search found {len(results)} results for '{query}' in {project_id}")
                return results
                
        except Exception as e:
            logger.error(f"Error searching index for {project_id}: {e}")
            return []
    
    def get_index_entry(self, entry_id: int) -> Dict:
        """獲取特定條目的索引資訊 - 基於 V2 表"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT mi.*, me.title, me.category, me.content, me.created_at as entry_created_at
                    FROM memory_index mi
                    JOIN memory_entries me ON mi.entry_id = me.id
                    WHERE mi.entry_id = ?
                """, (entry_id,))
                
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return {}
                
        except Exception as e:
            logger.error(f"Error getting index entry {entry_id}: {e}")
            return {}
    
    def update_index_entry(self, entry_id: int, **kwargs) -> bool:
        """更新索引條目"""
        try:
            with self.get_connection() as conn:
                # 允許更新的欄位
                allowed_fields = ['summary', 'keywords', 'hierarchy_level', 'entry_type', 
                                'importance_level', 'parent_entry_id', 'hierarchy_path']
                
                update_fields = []
                params = []
                
                for field, value in kwargs.items():
                    if field in allowed_fields:
                        update_fields.append(f"{field} = ?")
                        params.append(value)
                
                if not update_fields:
                    return False
                
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                params.append(entry_id)
                
                conn.execute(f"""
                    UPDATE memory_index 
                    SET {', '.join(update_fields)}
                    WHERE entry_id = ?
                """, params)
                
                conn.commit()
                logger.info(f"Updated index entry {entry_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating index entry {entry_id}: {e}")
            return False
    
    def get_hierarchy_tree(self, project_id: str) -> Dict:
        """獲取專案的階層樹狀結構"""
        try:
            with self.get_connection() as conn:
                # 直接從 memory_entries 獲取條目
                cursor = conn.execute("""
                    SELECT id, title, category, entry_type, created_at
                    FROM memory_entries
                    WHERE project = ?
                    ORDER BY created_at DESC
                """, (project_id,))
                
                entries = []
                for row in cursor.fetchall():
                    entries.append(dict(row))
                
                return {'children': entries}
                
        except Exception as e:
            logger.error(f"Error getting hierarchy tree for {project_id}: {e}")
            return {'children': []}
    
    def rebuild_index_for_project(self, project_id: str) -> Dict:
        """為專案重建所有索引條目 (基於 memory_entries 表)"""
        try:
            with self.get_connection() as conn:
                # 獲取所有記憶條目
                cursor = conn.execute("""
                    SELECT id, title, category, entry, created_at
                    FROM memory_entries
                    WHERE project = ?
                    ORDER BY created_at DESC
                """, (project_id,))
                
                entries = cursor.fetchall()
                total_entries = len(entries)
                
                if total_entries == 0:
                    return {
                        'success': False,
                        'message': f'Project {project_id} has no entries to index'
                    }
                
                logger.info(f"✅ Found {total_entries} entries for project {project_id}")
                return {
                    'success': True,
                    'total_entries': total_entries,
                    'indexed_entries': total_entries,
                    'message': f'Project {project_id} has {total_entries} entries available for search'
                }
                
        except Exception as e:
            logger.error(f"Error rebuilding index for {project_id}: {e}")
            return {'success': False, 'message': str(e)}
    
    def get_index_stats(self, project_id: str = None) -> Dict:
        """獲取索引統計資訊"""
        try:
            with self.get_connection() as conn:
                if project_id:
                    # 專案特定統計
                    cursor = conn.execute("""
                        SELECT COUNT(*) as total,
                               COUNT(DISTINCT entry_type) as types
                        FROM memory_entries
                        WHERE project = ?
                    """, (project_id,))
                    
                    result = cursor.fetchone()
                    return {
                        'total_indexed': result['total'] or 0,
                        'entry_types': result['types'] or 0,
                        'max_hierarchy_level': 0
                    }
                else:
                    # 全局統計
                    cursor = conn.execute("""
                        SELECT COUNT(*) as total,
                               COUNT(DISTINCT project) as projects
                        FROM memory_entries
                    """)
                    
                    result = cursor.fetchone()
                    return {
                        'total_indexed': result['total'] or 0,
                        'indexed_projects': result['projects'] or 0
                    }
                    
        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            return {'total_indexed': 0, 'indexed_projects': 0}
    
    def _detect_entry_type(self, content: str, category: str = None) -> str:
        """檢測條目類型"""
        content_lower = content.lower()
        category_lower = (category or '').lower()
        
        # 根據分類判斷
        if any(keyword in category_lower for keyword in ['bug', 'error', 'fix', '修復', '錯誤']):
            return 'bug'
        elif any(keyword in category_lower for keyword in ['feature', 'enhancement', '功能', '增強']):
            return 'feature'
        elif any(keyword in category_lower for keyword in ['milestone', 'release', '里程碑', '發布']):
            return 'milestone'
        
        # 根據內容判斷
        if any(keyword in content_lower for keyword in ['bug', 'error', 'fix', 'crash', '錯誤', '修復', '崩潰']):
            return 'bug'
        elif any(keyword in content_lower for keyword in ['feature', 'implement', 'add', '功能', '實作', '新增']):
            return 'feature'
        elif any(keyword in content_lower for keyword in ['milestone', 'release', 'version', '里程碑', '發布', '版本']):
            return 'milestone'
        
        return 'discussion'  # 預設為討論
    
    def delete_index_entry(self, entry_id: int) -> bool:
        """刪除索引條目"""
        try:
            with self.get_connection() as conn:
                conn.execute("DELETE FROM memory_index WHERE entry_id = ?", (entry_id,))
                conn.commit()
                logger.info(f"Deleted index entry {entry_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error deleting index entry {entry_id}: {e}")
            return False
    
    
    
    
    # ==================== NEW TABLE METHODS ====================
    
    def add_memory(self, project: str, title: str, entry: str, 
                      category: str = None, entry_type: str = "note", 
                      summary: str = None) -> int:
        """新增記憶條目到最終表"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO memory_entries 
                (project, category, entry_type, title, summary, entry, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (project, category, entry_type, title, summary, entry))
            conn.commit()  # 手動提交事務
            return cursor.lastrowid
    
    def search_mem_entries(self, project: str = None, query: str = None, 
                         category: str = None, entry_type: str = None, 
                         limit: int = 10) -> List[Dict[str, Any]]:
        """搜尋最終表中的記憶條目（內部方法）"""
        with self.get_connection() as conn:
            if query:
                # 使用 FTS5 全文搜尋
                sql = """
                    SELECT m.id, m.project, m.category, m.entry_type, m.title, 
                           m.summary, m.entry, m.created_at, m.updated_at
                    FROM memory_entries m
                    JOIN memory_fts fts ON m.id = fts.rowid
                    WHERE memory_fts MATCH ?
                """
                params = [query]
                
                if project:
                    sql += " AND m.project = ?"
                    params.append(project)
                if category:
                    sql += " AND m.category = ?"
                    params.append(category)
                if entry_type:
                    sql += " AND m.entry_type = ?"
                    params.append(entry_type)
                    
                sql += " ORDER BY bm25(memory_fts) LIMIT ?"
                params.append(limit)
            else:
                # 一般查詢
                sql = """
                    SELECT id, project, category, entry_type, title, 
                           summary, entry, created_at, updated_at
                    FROM memory_entries
                    WHERE 1=1
                """
                params = []
                
                if project:
                    sql += " AND project = ?"
                    params.append(project)
                if category:
                    sql += " AND category = ?"
                    params.append(category)
                if entry_type:
                    sql += " AND entry_type = ?"
                    params.append(entry_type)
                    
                sql += " ORDER BY updated_at DESC LIMIT ?"
                params.append(limit)
            
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_memory_entry(self, entry_id: int) -> Dict[str, Any]:
        """根據 ID 取得記憶條目（最終表）"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, project, category, entry_type, title, 
                       summary, entry, created_at, updated_at
                FROM memory_entries
                WHERE id = ?
            """, (entry_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def list_memories(self, project: str = None, category: str = None, 
                         entry_type: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """列出記憶條目（最終表）"""
        with self.get_connection() as conn:
            sql = """
                SELECT id, project, category, entry_type, title, 
                       summary, entry, created_at, updated_at
                FROM memory_entries
                WHERE 1=1
            """
            params = []
            
            if project:
                sql += " AND project = ?"
                params.append(project)
            if category:
                sql += " AND category = ?"
                params.append(category)
            if entry_type:
                sql += " AND entry_type = ?"
                params.append(entry_type)
                
            sql += " ORDER BY updated_at DESC LIMIT ?"
            params.append(limit)
            
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def edit_memory(self, entry_id: int, title: str = None, entry: str = None,
                       category: str = None, entry_type: str = None, 
                       summary: str = None) -> bool:
        """編輯記憶條目（最終表）"""
        with self.get_connection() as conn:
            # 建立安全的更新欄位
            update_fields = {}
            
            if title is not None:
                update_fields["title"] = title
            if entry is not None:
                update_fields["entry"] = entry
            if category is not None:
                update_fields["category"] = category
            if entry_type is not None:
                update_fields["entry_type"] = entry_type
            if summary is not None:
                update_fields["summary"] = summary
                
            if not update_fields:
                return False
            
            # 使用安全的 UPDATE 子句建立器
            update_clause, update_params = SQLSafetyUtils.build_safe_update_clause(update_fields)
            
            # 加入時間戳更新
            update_clause += ", updated_at = CURRENT_TIMESTAMP"
            update_params.append(entry_id)
            
            sql = f"UPDATE memory_entries SET {update_clause} WHERE id = ?"
            cursor = conn.execute(sql, update_params)
            conn.commit()  # 手動提交事務
            return cursor.rowcount > 0
    
    def delete_memory_by_id(self, entry_id: int) -> bool:
        """刪除記憶條目（最終表）"""
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM memory_entries WHERE id = ?", (entry_id,))
            conn.commit()  # 手動提交事務
            return cursor.rowcount > 0
    
    def get_project_stats(self, project: str) -> Dict[str, Any]:
        """取得專案統計資訊（最終表）"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_entries,
                    COUNT(DISTINCT category) as categories,
                    COUNT(DISTINCT entry_type) as entry_types,
                    MIN(created_at) as first_entry,
                    MAX(updated_at) as last_updated
                FROM memory_entries
                WHERE project = ?
            """, (project,))
            return dict(cursor.fetchone())
    
    def list_projects_stats(self) -> List[Dict[str, Any]]:
        """列出所有專案及統計（最終表）"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT 
                    project,
                    COUNT(*) as total_entries,
                    COUNT(DISTINCT category) as categories,
                    COUNT(DISTINCT entry_type) as entry_types,
                    MAX(updated_at) as last_updated
                FROM memory_entries
                GROUP BY project
                ORDER BY last_updated DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
    
    # ==================== DATA MIGRATION METHODS ====================
    

class DataSyncManager:
    """
    資料同步管理器 - 負責 Markdown 到 SQLite 的同步
    Data Sync Manager - Handles Markdown to SQLite synchronization
    
    提供自動同步功能，包括相似度檢測、內容合併和衝突解決
    Provides auto sync features including similarity detection, content merging, and conflict resolution
    
    Sync Modes / 同步模式:
    - auto: 自動合併 / Automatic merging
    - interactive: 互動式選擇 / Interactive selection  
    - preview: 預覽模式 / Preview mode
    """
    
    def __init__(self, markdown_backend: MemoryBackend, sqlite_backend: MemoryBackend):
        self.markdown = markdown_backend
        self.sqlite = sqlite_backend
        self.sync_log = []
    
    def sync_all_projects(self, mode='auto', similarity_threshold=0.8):
        """同步所有 Markdown 專案到 SQLite
        
        Args:
            mode: 'auto', 'interactive', 'preview'
            similarity_threshold: 相似度閾值 (0.0-1.0)
        """
        logger.info("開始同步 Markdown 專案到 SQLite...")
        
        # 獲取所有 Markdown 專案
        markdown_projects = self.markdown.list_projects()
        
        if not markdown_projects:
            logger.info("沒有找到 Markdown 專案")
            return {'success': True, 'message': '沒有專案需要同步', 'synced': 0}
        
        logger.info(f"找到 {len(markdown_projects)} 個 Markdown 專案")
        
        synced_count = 0
        skipped_count = 0
        error_count = 0
        
        for project in markdown_projects:
            try:
                result = self.sync_project(project['id'], mode, similarity_threshold)
                if result['action'] == 'synced':
                    synced_count += 1
                elif result['action'] == 'skipped':
                    skipped_count += 1
                
                self.sync_log.append({
                    'project_id': project['id'],
                    'action': result['action'],
                    'message': result['message']
                })
                
            except Exception as e:
                error_count += 1
                error_msg = f"同步專案 {project['id']} 時發生錯誤: {str(e)}"
                logger.error(error_msg)
                self.sync_log.append({
                    'project_id': project['id'],
                    'action': 'error',
                    'message': error_msg
                })
        
        summary = {
            'success': True,
            'total_projects': len(markdown_projects),
            'synced': synced_count,
            'skipped': skipped_count,
            'errors': error_count,
            'log': self.sync_log
        }
        
        logger.info(f"同步完成: {synced_count} 個專案已同步, {skipped_count} 個跳過, {error_count} 個錯誤")
        return summary
    
    def sync_project(self, project_id, mode='auto', similarity_threshold=0.8):
        """同步單個專案"""
        logger.info(f"正在同步專案: {project_id}")
        
        # 獲取 Markdown 內容
        markdown_content = self.markdown.get_memory(project_id)
        if not markdown_content:
            return {'action': 'skipped', 'message': f'專案 {project_id} 沒有內容'}
        
        # 檢查 SQLite 中是否已存在
        sqlite_content = self.sqlite.get_memory(project_id)
        
        if sqlite_content:
            # 專案已存在，處理合併邏輯
            return self.handle_existing_project(project_id, markdown_content, sqlite_content, mode, similarity_threshold)
        else:
            # 新專案，直接匯入
            return self.import_project(project_id, markdown_content, mode)
    
    def handle_existing_project(self, project_id, markdown_content, sqlite_content, mode, similarity_threshold):
        """處理已存在的專案"""
        # 計算相似度
        similarity = self.calculate_similarity(markdown_content, sqlite_content)
        
        logger.info(f"專案 {project_id} 相似度: {similarity:.2f}")
        
        if mode == 'preview':
            return {
                'action': 'preview',
                'message': f'專案已存在，相似度: {similarity:.2f}，建議動作: {"合併" if similarity > similarity_threshold else "創建新專案"}'
            }
        
        if similarity > similarity_threshold:
            # 高相似度，自動合併
            if mode == 'auto':
                merged_content = self.merge_contents(markdown_content, sqlite_content)
                success = self.replace_project_content(project_id, merged_content)
                if success:
                    return {'action': 'synced', 'message': f'專案 {project_id} 已合併 (相似度: {similarity:.2f})'}
                else:
                    return {'action': 'error', 'message': f'合併專案 {project_id} 失敗'}
            elif mode == 'interactive':
                # 互動模式 - 這裡簡化為自動合併，實際可以添加用戶輸入
                logger.info(f"互動模式: 自動合併高相似度專案 {project_id}")
                merged_content = self.merge_contents(markdown_content, sqlite_content)
                success = self.replace_project_content(project_id, merged_content)
                if success:
                    return {'action': 'synced', 'message': f'專案 {project_id} 已合併 (互動模式)'}
                else:
                    return {'action': 'error', 'message': f'合併專案 {project_id} 失敗'}
        else:
            # 低相似度，創建新專案
            new_project_id = f"{project_id}-markdown-import"
            success = self.import_project(new_project_id, markdown_content, mode)
            if success['action'] == 'synced':
                return {'action': 'synced', 'message': f'創建新專案 {new_project_id} (原專案相似度過低: {similarity:.2f})'}
            else:
                return success
    
    def import_project(self, project_id, markdown_content, mode):
        """匯入新專案"""
        if mode == 'preview':
            return {'action': 'preview', 'message': f'將創建新專案: {project_id}'}
        
        # 解析 Markdown 內容並匯入到 SQLite
        entries = self.parse_markdown_entries(markdown_content)
        
        success_count = 0
        for entry in entries:
            success = self.sqlite.save_memory(
                project_id,
                entry['content'],
                entry['title'],
                entry['category']
            )
            if success:
                success_count += 1
        
        if success_count > 0:
            return {'action': 'synced', 'message': f'專案 {project_id} 已匯入 ({success_count} 個條目)'}
        else:
            return {'action': 'error', 'message': f'匯入專案 {project_id} 失敗'}
    
    def calculate_similarity(self, content1, content2):
        """計算兩個內容的相似度 (簡化版本)"""
        # 簡化的相似度計算 - 基於關鍵詞重疊
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())
        
        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def merge_contents(self, markdown_content, sqlite_content):
        """合併兩個內容 (簡化版本)"""
        # 簡化的合併邏輯 - 將 Markdown 內容追加到 SQLite 內容
        markdown_entries = self.parse_markdown_entries(markdown_content)
        
        # 這裡簡化處理，實際應該更好地去重和排序
        return markdown_entries
    
    def parse_markdown_entries(self, markdown_content):
        """解析 Markdown 內容為條目列表"""
        entries = []
        lines = markdown_content.split('\n')
        current_entry = None
        current_content = []
        
        for line in lines:
            if line.startswith('## '):
                # 保存上一個條目
                if current_entry:
                    entries.append({
                        'timestamp': current_entry['timestamp'],
                        'title': current_entry['title'],
                        'category': current_entry['category'],
                        'content': '\n'.join(current_content).strip()
                    })
                
                # 解析新條目標題
                header = line[3:].strip()
                timestamp, title, category = self._parse_section_header(header)
                current_entry = {
                    'timestamp': timestamp,
                    'title': title,
                    'category': category
                }
                current_content = []
                
            elif line.strip() == '---':
                # 條目結束
                continue
            else:
                current_content.append(line)
        
        # 處理最後一個條目
        if current_entry:
            entries.append({
                'timestamp': current_entry['timestamp'],
                'title': current_entry['title'],
                'category': current_entry['category'],
                'content': '\n'.join(current_content).strip()
            })
        
        return entries
    
    def _parse_section_header(self, header):
        """解析區段標題，提取時間戳、標題和分類"""
        timestamp = ""
        title = ""
        category = ""
        
        # 提取分類 (hashtag)
        if '#' in header:
            header, category = header.split('#', 1)
            category = category.strip()
        
        # 提取時間戳和標題
        if ' - ' in header:
            timestamp, title = header.split(' - ', 1)
            timestamp = timestamp.strip()
            title = title.strip()
        else:
            timestamp = header.strip()
        
        return timestamp, title, category
    
    def replace_project_content(self, project_id, entries):
        """替換專案內容"""
        try:
            # 先刪除現有內容
            self.sqlite.delete_memory(project_id)
            
            # 重新匯入
            for entry in entries:
                self.sqlite.save_memory(
                    project_id,
                    entry['content'],
                    entry['title'],
                    entry['category']
                )
            return True
        except Exception as e:
            logger.error(f"替換專案內容失敗: {e}")
            return False
    
    def get_sync_report(self):
        """獲取同步報告"""
        return self.sync_log

class ProjectMemoryImporter:
    """專案記憶匯入器 / Project Memory Importer
    
    支援從多種格式匯入專案記憶資料
    Supports importing project memory data from multiple formats
    """
    
    def __init__(self, memory_manager: MemoryBackend):
        self.memory_manager = memory_manager
        self.logger = logging.getLogger(__name__)
    
    def import_from_markdown(self, file_path: str, project_id: str = None, 
                           merge_strategy: str = "append") -> Dict[str, Any]:
        """從 Markdown 檔案匯入記憶資料
        
        Args:
            file_path: Markdown 檔案路徑
            project_id: 目標專案 ID，如果為 None 則從檔案名推斷
            merge_strategy: 合併策略 ("append", "replace", "skip_duplicates")
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # 推斷專案 ID
            if not project_id:
                project_id = file_path.stem.replace('-', '_').replace(' ', '_')
            
            # 讀取 Markdown 內容
            content = file_path.read_text(encoding='utf-8')
            
            # 解析 Markdown 格式的記憶條目
            entries = self._parse_markdown_entries(content)
            
            # 匯入條目
            imported_count = 0
            skipped_count = 0
            
            for entry in entries:
                try:
                    if merge_strategy == "replace":
                        # 替換模式：先清空專案
                        if imported_count == 0:
                            self.memory_manager.delete_memory(project_id)
                    
                    elif merge_strategy == "skip_duplicates":
                        # 檢查重複
                        if self._is_duplicate_entry(project_id, entry):
                            skipped_count += 1
                            continue
                    
                    # 儲存條目
                    self.memory_manager.save_memory(
                        project_id,
                        entry['content'],
                        entry.get('title', ''),
                        entry.get('category', '')
                    )
                    imported_count += 1
                    
                except Exception as e:
                    self.logger.warning(f"Failed to import entry: {e}")
                    continue
            
            return {
                "success": True,
                "project_id": project_id,
                "imported_count": imported_count,
                "skipped_count": skipped_count,
                "total_entries": len(entries),
                "message": f"Successfully imported {imported_count} entries to project '{project_id}'"
            }
            
        except Exception as e:
            self.logger.error(f"Error importing from Markdown: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to import from {file_path}"
            }
    
    def import_from_json(self, file_path: str, project_id: str = None,
                        merge_strategy: str = "append") -> Dict[str, Any]:
        """從 JSON 檔案匯入記憶資料"""
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # 推斷專案 ID
            if not project_id:
                project_id = file_path.stem.replace('-', '_').replace(' ', '_')
            
            # 讀取 JSON 內容
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 解析 JSON 格式
            entries = self._parse_json_entries(data)
            
            # 匯入條目
            imported_count = 0
            skipped_count = 0
            
            for entry in entries:
                try:
                    if merge_strategy == "replace":
                        if imported_count == 0:
                            self.memory_manager.delete_memory(project_id)
                    
                    elif merge_strategy == "skip_duplicates":
                        if self._is_duplicate_entry(project_id, entry):
                            skipped_count += 1
                            continue
                    
                    self.memory_manager.save_memory(
                        project_id,
                        entry['content'],
                        entry.get('title', ''),
                        entry.get('category', '')
                    )
                    imported_count += 1
                    
                except Exception as e:
                    self.logger.warning(f"Failed to import entry: {e}")
                    continue
            
            return {
                "success": True,
                "project_id": project_id,
                "imported_count": imported_count,
                "skipped_count": skipped_count,
                "total_entries": len(entries),
                "message": f"Successfully imported {imported_count} entries to project '{project_id}'"
            }
            
        except Exception as e:
            self.logger.error(f"Error importing from JSON: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to import from {file_path}"
            }
    
    def import_from_csv(self, file_path: str, project_id: str = None,
                       merge_strategy: str = "append") -> Dict[str, Any]:
        """從 CSV 檔案匯入記憶資料"""
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # 推斷專案 ID
            if not project_id:
                project_id = file_path.stem.replace('-', '_').replace(' ', '_')
            
            # 讀取 CSV 內容
            entries = []
            with open(file_path, 'r', encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    entries.append({
                        'timestamp': row.get('timestamp', ''),
                        'title': row.get('title', ''),
                        'category': row.get('category', ''),
                        'content': row.get('content', '')
                    })
            
            # 匯入條目
            imported_count = 0
            skipped_count = 0
            
            for entry in entries:
                try:
                    if not entry['content'].strip():
                        continue
                    
                    if merge_strategy == "replace":
                        if imported_count == 0:
                            self.memory_manager.delete_memory(project_id)
                    
                    elif merge_strategy == "skip_duplicates":
                        if self._is_duplicate_entry(project_id, entry):
                            skipped_count += 1
                            continue
                    
                    self.memory_manager.save_memory(
                        project_id,
                        entry['content'],
                        entry.get('title', ''),
                        entry.get('category', '')
                    )
                    imported_count += 1
                    
                except Exception as e:
                    self.logger.warning(f"Failed to import entry: {e}")
                    continue
            
            return {
                "success": True,
                "project_id": project_id,
                "imported_count": imported_count,
                "skipped_count": skipped_count,
                "total_entries": len(entries),
                "message": f"Successfully imported {imported_count} entries to project '{project_id}'"
            }
            
        except Exception as e:
            self.logger.error(f"Error importing from CSV: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to import from {file_path}"
            }
    
    def import_universal(self, file_path: str, project_id: str = None,
                        merge_strategy: str = "append") -> Dict[str, Any]:
        """通用匯入功能，自動檢測檔案格式"""
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # 根據副檔名檢測格式
            suffix = file_path.suffix.lower()
            
            if suffix == '.md':
                return self.import_from_markdown(str(file_path), project_id, merge_strategy)
            elif suffix == '.json':
                return self.import_from_json(str(file_path), project_id, merge_strategy)
            elif suffix == '.csv':
                return self.import_from_csv(str(file_path), project_id, merge_strategy)
            elif suffix == '.txt':
                # TXT 檔案當作簡單的 Markdown 處理
                return self.import_from_markdown(str(file_path), project_id, merge_strategy)
            else:
                raise ValueError(f"Unsupported file format: {suffix}")
                
        except Exception as e:
            self.logger.error(f"Error in universal import: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to import from {file_path}"
            }
    
    def _parse_markdown_entries(self, content: str) -> List[Dict[str, Any]]:
        """解析 Markdown 格式的記憶條目"""
        entries = []
        
        # 分割條目（使用 ## 或 --- 作為分隔符）
        sections = re.split(r'\n(?:## |\-\-\-\n)', content)
        
        for section in sections:
            if not section.strip():
                continue
            
            entry = {}
            lines = section.strip().split('\n')
            
            # 解析第一行（可能包含時間戳和標題）
            first_line = lines[0] if lines else ""
            
            # 嘗試解析時間戳
            timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})', first_line)
            if timestamp_match:
                entry['timestamp'] = timestamp_match.group(1)
                # 移除時間戳後的部分作為標題
                title = re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', '', first_line).strip()
                if title.startswith('- '):
                    title = title[2:]
                entry['title'] = title
            else:
                entry['title'] = first_line
            
            # 解析分類（尋找 #category 格式）
            category_match = re.search(r'#(\w+)', first_line)
            if category_match:
                entry['category'] = category_match.group(1)
                # 從標題中移除分類標籤
                entry['title'] = re.sub(r'\s*#\w+\s*', '', entry['title']).strip()
            
            # 內容是剩餘的行
            if len(lines) > 1:
                entry['content'] = '\n'.join(lines[1:]).strip()
            else:
                entry['content'] = entry.get('title', '')
            
            if entry['content']:
                entries.append(entry)
        
        return entries
    
    def _parse_json_entries(self, data: Any) -> List[Dict[str, Any]]:
        """解析 JSON 格式的記憶條目"""
        entries = []
        
        if isinstance(data, list):
            # 陣列格式
            for item in data:
                if isinstance(item, dict):
                    entries.append(self._normalize_entry(item))
                elif isinstance(item, str):
                    entries.append({'content': item})
        
        elif isinstance(data, dict):
            # 物件格式
            if 'entries' in data:
                # 有 entries 欄位
                for item in data['entries']:
                    entries.append(self._normalize_entry(item))
            else:
                # 單一條目
                entries.append(self._normalize_entry(data))
        
        return entries
    
    def _normalize_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """標準化條目格式"""
        normalized = {}
        
        # 內容欄位的可能名稱
        content_fields = ['content', 'text', 'body', 'message', 'description']
        for field in content_fields:
            if field in entry and entry[field]:
                normalized['content'] = str(entry[field])
                break
        
        # 標題欄位
        title_fields = ['title', 'name', 'subject', 'heading']
        for field in title_fields:
            if field in entry and entry[field]:
                normalized['title'] = str(entry[field])
                break
        
        # 分類欄位
        category_fields = ['category', 'tag', 'type', 'label']
        for field in category_fields:
            if field in entry and entry[field]:
                normalized['category'] = str(entry[field])
                break
        
        # 時間戳欄位
        timestamp_fields = ['timestamp', 'created_at', 'date', 'time']
        for field in timestamp_fields:
            if field in entry and entry[field]:
                normalized['timestamp'] = str(entry[field])
                break
        
        return normalized
    
    def _is_duplicate_entry(self, project_id: str, entry: Dict[str, Any]) -> bool:
        """檢查是否為重複條目"""
        try:
            # 搜尋相似內容
            search_results = self.memory_manager.search_memory(
                project_id, entry['content'][:100], limit=5
            )
            
            # 簡單的重複檢測：內容前100字符相同
            entry_preview = entry['content'][:100].strip().lower()
            for result in search_results:
                if result['content'][:100].strip().lower() == entry_preview:
                    return True
            
            return False
            
        except Exception:
            # 如果檢測失敗，假設不重複
            return False


class MCPServer:
    """
    Model Context Protocol 伺服器
    Model Context Protocol Server
    
    實作 MCP 協議的伺服器，提供記憶管理工具給 AI 助手使用
    Implements MCP protocol server providing memory management tools for AI assistants
    
    Capabilities / 功能:
    - 工具調用 / Tool invocation
    - 記憶管理 / Memory management  
    - 專案同步 / Project synchronization
    - 啟動時專案顯示 / Startup project display
    """
    
    def __init__(self, backend: MemoryBackend = None):
        if backend is None:
            raise ValueError("MCPServer requires an explicit backend. For SQLite backend, start the server with --backend=sqlite and --db-path=<path>.")
        self.memory_manager = backend
        self.version = "1.0.0"
        
        
        # 初始化匯入器
        self.importer = ProjectMemoryImporter(self.memory_manager)

    async def handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """處理 MCP 訊息"""
        # 提取請求 ID 用於回應
        request_id = message.get('id')
        
        try:
            method = message.get('method')
            logger.info(f"[MCP] Handling message with method: {method}, id: {request_id}")
            
            if method == 'initialize':
                response = await self.handle_initialize(message)
            elif method == 'tools/list':
                logger.info("[MCP] About to call list_tools")
                response = await self.list_tools()
                logger.info(f"[MCP] list_tools returned, response type: {type(response)}")
            elif method == 'tools/call':
                response = await self.call_tool(message['params'])
            elif method == 'resources/list':
                response = await self.list_resources()
            elif method == 'prompts/list':
                response = await self.list_prompts()
            elif method == 'notifications/initialized':
                response = await self.handle_initialized()
            else:
                response = self._error_response(-32601, f"Method not found: {method}")
            
            # 確保回應包含正確的請求 ID（除了通知消息）
            if response is not None and request_id is not None:
                response['id'] = request_id
            
            logger.info(f"[MCP] handle_message returning response for method: {method}")
            return response
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            error_response = self._error_response(-32603, str(e))
            # 錯誤回應也需要包含請求 ID
            if request_id is not None:
                error_response['id'] = request_id
            return error_response

    async def handle_initialize(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """處理初始化請求"""
        return {
            'jsonrpc': '2.0',
            'result': {
                'protocolVersion': '2024-11-05',
                'capabilities': {
                    'tools': {}
                },
                'serverInfo': {
                    'name': 'markdown-memory-mcp',
                    'version': self.version
                }
            }
        }

    async def list_tools(self) -> Dict[str, Any]:
        """列出可用工具"""
        logger.info("[MCP] Starting list_tools function")
        tools = [
            # 🎯 優先級工具：Claude 最常用的查詢工具放在前面
            {
                'name': 'list_memory_projects',
                'description': '📂 查看所有可用的專案列表 / View all available projects - 🚀 開始任何工作前建議先查看',
                'inputSchema': {
                    'type': 'object',
                    'properties': {},
                    'required': []
                }
            },
            {
                'name': 'search_project_memory',
                'description': '🔍 搜尋專案記憶，回答專案相關問題 / Search project memory to answer questions - 🎯 優先使用此工具了解專案',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'project_id': {
                            'type': 'string',
                            'description': 'Project identifier'
                        },
                        'query': {
                            'type': 'string',
                            'description': 'Search query'
                        },
                        'limit': {
                            'type': 'integer',
                            'description': 'Maximum number of results to return',
                            'default': 10
                        }
                    },
                    'required': ['project_id', 'query']
                }
            },
            {
                'name': 'get_project_memory',
                'description': '📖 取得完整專案記憶內容 / Get full project memory content - 深入了解專案詳情',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'project_id': {
                            'type': 'string',
                            'description': 'Project identifier'
                        }
                    },
                    'required': ['project_id']
                }
            },
            {
                'name': 'get_recent_project_memory',
                'description': '📅 取得最近的專案記憶條目 / Get recent project memory entries - 了解最新進展',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'project_id': {
                            'type': 'string',
                            'description': 'Project identifier'
                        },
                        'limit': {
                            'type': 'integer',
                            'description': 'Number of recent entries to return',
                            'default': 5
                        }
                    },
                    'required': ['project_id']
                }
            },
            # 📊 統計工具：快速了解專案概況
            {
                'name': 'get_project_memory_stats',
                'description': '📊 取得專案記憶統計資訊 / Get project memory statistics - 快速了解專案規模和狀態',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'project_id': {
                            'type': 'string',
                            'description': 'Project identifier'
                        }
                    },
                    'required': ['project_id']
                }
            },
            # 🤖 智能查詢工具：RAG 問答系統
            {
                'name': 'rag_query',
                'description': '🧠 基於專案記憶的智能問答 / RAG-based intelligent Q&A - 回答複雜專案問題',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'project_id': {
                            'type': 'string',
                            'description': 'Project identifier'
                        },
                        'question': {
                            'type': 'string',
                            'description': 'Question to answer based on project memory'
                        },
                        'context_limit': {
                            'type': 'integer',
                            'description': 'Maximum number of relevant contexts to include',
                            'default': 5
                        },
                        'max_tokens': {
                            'type': 'integer',
                            'description': 'Maximum tokens for context (controls response length)',
                            'default': 2000
                        }
                    },
                    'required': ['project_id', 'question']
                }
            },
            {
                'name': 'summarize_project',
                'description': '📊 生成專案內容摘要 / Generate project content summary - 快速了解專案概況和架構',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'project_id': {
                            'type': 'string',
                            'description': 'Project identifier'
                        },
                        'summary_type': {
                            'type': 'string',
                            'enum': ['brief', 'detailed', 'timeline'],
                            'description': 'Summary type: brief (quick overview), detailed (comprehensive), timeline (chronological)',
                            'default': 'brief'
                        },
                        'max_entries': {
                            'type': 'integer',
                            'description': 'Maximum number of entries to analyze',
                            'default': 20
                        }
                    },
                    'required': ['project_id']
                }
            },
            # 💾 儲存工具：放在後面，避免優先選擇
            {
                'name': 'save_project_memory',
                'description': '💾 儲存資訊到專案記憶 / Save information to project memory - 保存重要發現和決定',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'project_id': {
                            'type': 'string',
                            'description': 'Project identifier (will be sanitized for filename)'
                        },
                        'content': {
                            'type': 'string',
                            'description': 'Content to save to project memory'
                        },
                        'title': {
                            'type': 'string',
                            'description': 'Optional title for the project memory entry'
                        },
                        'category': {
                            'type': 'string',
                            'description': 'Optional category/tag for the project memory entry'
                        }
                    },
                    'required': ['project_id', 'content']
                }
            },
            # 🗑️ 管理工具：危險操作放最後
            {
                'name': 'delete_project_memory',
                'description': '⚠️ 刪除專案記憶 / Delete project memory - 危險操作，請謹慎使用',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'project_id': {
                            'type': 'string',
                            'description': 'Project identifier'
                        }
                    },
                    'required': ['project_id']
                }
            },
            {
                'name': 'delete_project_memory_entry',
                'description': 'Delete specific project memory entries based on various criteria',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'project_id': {
                            'type': 'string',
                            'description': 'Project identifier'
                        },
                        'entry_id': {
                            'type': 'string',
                            'description': 'Entry ID (1-based index) to delete'
                        },
                        'timestamp': {
                            'type': 'string',
                            'description': 'Timestamp pattern to match for deletion'
                        },
                        'title': {
                            'type': 'string',
                            'description': 'Title pattern to match for deletion'
                        },
                        'category': {
                            'type': 'string',
                            'description': 'Category pattern to match for deletion'
                        },
                        'content_match': {
                            'type': 'string',
                            'description': 'Content pattern to match for deletion'
                        }
                    },
                    'required': ['project_id']
                }
            },
            {
                'name': 'edit_project_memory_entry',
                'description': 'Edit specific project memory entry content',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'project_id': {
                            'type': 'string',
                            'description': 'Project identifier'
                        },
                        'entry_id': {
                            'type': 'string',
                            'description': 'Entry ID (1-based index) to edit'
                        },
                        'timestamp': {
                            'type': 'string',
                            'description': 'Timestamp pattern to match for editing'
                        },
                        'new_title': {
                            'type': 'string',
                            'description': 'New title for the entry'
                        },
                        'new_category': {
                            'type': 'string',
                            'description': 'New category for the entry'
                        },
                        'new_content': {
                            'type': 'string',
                            'description': 'New content for the entry'
                        }
                    },
                    'required': ['project_id']
                }
            },
            {
                'name': 'list_project_memory_entries',
                'description': 'List all project memory entries with their IDs for easy reference',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'project_id': {
                            'type': 'string',
                            'description': 'Project identifier'
                        }
                    },
                    'required': ['project_id']
                }
            },
            {
                'name': 'sync_markdown_to_sqlite',
                'description': '同步 Markdown 專案到 SQLite / Sync all Markdown projects to SQLite backend with auto merging',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'mode': {
                            'type': 'string',
                            'enum': ['auto', 'interactive', 'preview'],
                            'default': 'auto',
                            'description': 'Sync mode: auto merge, interactive prompts, or preview only'
                        },
                        'similarity_threshold': {
                            'type': 'number',
                            'default': 0.8,
                            'minimum': 0.0,
                            'maximum': 1.0,
                            'description': 'Similarity threshold for automatic merging (0.0-1.0)'
                        }
                    }
                }
            },
            {
                'name': 'export_project_memory',
                'description': '匯出專案記憶 / Export project memory to various formats',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'project_id': {
                            'type': 'string',
                            'description': 'Project identifier to export'
                        },
                        'format': {
                            'type': 'string',
                            'enum': ['markdown', 'json', 'csv', 'txt'],
                            'default': 'markdown',
                            'description': 'Export format (default: markdown)'
                        },
                        'output_path': {
                            'type': 'string',
                            'description': 'Optional output file path (if not provided, returns content as text)'
                        },
                        'include_metadata': {
                            'type': 'boolean',
                            'default': True,
                            'description': 'Include metadata like timestamps and categories'
                        }
                    },
                    'required': ['project_id']
                }
            },
            {
                'name': 'save_global_memory',
                'description': '儲存全局記憶 / Save global memory for cross-project knowledge',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'content': {
                            'type': 'string',
                            'description': 'Content to save to global memory'
                        },
                        'title': {
                            'type': 'string',
                            'description': 'Optional title for the global memory entry'
                        },
                        'category': {
                            'type': 'string',
                            'description': 'Optional category/tag for the global memory entry'
                        }
                    },
                    'required': ['content']
                }
            },
            {
                'name': 'get_global_memory',
                'description': '取得全局記憶 / Get all global memory content',
                'inputSchema': {
                    'type': 'object',
                    'properties': {},
                    'required': []
                }
            },
            {
                'name': 'search_global_memory',
                'description': '搜尋全局記憶 / Search global memory for specific content',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'query': {
                            'type': 'string',
                            'description': 'Search query'
                        },
                        'limit': {
                            'type': 'integer',
                            'default': 10,
                            'description': 'Maximum number of results to return'
                        }
                    },
                    'required': ['query']
                }
            },
            {
                'name': 'get_global_memory_stats',
                'description': '取得全局記憶統計 / Get global memory statistics',
                'inputSchema': {
                    'type': 'object',
                    'properties': {},
                    'required': []
                }
            },
            {
                'name': 'get_backend_status',
                'description': '快速查看當前後端狀態 / Quick check current backend status',
                'inputSchema': {
                    'type': 'object',
                    'properties': {},
                    'required': []
                }
            },
            {
                'name': 'rename_project',
                'description': '重新命名專案 / Rename a project',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'project_id': {
                            'type': 'string',
                            'description': 'Project identifier'
                        },
                        'new_name': {
                            'type': 'string',
                            'description': 'New project name'
                        }
                    },
                    'required': ['project_id', 'new_name']
                }
            },
            {
                'name': 'search_index',
                'description': '🚀 智能搜尋 - 使用 Index Table 大幅減少 token 使用',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'project_id': {'type': 'string', 'description': '專案 ID'},
                        'query': {'type': 'string', 'description': '搜尋關鍵字'},
                        'limit': {'type': 'integer', 'description': '最大結果數量', 'default': 10}
                    },
                    'required': ['project_id', 'query']
                }
            },
            {
                'name': 'get_hierarchy_tree',
                'description': '📊 獲取專案的階層樹狀結構',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'project_id': {'type': 'string', 'description': '專案 ID'}
                    },
                    'required': ['project_id']
                }
            },
            {
                'name': 'rebuild_index_for_project',
                'description': '🔄 為專案重建所有索引條目 (批量處理現有條目)',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'project_id': {'type': 'string', 'description': '專案 ID'}
                    },
                    'required': ['project_id']
                }
            },
            {
                'name': 'get_index_stats',
                'description': '📈 獲取索引統計資訊',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'project_id': {'type': 'string', 'description': '專案 ID (可選，不提供則顯示全局統計)'}
                    },
                    'required': []
                }
            },
            {
                'name': 'update_index_entry',
                'description': '✏️ 更新索引條目的階層和分類資訊',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'entry_id': {'type': 'integer', 'description': '條目 ID'},
                        'summary': {'type': 'string', 'description': '新的摘要'},
                        'keywords': {'type': 'string', 'description': '新的關鍵字'},
                        'hierarchy_level': {'type': 'integer', 'description': '階層級別 (0=大標題, 1=中標題, 2=小標題)'},
                        'entry_type': {'type': 'string', 'description': '條目類型 (discussion/feature/bug/milestone)'},
                        'importance_level': {'type': 'integer', 'description': '重要程度 (1-5)'},
                        'parent_entry_id': {'type': 'integer', 'description': '父條目 ID'}
                    },
                    'required': ['entry_id']
                }
            },
            {
                'name': 'import_project_memory_universal',
                'description': '通用匯入專案記憶 / Universal import project memory from various formats (auto-detect)',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'file_path': {
                            'type': 'string',
                            'description': 'Path to the file to import (supports .md, .json, .csv, .txt)'
                        },
                        'project_id': {
                            'type': 'string',
                            'description': 'Target project ID (optional, will be inferred from filename if not provided)'
                        },
                        'merge_strategy': {
                            'type': 'string',
                            'enum': ['append', 'replace', 'skip_duplicates'],
                            'default': 'append',
                            'description': 'How to handle existing data: append (add to existing), replace (clear first), skip_duplicates (avoid duplicates)'
                        }
                    },
                    'required': ['file_path']
                }
            },
            {
                'name': 'import_project_memory_from_markdown',
                'description': '從 Markdown 檔案匯入專案記憶 / Import project memory from Markdown file',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'file_path': {
                            'type': 'string',
                            'description': 'Path to the Markdown file to import'
                        },
                        'project_id': {
                            'type': 'string',
                            'description': 'Target project ID (optional, will be inferred from filename if not provided)'
                        },
                        'merge_strategy': {
                            'type': 'string',
                            'enum': ['append', 'replace', 'skip_duplicates'],
                            'default': 'append',
                            'description': 'How to handle existing data'
                        }
                    },
                    'required': ['file_path']
                }
            },
            {
                'name': 'import_project_memory_from_json',
                'description': '從 JSON 檔案匯入專案記憶 / Import project memory from JSON file',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'file_path': {
                            'type': 'string',
                            'description': 'Path to the JSON file to import'
                        },
                        'project_id': {
                            'type': 'string',
                            'description': 'Target project ID (optional, will be inferred from filename if not provided)'
                        },
                        'merge_strategy': {
                            'type': 'string',
                            'enum': ['append', 'replace', 'skip_duplicates'],
                            'default': 'append',
                            'description': 'How to handle existing data'
                        }
                    },
                    'required': ['file_path']
                }
            },
            {
                'name': 'import_project_memory_from_csv',
                'description': '從 CSV 檔案匯入專案記憶 / Import project memory from CSV file',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'file_path': {
                            'type': 'string',
                            'description': 'Path to the CSV file to import (expects columns: timestamp, title, category, content)'
                        },
                        'project_id': {
                            'type': 'string',
                            'description': 'Target project ID (optional, will be inferred from filename if not provided)'
                        },
                        'merge_strategy': {
                            'type': 'string',
                            'enum': ['append', 'replace', 'skip_duplicates'],
                            'default': 'append',
                            'description': 'How to handle existing data'
                        }
                    },
                    'required': ['file_path']
                }
            },
            {
                'name': 'import_project_memory_from_txt',
                'description': '從 TXT 檔案匯入專案記憶 / Import project memory from TXT file',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'file_path': {
                            'type': 'string',
                            'description': 'Path to the TXT file to import (treated as simple markdown)'
                        },
                        'project_id': {
                            'type': 'string',
                            'description': 'Target project ID (optional, will be inferred from filename if not provided)'
                        },
                        'merge_strategy': {
                            'type': 'string',
                            'enum': ['append', 'replace', 'skip_duplicates'],
                            'default': 'append',
                            'description': 'How to handle existing data'
                        }
                    },
                    'required': ['file_path']
                }
            }
        ]
        
        logger.info(f"[MCP] Successfully created {len(tools)} tools")
        return {
            'jsonrpc': '2.0',
            'result': {
                'tools': tools
            }
        }

    async def list_resources(self) -> Dict[str, Any]:
        """列出可用資源（目前為空）"""
        return {
            'jsonrpc': '2.0',
            'result': {
                'resources': []
            }
        }

    async def list_prompts(self) -> Dict[str, Any]:
        """列出可用提示（目前為空）"""
        return {
            'jsonrpc': '2.0',
            'result': {
                'prompts': []
            }
        }

    async def handle_initialized(self) -> None:
        """處理初始化完成通知（無需回應）"""
        logger.info("Client initialization completed")
        
        # 自動顯示專案列表 / Auto display project list
        try:
            projects = self.memory_manager.list_projects()
            if projects:
                welcome_message = f"""🎉 **記憶管理系統已啟動 / Memory Management System Started**
發現 {len(projects)} 個專案 / Found {len(projects)} projects:

"""
                for project in projects:
                    welcome_message += f"**{project['name']}** (`{project['id']}`)\n"
                    welcome_message += f"  - 條目 / Entries: {project['entries_count']} 個\n"
                    welcome_message += f"  - 最後修改 / Last Modified: {project['last_modified']}\n"
                    if project['categories']:
                        welcome_message += f"  - 類別 / Categories: {', '.join(project['categories'])}\n"
                    welcome_message += "\n"
                
                welcome_message += """💡 使用 `list_memory_projects` 工具可隨時查看專案列表
💡 Use `list_memory_projects` tool to view project list anytime"""
                
                # 發送歡迎訊息作為通知
                notification = {
                    'jsonrpc': '2.0',
                    'method': 'notifications/message',
                    'params': {
                        'level': 'info',
                        'logger': 'memory-server',
                        'data': welcome_message
                    }
                }
                
                # 輸出通知
                print(json.dumps(notification, ensure_ascii=False))
                sys.stdout.flush()
                
            else:
                # 如果沒有專案，發送提示訊息 / If no projects, send guidance message
                welcome_message = """📝 **記憶管理系統已啟動 / Memory Management System Started**
目前沒有專案，可以開始創建您的第一個記憶！
No projects found. You can start creating your first memory!

💡 使用 `save_project_memory` 工具開始記錄
💡 Use `save_project_memory` tool to start recording"""
                notification = {
                    'jsonrpc': '2.0',
                    'method': 'notifications/message',
                    'params': {
                        'level': 'info',
                        'logger': 'memory-server',
                        'data': welcome_message
                    }
                }
                print(json.dumps(notification, ensure_ascii=False))
                sys.stdout.flush()
                
        except Exception as e:
            logger.error(f"Error displaying welcome message: {e}")
        
        return None

    async def call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """執行工具調用"""
        tool_name = params.get('name')
        arguments = params.get('arguments', {})

        logger.info(f" ****** call tool ****** {params.get('name')} and arguments: {params.get('arguments')}")
        try:
            if tool_name == 'save_project_memory':
                success = self.memory_manager.save_memory(
                    arguments['project_id'],
                    arguments['content'],
                    arguments.get('title', ''),
                    arguments.get('category', '')
                )
                return self._success_response(
                    f"Memory {'saved' if success else 'failed to save'} for project: {arguments['project_id']}"
                )


            elif tool_name == 'get_project_memory':
                project_id = arguments.get('project_id')
                logger.info(f"[MCP] get_project_memory called with project_id: {project_id}")
                if not project_id:
                    logger.error(f"[MCP] get_project_memory: missing project_id in arguments: {arguments}")
                    return self._error_response(-32602, "Missing required parameter: project_id")
                
                memory = self.memory_manager.get_memory(project_id)
                return self._success_response(
                    memory or f"No memory found for project: {project_id}"
                )

            elif tool_name == 'search_project_memory':
                try:
                    project_id = arguments['project_id']
                    query = arguments['query']
                    limit = arguments.get('limit', 10)
                    
                    logger.info(f"智能搜尋: 專案={project_id}, 查詢='{query}'")
                    
                    # 使用智能路由系統
                    smart_result = self.memory_manager.smart_search(project_id, query, limit)
                    
                    if smart_result['result_count'] == 0:
                        text = f"🔍 **搜尋結果**\n\n"
                        text += f"**專案**: {project_id}\n"
                        text += f"**查詢**: {query}\n\n"
                        text += "❌ 沒有找到匹配的內容\n\n"
                        text += "💡 **建議**:\n"
                        text += "   • 嘗試使用不同的關鍵字\n"
                        text += "   • 使用 `rag_query` 進行更智能的問答\n"
                        text += "   • 檢查專案ID是否正確\n"
                        return self._success_response(text)
                    
                    # 根據搜尋策略格式化輸出
                    if smart_result['strategy'] == 'simple_lookup':
                        # 簡單查找模式：顯示摘要
                        text = f"🔍 **智能搜尋 - 快速模式**\n\n"
                        text += f"**專案**: {project_id}\n"
                        text += f"**查詢**: {query}\n"
                        text += f"**策略**: 摘要模式 (節省 token)\n\n"
                        text += f"✅ {smart_result['message']}\n\n"
                        
                        for i, result in enumerate(smart_result['results'], 1):
                            text += f"**{i}.** "
                            if result['title']:
                                text += f"{result['title']}"
                            if result['category']:
                                text += f" #{result['category']}"
                            if result['timestamp']:
                                text += f" ({result['timestamp'][:16]})"
                            text += f"\n📝 {result['summary']}\n"
                            if result['full_content_available']:
                                text += "💡 使用 `rag_query` 查看完整內容\n"
                            text += "\n"
                        
                    elif smart_result['strategy'] == 'complex_question':
                        # 複雜問題模式：顯示 RAG 結果
                        text = f"🧠 **智能搜尋 - 深度模式**\n\n"
                        text += f"**專案**: {project_id}\n"
                        text += f"**問題**: {query}\n"
                        text += f"**策略**: RAG 智能問答\n\n"
                        text += f"✅ {smart_result['message']}\n\n"
                        
                        if 'rag_prompt' in smart_result:
                            text += "**📝 回答提示**:\n"
                            text += smart_result['rag_prompt']
                            text += "\n\n**📚 參考資料**:\n"
                            
                            for i, source in enumerate(smart_result['results'], 1):
                                text += f"\n**{i}.** "
                                if source['title']:
                                    text += f"{source['title']}"
                                if source['category']:
                                    text += f" #{source['category']}"
                                if source['timestamp']:
                                    text += f" ({source['timestamp'][:16]})"
                                text += f"\n`{source['content_preview']}`\n"
                        
                    else:
                        # 混合策略或其他
                        text = f"🔍 **搜尋結果**\n\n"
                        text += f"**專案**: {project_id}\n"
                        text += f"**查詢**: {query}\n"
                        text += f"**策略**: {smart_result['strategy']}\n\n"
                        text += f"找到 {smart_result['result_count']} 條匹配記憶:\n\n"
                        
                        for i, result in enumerate(smart_result['results'], 1):
                            text += f"**{i}. {result.get('timestamp', '')}"
                            if result.get('title'):
                                text += f" - {result['title']}"
                            if result.get('category'):
                                text += f" #{result['category']}"
                            text += f"**\n{result.get('content', result.get('entry', ''))}\n\n"
                    
                    return self._success_response(text)
                    
                except Exception as e:
                    logger.error(f"Error in smart search: {e}")
                    return self._success_response("❌ 智能搜尋系統暫時無法使用")

            elif tool_name == 'list_memory_projects':
                try:
                    projects = self.memory_manager.list_projects()
                    
                    if projects:
                        text = f"📋 **Available Projects ({len(projects)} total)**\n\n"
                        
                        # 智能建議：分析專案狀態
                        rich_projects = []  # 內容豐富的專案
                        recent_projects = []  # 最近活動的專案
                        
                        # 顯示所有專案的摘要信息
                        for i, project in enumerate(projects, 1):
                            name = str(project.get('name', 'Unknown'))[:40]
                            project_id = str(project.get('id', 'unknown'))[:25]
                            entries = project.get('entries_count', 0)
                            last_modified = str(project.get('last_modified', 'Unknown'))[:16]
                            
                            # 根據內容多少給出不同的建議圖標
                            if entries == 0:
                                icon = "🆕"
                                suggestion = "新專案"
                            elif entries < 5:
                                icon = "📝"
                                suggestion = f"{entries} 條記憶"
                            elif entries < 20:
                                icon = "📚"
                                suggestion = f"{entries} 條記憶"
                                recent_projects.append(project_id)
                            else:
                                icon = "🏗️"
                                suggestion = f"{entries} 條記憶 - 豐富專案"
                                rich_projects.append(project_id)
                            
                            text += f"{icon} **{i}.** `{project_id}` - {suggestion} (更新: {last_modified})\n"
                        
                        # 智能建議區塊
                        text += "\n---\n\n"
                        text += "💡 **建議下一步 / Suggested Next Steps:**\n\n"
                        
                        if rich_projects:
                            text += f"🔍 **豐富專案 ({len(rich_projects)} 個)**：建議使用 `search_project_memory` 搜尋具體內容\n"
                            text += f"   推薦專案：{', '.join([f'`{p}`' for p in rich_projects[:3]])}\n\n"
                        
                        if recent_projects:
                            text += f"📊 **活躍專案 ({len(recent_projects)} 個)**：使用 `get_project_memory_stats` 查看詳細統計\n"
                            text += f"   推薦專案：{', '.join([f'`{p}`' for p in recent_projects[:3]])}\n\n"
                        
                        text += "🎯 **快速開始**：\n"
                        text += "   • `rag_query(project_id, \"這個專案是什麼？\")` - 🧠 智能問答\n"
                        text += "   • `search_project_memory(project_id, \"概況\")` - 搜尋特定內容\n"
                        text += "   • `get_recent_project_memory(project_id)` - 查看最新進展\n"
                        text += "   • `get_project_memory_stats(project_id)` - 專案統計資訊\n"
                        
                    else:
                        text = "📝 **沒有找到專案**\n\n"
                        text += "💡 使用 `save_project_memory` 開始記錄第一個專案的內容"
                    
                    return self._success_response(text)
                except Exception as e:
                    logger.error(f"Error in list_memory_projects: {e}")
                    return self._success_response("❌ Error: Unable to list projects at this time")

            elif tool_name == 'get_recent_project_memory':
                results = self.memory_manager.get_recent_memory(
                    arguments['project_id'],
                    arguments.get('limit', 5)
                )
                
                if results:
                    text = f"Recent {len(results)} memory entries:\n\n"
                    for result in results:
                        text += f"**{result['timestamp']}"
                        if result['title']:
                            text += f" - {result['title']}"
                        if result['category']:
                            text += f" #{result['category']}"
                        text += f"**\n{result['content']}\n\n"
                else:
                    text = f"No recent memory found for project: {arguments['project_id']}"
                
                return self._success_response(text)

            elif tool_name == 'get_project_memory_stats':
                stats = self.memory_manager.get_memory_stats(arguments['project_id'])
                
                if stats['exists']:
                    text = f"Memory statistics for **{arguments['project_id']}**:\n\n"
                    text += f"- Total entries: {stats['total_entries']}\n"
                    text += f"- Total words: {stats['total_words']}\n"
                    text += f"- Total characters: {stats['total_characters']}\n"
                    if stats['categories']:
                        text += f"- Categories: {', '.join(stats['categories'])}\n"
                    if stats['latest_entry']:
                        text += f"- Latest entry: {stats['latest_entry']}\n"
                    if stats['oldest_entry']:
                        text += f"- Oldest entry: {stats['oldest_entry']}\n"
                else:
                    text = f"No memory found for project: {arguments['project_id']}"
                
                return self._success_response(text)

            elif tool_name == 'rag_query':
                try:
                    project_id = arguments['project_id']
                    question = arguments['question']
                    context_limit = arguments.get('context_limit', 5)
                    max_tokens = arguments.get('max_tokens', 2000)
                    
                    logger.info(f"RAG查詢: 專案={project_id}, 問題={question[:50]}...")
                    
                    # 執行 RAG 查詢
                    rag_result = self.memory_manager.rag_query(
                        project_id, question, context_limit, max_tokens
                    )
                    
                    if rag_result['status'] == 'no_context':
                        # 沒有找到相關內容
                        text = f"🤔 **無法回答問題**\n\n"
                        text += f"**問題**: {question}\n"
                        text += f"**專案**: {project_id}\n\n"
                        text += "❌ 沒有找到相關的專案記憶內容。\n\n"
                        text += "💡 **建議**:\n"
                        for suggestion in rag_result['suggestions']:
                            text += f"   • {suggestion}\n"
                        
                        return self._success_response(text)
                    
                    elif rag_result['status'] == 'success':
                        # 成功找到相關內容，構建回答
                        text = f"🧠 **RAG 智能問答**\n\n"
                        text += f"**問題**: {question}\n"
                        text += f"**專案**: {project_id}\n"
                        text += f"**使用記憶**: {rag_result['context_count']} 條 (~{rag_result['estimated_tokens']} tokens)\n\n"
                        
                        text += "---\n\n"
                        text += "**📝 給你的回答提示**:\n\n"
                        text += rag_result['prompt']
                        text += "\n\n---\n\n"
                        
                        text += "**📚 參考資料來源**:\n"
                        for i, source in enumerate(rag_result['context_sources'], 1):
                            text += f"\n**來源 {i}**: "
                            if source['title']:
                                text += f"{source['title']}"
                            if source['category']:
                                text += f" #{source['category']}"
                            if source['timestamp']:
                                text += f" ({source['timestamp'][:16]})"
                            text += f"\n`{source['content_preview']}`\n"
                        
                        text += f"\n💡 使用此資訊來回答用戶的問題「{question}」"
                        
                        return self._success_response(text)
                    
                    else:
                        return self._success_response("❌ RAG 查詢處理時發生錯誤")
                        
                except Exception as e:
                    logger.error(f"Error in rag_query: {e}")
                    return self._success_response("❌ RAG 查詢系統暫時無法使用")

            elif tool_name == 'summarize_project':
                try:
                    project_id = arguments['project_id']
                    summary_type = arguments.get('summary_type', 'brief')
                    max_entries = arguments.get('max_entries', 20)
                    
                    logger.info(f"生成專案摘要: 專案={project_id}, 類型={summary_type}")
                    
                    # 執行摘要生成
                    summary_result = self.memory_manager.summarize_project(
                        project_id, summary_type, max_entries
                    )
                    
                    if summary_result['status'] == 'not_found':
                        text = f"📊 **專案摘要**\n\n"
                        text += f"**專案**: {project_id}\n\n"
                        text += "❌ " + summary_result['message'] + "\n\n"
                        text += "💡 **建議**:\n"
                        for suggestion in summary_result['suggestions']:
                            text += f"   • {suggestion}\n"
                        
                        return self._success_response(text)
                    
                    elif summary_result['status'] == 'success':
                        text = f"📊 **專案摘要 - {summary_type.upper()} 模式**\n\n"
                        text += summary_result['summary']
                        
                        # 根據摘要類型添加額外資訊
                        if summary_type == 'brief' and 'key_metrics' in summary_result:
                            metrics = summary_result['key_metrics']
                            text += f"\n\n**📈 關鍵指標**:\n"
                            text += f"- 記憶條目: {metrics.get('total_entries', 0)}\n"
                            text += f"- 分類數量: {metrics.get('categories', 0)}\n"
                            text += f"- 最近活動: {metrics.get('recent_activity', 'Unknown')}\n"
                        
                        elif summary_type == 'detailed' and 'analysis' in summary_result:
                            analysis = summary_result['analysis']
                            text += f"\n\n💡 **深入分析可用**:\n"
                            text += f"   • 分類分佈: {len(analysis.get('category_distribution', {}))} 個分類\n"
                            text += f"   • 時間分佈: {len(analysis.get('timeline', {}))} 個月份\n"
                            text += f"   • 關鍵主題: {len(analysis.get('key_topics', []))} 個主題\n"
                        
                        elif summary_type == 'timeline' and 'timeline_data' in summary_result:
                            timeline = summary_result['timeline_data']
                            text += f"\n\n📅 **時間軸數據**: 涵蓋 {len(timeline)} 個月份的活動記錄\n"
                        
                        text += f"\n\n🎯 **下一步建議**:\n"
                        if summary_type == 'brief':
                            text += f"   • 使用 `summarize_project('{project_id}', 'detailed')` 獲取詳細分析\n"
                            text += f"   • 使用 `rag_query('{project_id}', '專案的核心功能是什麼？')` 深入了解\n"
                        elif summary_type == 'detailed':
                            text += f"   • 使用 `summarize_project('{project_id}', 'timeline')` 查看發展歷程\n"
                            text += f"   • 使用 `search_project_memory` 搜尋特定主題\n"
                        else:
                            text += f"   • 使用 `rag_query` 針對特定時期提問\n"
                            text += f"   • 使用 `search_project_memory` 搜尋具體內容\n"
                        
                        return self._success_response(text)
                    
                    else:
                        return self._success_response("❌ 專案摘要生成失敗: " + summary_result.get('message', '未知錯誤'))
                        
                except Exception as e:
                    logger.error(f"Error in summarize_project: {e}")
                    return self._success_response("❌ 專案摘要系統暫時無法使用")

            elif tool_name == 'delete_project_memory':
                success = self.memory_manager.delete_memory(arguments['project_id'])
                return self._success_response(
                    f"Memory {'deleted' if success else 'not found'} for project: {arguments['project_id']}"
                )

            elif tool_name == 'delete_project_memory_entry':
                result = self.memory_manager.delete_memory_entry(
                    arguments['project_id'],
                    arguments.get('entry_id'),
                    arguments.get('timestamp'),
                    arguments.get('title'),
                    arguments.get('category'),
                    arguments.get('content_match')
                )
                
                if result['success']:
                    text = result['message'] + f"\n\nDeleted entries:\n"
                    for entry in result['deleted_entries']:
                        text += f"- {entry['timestamp']}"
                        if entry['title']:
                            text += f" - {entry['title']}"
                        text += "\n"
                    text += f"\nRemaining entries: {result['remaining_count']}"
                else:
                    text = result['message']
                
                return self._success_response(text)

            elif tool_name == 'edit_project_memory_entry':
                result = self.memory_manager.edit_memory_entry(
                    arguments['project_id'],
                    arguments.get('entry_id'),
                    arguments.get('timestamp'),
                    arguments.get('new_title'),
                    arguments.get('new_category'),
                    arguments.get('new_content')
                )
                
                if result['success']:
                    text = result['message'] + f"\n\nEdited entry:\n"
                    entry = result['edited_entry']
                    text += f"- {entry['timestamp']}"
                    if entry['title']:
                        text += f" - {entry['title']}"
                    if entry['category']:
                        text += f" #{entry['category']}"
                else:
                    text = result['message']
                
                return self._success_response(text)

            elif tool_name == 'list_project_memory_entries':
                result = self.memory_manager.list_memory_entries(arguments['project_id'])
                
                if result['success']:
                    text = f"Memory entries for **{arguments['project_id']}** ({result['total_entries']} entries):\n\n"
                    for entry in result['entries']:
                        text += f"**{entry['id']}.** {entry['timestamp']}"
                        if entry['title']:
                            text += f" - {entry['title']}"
                        if entry['category']:
                            text += f" #{entry['category']}"
                        text += f"\n   {entry['content_preview']}\n\n"
                else:
                    text = result['message']
                
                return self._success_response(text)

            elif tool_name == 'rename_project':
                # 重新命名專案
                success = self.memory_manager.rename_project(
                    arguments['project_id'],
                    arguments['new_name']
                )
                
                if success:
                    return self._success_response(
                        f"✅ Project '{arguments['project_id']}' successfully renamed to '{arguments['new_name']}'"
                    )
                else:
                    return self._error_response(
                        -32603,
                        f"❌ Failed to rename project '{arguments['project_id']}' to '{arguments['new_name']}'. "
                        f"Check if the project exists."
                    )
            
            # ==================== INDEX TABLE TOOLS ====================
            elif tool_name == 'search_index':
                project_id = arguments.get('project_id')
                query = arguments.get('query')
                limit = arguments.get('limit', 10)
                
                if hasattr(self.memory_manager, 'search_index'):
                    results = self.memory_manager.search_index(project_id, query, limit)
                    
                    if not results:
                        return self._success_response(f"🔍 No results found for '{query}' in project '{project_id}'")
                    
                    response = f"🚀 **智能搜尋結果** (節省 70-85% token)\n\n"
                    response += f"**專案**: {project_id}\n**查詢**: {query}\n**找到**: {len(results)} 個結果\n\n"
                    
                    for i, result in enumerate(results, 1):
                        if result.get('match_type') == 'index':
                            response += f"**{i}. 📋 {result.get('title', 'Untitled')}** (索引匹配)\n"
                            response += f"   - **摘要**: {result.get('summary', '')}\n"
                            response += f"   - **關鍵字**: {result.get('keywords', '')}\n"
                            response += f"   - **階層**: Level {result.get('hierarchy_level', 0)}\n"
                            response += f"   - **類型**: {result.get('entry_type', 'discussion')}\n\n"
                        else:
                            response += f"**{i}. 📄 {result.get('title', 'Untitled')}** (內容匹配)\n"
                            response += f"   - **預覽**: {result.get('content_preview', '')}\n\n"
                    
                    response += f"💡 **提示**: 索引匹配結果已大幅減少 token 使用量！"
                    return self._success_response(response)
                else:
                    return self._error_response("❌ Index search not available (SQLite backend required)")
            
            elif tool_name == 'rebuild_index_for_project':
                project_id = arguments.get('project_id')
                
                if hasattr(self.memory_manager, 'rebuild_index_for_project'):
                    result = self.memory_manager.rebuild_index_for_project(project_id)
                    
                    if result.get('success'):
                        response = f"🔄 **索引重建完成**: {project_id}\n\n"
                        response += f"- **總條目數**: {result.get('total_entries', 0)}\n"
                        response += f"- **成功索引**: {result.get('indexed_entries', 0)}\n"
                        response += f"💡 現在可以使用 search_index 享受 70-85% token 節省效益！"
                        return self._success_response(response)
                    else:
                        return self._error_response(f"❌ 索引重建失敗: {result.get('message', 'Unknown error')}")
                else:
                    return self._error_response("❌ Index rebuild not available (SQLite backend required)")
            
            elif tool_name == 'get_index_stats':
                project_id = arguments.get('project_id')
                
                if hasattr(self.memory_manager, 'get_index_stats'):
                    stats = self.memory_manager.get_index_stats(project_id)
                    
                    if project_id:
                        response = f"📈 **專案索引統計**: {project_id}\n\n"
                        response += f"- **已索引條目**: {stats.get('total_indexed', 0)}\n"
                        response += f"- **條目類型數**: {stats.get('entry_types', 0)}\n"
                        response += f"- **最大階層級別**: {stats.get('max_hierarchy_level', 0)}\n"
                    else:
                        response = f"📈 **全局索引統計**\n\n"
                        response += f"- **已索引條目**: {stats.get('total_indexed', 0)}\n"
                        response += f"- **索引專案數**: {stats.get('indexed_projects', 0)}\n"
                    
                    return self._success_response(response)
                else:
                    return self._error_response("❌ Index stats not available (SQLite backend required)")
            
            elif tool_name == 'get_hierarchy_tree':
                project_id = arguments.get('project_id')
                
                if hasattr(self.memory_manager, 'get_hierarchy_tree'):
                    tree = self.memory_manager.get_hierarchy_tree(project_id)
                    
                    if tree.get('children'):
                        response = f"📊 **專案階層結構**: {project_id}\n\n"
                        for entry in tree['children']:
                            level_icon = ["📁", "📂", "📄"][min(entry.get('hierarchy_level', 0), 2)]
                            type_icon = {"feature": "🚀", "bug": "🐛", "milestone": "🎯", "discussion": "💬"}.get(entry.get('entry_type', 'discussion'), "💬")
                            response += f"{level_icon} {type_icon} **{entry.get('title', entry.get('summary', 'Untitled'))}**\n"
                        return self._success_response(response)
                    else:
                        return self._success_response(f"📊 專案 '{project_id}' 尚無索引條目，請先使用 rebuild_index_for_project 建立索引")
                else:
                    return self._error_response("❌ Hierarchy tree not available (SQLite backend required)")
            
            elif tool_name == 'update_index_entry':
                entry_id = arguments.get('entry_id')
                
                if hasattr(self.memory_manager, 'update_index_entry'):
                    update_fields = {}
                    for field in ['summary', 'keywords', 'hierarchy_level', 'entry_type', 'importance_level', 'parent_entry_id']:
                        if field in arguments and arguments[field] is not None:
                            update_fields[field] = arguments[field]
                    
                    if not update_fields:
                        return self._error_response("❌ 沒有提供要更新的欄位")
                    
                    success = self.memory_manager.update_index_entry(entry_id, **update_fields)
                    
                    if success:
                        response = f"✏️ **索引條目更新成功**: Entry ID {entry_id}\n\n"
                        for field, value in update_fields.items():
                            response += f"  - {field}: {value}\n"
                        return self._success_response(response)
                    else:
                        return self._error_response(f"❌ 更新索引條目失敗: Entry ID {entry_id}")
                else:
                    return self._error_response("❌ Index update not available (SQLite backend required)")

            elif tool_name == 'sync_markdown_to_sqlite':
                # 檢查當前後端是否為 SQLite
                if not isinstance(self.memory_manager, SQLiteBackend):
                    return self._error_response(-32603, "同步功能只能在 SQLite 後端模式下使用")
                
                try:
                    # 創建 Markdown 後端實例
                    markdown_backend = MarkdownMemoryManager()
                    
                    # 創建同步管理器
                    sync_manager = DataSyncManager(markdown_backend, self.memory_manager)
                    
                    # 執行同步
                    result = sync_manager.sync_all_projects(
                        mode=arguments.get('mode', 'auto'),
                        similarity_threshold=arguments.get('similarity_threshold', 0.8)
                    )
                    
                    # 格式化回應
                    if result['success']:
                        text = f"🔄 **Markdown → SQLite 同步完成**\n\n"
                        text += f"📊 **統計資訊**:\n"
                        text += f"- 總專案數: {result['total_projects']}\n"
                        text += f"- 已同步: {result['synced']} ✅\n"
                        text += f"- 跳過: {result['skipped']} ⏭️\n"
                        text += f"- 錯誤: {result['errors']} ❌\n\n"
                        
                        if result['log']:
                            text += f"📋 **詳細日誌**:\n"
                            for log_entry in result['log']:
                                status_icon = {
                                    'synced': '✅',
                                    'skipped': '⏭️', 
                                    'error': '❌',
                                    'preview': '👁️'
                                }.get(log_entry['action'], '❓')
                                
                                text += f"{status_icon} **{log_entry['project_id']}**: {log_entry['message']}\n"
                        
                        if result['synced'] > 0:
                            text += f"\n🎉 成功同步 {result['synced']} 個專案到 SQLite 後端！"
                        elif result['total_projects'] == 0:
                            text += f"\n💡 沒有找到 Markdown 專案需要同步。"
                        else:
                            text += f"\n⚠️ 所有專案都被跳過，可能已經存在於 SQLite 中。"
                    else:
                        text = f"❌ 同步失敗: {result.get('message', '未知錯誤')}"
                    
                    return self._success_response(text)
                    
                except Exception as e:
                    logger.error(f"Sync operation failed: {e}")
                    return self._error_response(-32603, f"同步過程中發生錯誤: {str(e)}")

            elif tool_name == 'export_project_memory':
                try:
                    project_id = arguments['project_id']
                    export_format = arguments.get('format', 'markdown')
                    output_path = arguments.get('output_path')
                    include_metadata = arguments.get('include_metadata', True)
                    
                    # 獲取專案記憶內容
                    memory_content = self.memory_manager.get_memory(project_id)
                    if not memory_content:
                        return self._error_response(-32603, f"No memory found for project: {project_id}")
                    
                    # 獲取專案統計資訊
                    stats = self.memory_manager.get_memory_stats(project_id)
                    
                    # 根據格式匯出
                    if export_format == 'markdown':
                        exported_content = self._export_to_markdown(project_id, memory_content, stats, include_metadata)
                    elif export_format == 'json':
                        exported_content = self._export_to_json(project_id, memory_content, stats, include_metadata)
                    elif export_format == 'csv':
                        exported_content = self._export_to_csv(project_id, memory_content, stats, include_metadata)
                    elif export_format == 'txt':
                        exported_content = self._export_to_txt(project_id, memory_content, stats, include_metadata)
                    else:
                        return self._error_response(-32603, f"Unsupported export format: {export_format}")
                    
                    # 如果指定了輸出路徑，寫入檔案
                    if output_path:
                        try:
                            output_file = Path(output_path)
                            output_file.parent.mkdir(parents=True, exist_ok=True)
                            
                            if export_format == 'json':
                                with open(output_file, 'w', encoding='utf-8') as f:
                                    json.dump(exported_content, f, ensure_ascii=False, indent=2)
                            else:
                                with open(output_file, 'w', encoding='utf-8') as f:
                                    f.write(exported_content)
                            
                            text = f"📤 **專案匯出完成 / Project Export Complete**\n\n"
                            text += f"- 專案 / Project: **{project_id}**\n"
                            text += f"- 格式 / Format: **{export_format.upper()}**\n"
                            text += f"- 輸出檔案 / Output File: `{output_file}`\n"
                            if stats['exists']:
                                text += f"- 條目數量 / Entries: {stats['total_entries']}\n"
                                text += f"- 總字數 / Words: {stats['total_words']}\n"
                            text += f"\n✅ 檔案已成功儲存！"
                            
                        except Exception as e:
                            return self._error_response(-32603, f"Failed to write export file: {str(e)}")
                    else:
                        # 直接返回內容
                        if export_format == 'json':
                            text = f"📤 **專案匯出 / Project Export** - {project_id} ({export_format.upper()})\n\n"
                            text += f"```json\n{json.dumps(exported_content, ensure_ascii=False, indent=2)}\n```"
                        else:
                            text = f"📤 **專案匯出 / Project Export** - {project_id} ({export_format.upper()})\n\n"
                            text += f"```{export_format}\n{exported_content}\n```"
                    
                    return self._success_response(text)
                    
                except Exception as e:
                    logger.error(f"Export operation failed: {e}")
                    return self._error_response(-32603, f"匯出過程中發生錯誤: {str(e)}")

            elif tool_name == 'save_global_memory':
                success = self.memory_manager.save_memory(
                    '__global__',
                    arguments['content'],
                    arguments.get('title', ''),
                    arguments.get('category', '')
                )
                return self._success_response(
                    f"Global memory {'saved' if success else 'failed to save'}: {arguments.get('title', 'Untitled')}"
                )

            elif tool_name == 'get_global_memory':
                memory = self.memory_manager.get_memory('__global__')
                return self._success_response(
                    memory or "No global memory found. Use save_global_memory to start building your knowledge base."
                )

            elif tool_name == 'search_global_memory':
                results = self.memory_manager.search_memory(
                    '__global__',
                    arguments['query'],
                    arguments.get('limit', 10)
                )
                
                if results:
                    text = f"Found {len(results)} global memory matches for \"{arguments['query']}\":\n\n"
                    for i, result in enumerate(results, 1):
                        text += f"**{i}. {result['timestamp']}"
                        if result['title']:
                            text += f" - {result['title']}"
                        if result['category']:
                            text += f" #{result['category']}"
                        text += f"**\n{result['content']}\n\n"
                else:
                    text = f"No global memory matches found for \"{arguments['query']}\""
                
                return self._success_response(text)

            elif tool_name == 'get_global_memory_stats':
                stats = self.memory_manager.get_memory_stats('__global__')
                
                if stats['exists']:
                    text = f"📊 **Global Memory Statistics**:\n\n"
                    text += f"- Total entries: {stats['total_entries']}\n"
                    text += f"- Total words: {stats['total_words']}\n"
                    text += f"- Total characters: {stats['total_characters']}\n"
                    if stats['categories']:
                        text += f"- Categories: {', '.join(stats['categories'])}\n"
                    if stats['latest_entry']:
                        text += f"- Latest entry: {stats['latest_entry']}\n"
                    if stats['oldest_entry']:
                        text += f"- Oldest entry: {stats['oldest_entry']}\n"
                    text += f"\n💡 Global memory contains cross-project knowledge and standards."
                else:
                    text = f"📝 **Global Memory is Empty**\n\nStart building your global knowledge base with save_global_memory!"
                
                return self._success_response(text)

            elif tool_name == 'get_backend_status':
                # 獲取當前後端類型
                backend_type = type(self.memory_manager).__name__
                backend_name = "SQLite" if "SQLite" in backend_type else "Markdown"
                
                # 獲取存儲路徑信息
                if hasattr(self.memory_manager, 'db_path'):
                    storage_path = str(self.memory_manager.db_path)
                    storage_type = "Database file"
                elif hasattr(self.memory_manager, 'memory_dir'):
                    storage_path = str(self.memory_manager.memory_dir)
                    storage_type = "Directory"
                else:
                    storage_path = "Unknown"
                    storage_type = "Unknown"
                
                # 獲取項目統計
                projects = self.memory_manager.list_projects()
                total_projects = len(projects)
                total_entries = sum(p['entries_count'] for p in projects)
                
                # 構建狀態信息
                text = f"🔧 **Backend Status / 後端狀態**\n\n"
                text += f"**Current Backend / 當前後端**: {backend_name}\n"
                text += f"**Backend Class / 後端類別**: `{backend_type}`\n"
                text += f"**Storage Type / 存儲類型**: {storage_type}\n"
                text += f"**Storage Path / 存儲路徑**: `{storage_path}`\n\n"
                text += f"📊 **Quick Stats / 快速統計**:\n"
                text += f"- Projects / 專案數: **{total_projects}**\n"
                text += f"- Total Entries / 總條目數: **{total_entries}**\n\n"
                
                # 添加後端特性說明
                if backend_name == "SQLite":
                    text += f"✅ **SQLite Features / SQLite 特性**:\n"
                    text += f"- 🔍 Full-text search / 全文搜尋\n"
                    text += f"- 🚀 High performance / 高效能\n"
                    text += f"- 🔒 ACID transactions / ACID 事務\n"
                    text += f"- 📊 Complex queries / 複雜查詢\n"
                else:
                    text += f"✅ **Markdown Features / Markdown 特性**:\n"
                    text += f"- 📝 Human-readable / 人類可讀\n"
                    text += f"- 🔄 Version control friendly / 版本控制友好\n"
                    text += f"- 📁 File-based storage / 檔案式存儲\n"
                    text += f"- 🔄 Easy backup / 容易備份\n"
                
                text += f"\n💡 Use `list_memory_projects` to see all projects"
                
                return self._success_response(text)

            elif tool_name == 'import_project_memory_universal':
                result = self.importer.import_universal(
                    arguments['file_path'],
                    arguments.get('project_id'),
                    arguments.get('merge_strategy', 'append')
                )
                
                if result['success']:
                    text = f"📥 **通用匯入成功 / Universal Import Successful**\n\n"
                    text += f"- 檔案路徑 / File Path: `{arguments['file_path']}`\n"
                    text += f"- 目標專案 / Target Project: **{result['project_id']}**\n"
                    text += f"- 匯入策略 / Merge Strategy: {arguments.get('merge_strategy', 'append')}\n"
                    text += f"- 成功匯入 / Imported: **{result['imported_count']}** 條目\n"
                    if result['skipped_count'] > 0:
                        text += f"- 跳過重複 / Skipped: **{result['skipped_count']}** 條目\n"
                    text += f"- 總條目數 / Total Entries: {result['total_entries']}\n\n"
                    text += f"✅ {result['message']}"
                else:
                    text = f"❌ **匯入失敗 / Import Failed**\n\n"
                    text += f"- 檔案路徑 / File Path: `{arguments['file_path']}`\n"
                    text += f"- 錯誤訊息 / Error: {result.get('error', 'Unknown error')}\n\n"
                    text += result.get('message', 'Import operation failed')
                
                return self._success_response(text)

            elif tool_name == 'import_project_memory_from_markdown':
                result = self.importer.import_from_markdown(
                    arguments['file_path'],
                    arguments.get('project_id'),
                    arguments.get('merge_strategy', 'append')
                )
                
                if result['success']:
                    text = f"📥 **Markdown 匯入成功 / Markdown Import Successful**\n\n"
                    text += f"- 檔案路徑 / File Path: `{arguments['file_path']}`\n"
                    text += f"- 目標專案 / Target Project: **{result['project_id']}**\n"
                    text += f"- 匯入策略 / Merge Strategy: {arguments.get('merge_strategy', 'append')}\n"
                    text += f"- 成功匯入 / Imported: **{result['imported_count']}** 條目\n"
                    if result['skipped_count'] > 0:
                        text += f"- 跳過重複 / Skipped: **{result['skipped_count']}** 條目\n"
                    text += f"- 總條目數 / Total Entries: {result['total_entries']}\n\n"
                    text += f"✅ {result['message']}"
                else:
                    text = f"❌ **Markdown 匯入失敗 / Markdown Import Failed**\n\n"
                    text += f"- 檔案路徑 / File Path: `{arguments['file_path']}`\n"
                    text += f"- 錯誤訊息 / Error: {result.get('error', 'Unknown error')}\n\n"
                    text += result.get('message', 'Import operation failed')
                
                return self._success_response(text)

            elif tool_name == 'import_project_memory_from_json':
                result = self.importer.import_from_json(
                    arguments['file_path'],
                    arguments.get('project_id'),
                    arguments.get('merge_strategy', 'append')
                )
                
                if result['success']:
                    text = f"📥 **JSON 匯入成功 / JSON Import Successful**\n\n"
                    text += f"- 檔案路徑 / File Path: `{arguments['file_path']}`\n"
                    text += f"- 目標專案 / Target Project: **{result['project_id']}**\n"
                    text += f"- 匯入策略 / Merge Strategy: {arguments.get('merge_strategy', 'append')}\n"
                    text += f"- 成功匯入 / Imported: **{result['imported_count']}** 條目\n"
                    if result['skipped_count'] > 0:
                        text += f"- 跳過重複 / Skipped: **{result['skipped_count']}** 條目\n"
                    text += f"- 總條目數 / Total Entries: {result['total_entries']}\n\n"
                    text += f"✅ {result['message']}"
                else:
                    text = f"❌ **JSON 匯入失敗 / JSON Import Failed**\n\n"
                    text += f"- 檔案路徑 / File Path: `{arguments['file_path']}`\n"
                    text += f"- 錯誤訊息 / Error: {result.get('error', 'Unknown error')}\n\n"
                    text += result.get('message', 'Import operation failed')
                
                return self._success_response(text)

            elif tool_name == 'import_project_memory_from_csv':
                result = self.importer.import_from_csv(
                    arguments['file_path'],
                    arguments.get('project_id'),
                    arguments.get('merge_strategy', 'append')
                )
                
                if result['success']:
                    text = f"📥 **CSV 匯入成功 / CSV Import Successful**\n\n"
                    text += f"- 檔案路徑 / File Path: `{arguments['file_path']}`\n"
                    text += f"- 目標專案 / Target Project: **{result['project_id']}**\n"
                    text += f"- 匯入策略 / Merge Strategy: {arguments.get('merge_strategy', 'append')}\n"
                    text += f"- 成功匯入 / Imported: **{result['imported_count']}** 條目\n"
                    if result['skipped_count'] > 0:
                        text += f"- 跳過重複 / Skipped: **{result['skipped_count']}** 條目\n"
                    text += f"- 總條目數 / Total Entries: {result['total_entries']}\n\n"
                    text += f"✅ {result['message']}"
                else:
                    text = f"❌ **CSV 匯入失敗 / CSV Import Failed**\n\n"
                    text += f"- 檔案路徑 / File Path: `{arguments['file_path']}`\n"
                    text += f"- 錯誤訊息 / Error: {result.get('error', 'Unknown error')}\n\n"
                    text += result.get('message', 'Import operation failed')
                
                return self._success_response(text)

            elif tool_name == 'import_project_memory_from_txt':
                result = self.importer.import_from_markdown(  # TXT 當作 Markdown 處理
                    arguments['file_path'],
                    arguments.get('project_id'),
                    arguments.get('merge_strategy', 'append')
                )
                
                if result['success']:
                    text = f"📥 **TXT 匯入成功 / TXT Import Successful**\n\n"
                    text += f"- 檔案路徑 / File Path: `{arguments['file_path']}`\n"
                    text += f"- 目標專案 / Target Project: **{result['project_id']}**\n"
                    text += f"- 匯入策略 / Merge Strategy: {arguments.get('merge_strategy', 'append')}\n"
                    text += f"- 成功匯入 / Imported: **{result['imported_count']}** 條目\n"
                    if result['skipped_count'] > 0:
                        text += f"- 跳過重複 / Skipped: **{result['skipped_count']}** 條目\n"
                    text += f"- 總條目數 / Total Entries: {result['total_entries']}\n\n"
                    text += f"✅ {result['message']}"
                else:
                    text = f"❌ **TXT 匯入失敗 / TXT Import Failed**\n\n"
                    text += f"- 檔案路徑 / File Path: `{arguments['file_path']}`\n"
                    text += f"- 錯誤訊息 / Error: {result.get('error', 'Unknown error')}\n\n"
                    text += result.get('message', 'Import operation failed')
                
                return self._success_response(text)

            else:
                return self._error_response(-32601, f"Unknown tool: {tool_name}")

        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            return self._error_response(-32603, str(e))

    def _success_response(self, text: str) -> Dict[str, Any]:
        """建立成功回應"""
        return {
            'jsonrpc': '2.0',
            'result': {
                'content': [{
                    'type': 'text',
                    'text': text
                }]
            }
        }

    def _error_response(self, code: int, message: str) -> Dict[str, Any]:
        """建立錯誤回應"""
        return {
            'jsonrpc': '2.0',
            'error': {
                'code': code,
                'message': message
            }
        }

    def _export_to_markdown(self, project_id: str, memory_content: str, stats: Dict, include_metadata: bool) -> str:
        """匯出為 Markdown 格式"""
        content = f"# {project_id}\n\n"
        
        if include_metadata and stats['exists']:
            content += f"## 專案資訊 / Project Information\n\n"
            content += f"- **專案名稱 / Project Name:** {project_id}\n"
            content += f"- **條目數量 / Total Entries:** {stats['total_entries']}\n"
            content += f"- **總字數 / Total Words:** {stats['total_words']}\n"
            content += f"- **總字符數 / Total Characters:** {stats['total_characters']}\n"
            if stats['categories']:
                content += f"- **分類 / Categories:** {', '.join(stats['categories'])}\n"
            if stats['latest_entry']:
                content += f"- **最新條目 / Latest Entry:** {stats['latest_entry']}\n"
            if stats['oldest_entry']:
                content += f"- **最舊條目 / Oldest Entry:** {stats['oldest_entry']}\n"
            content += f"- **匯出時間 / Export Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            content += "---\n\n"
        
        content += f"## 記憶內容 / Memory Content\n\n"
        content += memory_content
        
        return content

    def _export_to_json(self, project_id: str, memory_content: str, stats: Dict, include_metadata: bool) -> Dict:
        """匯出為 JSON 格式"""
        export_data = {
            'project_id': project_id,
            'content': memory_content,
            'export_time': datetime.now().isoformat()
        }
        
        if include_metadata and stats['exists']:
            export_data['metadata'] = {
                'total_entries': stats['total_entries'],
                'total_words': stats['total_words'],
                'total_characters': stats['total_characters'],
                'categories': stats['categories'],
                'latest_entry': stats['latest_entry'],
                'oldest_entry': stats['oldest_entry']
            }
        
        return export_data

    def _export_to_csv(self, project_id: str, memory_content: str, stats: Dict, include_metadata: bool) -> str:
        """匯出為 CSV 格式（簡化版本，主要用於條目列表）"""
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # CSV 標題
        if include_metadata:
            writer.writerow(['Timestamp', 'Title', 'Category', 'Content'])
        else:
            writer.writerow(['Content'])
        
        # 嘗試解析記憶內容中的條目
        lines = memory_content.split('\n')
        current_entry = {'timestamp': '', 'title': '', 'category': '', 'content': ''}
        
        for line in lines:
            line = line.strip()
            if line.startswith('**') and line.endswith('**'):
                # 可能是時間戳記行
                if current_entry['content']:
                    # 寫入前一個條目
                    if include_metadata:
                        writer.writerow([current_entry['timestamp'], current_entry['title'], 
                                       current_entry['category'], current_entry['content'].strip()])
                    else:
                        writer.writerow([current_entry['content'].strip()])
                    current_entry = {'timestamp': '', 'title': '', 'category': '', 'content': ''}
                
                # 解析新條目的標題行
                header = line[2:-2]  # 移除 **
                if ' - ' in header:
                    parts = header.split(' - ', 1)
                    current_entry['timestamp'] = parts[0]
                    title_and_category = parts[1]
                    if ' #' in title_and_category:
                        title_parts = title_and_category.split(' #')
                        current_entry['title'] = title_parts[0]
                        current_entry['category'] = title_parts[1] if len(title_parts) > 1 else ''
                    else:
                        current_entry['title'] = title_and_category
                else:
                    current_entry['timestamp'] = header
            else:
                if line:
                    current_entry['content'] += line + '\n'
        
        # 寫入最後一個條目
        if current_entry['content']:
            if include_metadata:
                writer.writerow([current_entry['timestamp'], current_entry['title'], 
                               current_entry['category'], current_entry['content'].strip()])
            else:
                writer.writerow([current_entry['content'].strip()])
        
        return output.getvalue()

    def _export_to_txt(self, project_id: str, memory_content: str, stats: Dict, include_metadata: bool) -> str:
        """匯出為純文字格式"""
        content = f"專案: {project_id}\n"
        content += "=" * 50 + "\n\n"
        
        if include_metadata and stats['exists']:
            content += f"專案資訊:\n"
            content += f"- 條目數量: {stats['total_entries']}\n"
            content += f"- 總字數: {stats['total_words']}\n"
            content += f"- 總字符數: {stats['total_characters']}\n"
            if stats['categories']:
                content += f"- 分類: {', '.join(stats['categories'])}\n"
            if stats['latest_entry']:
                content += f"- 最新條目: {stats['latest_entry']}\n"
            if stats['oldest_entry']:
                content += f"- 最舊條目: {stats['oldest_entry']}\n"
            content += f"- 匯出時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            content += "-" * 50 + "\n\n"
        
        content += "記憶內容:\n\n"
        # 移除 Markdown 格式標記
        clean_content = memory_content.replace('**', '').replace('*', '').replace('#', '')
        content += clean_content
        
        return content

    async def run(self):
        """運行 MCP 伺服器"""
        logger.info(f"Starting Memory MCP Server v{self.version}")
        
        try:
            while True:
                # 從 stdin 讀取訊息
                try:
                    line = await asyncio.get_event_loop().run_in_executor(
                        None, sys.stdin.readline
                    )
                except EOFError:
                    break
                
                if not line:
                    break
                
                try:
                    message = json.loads(line.strip())
                    logger.info(f"[MCP] Received message: {message.get('method', 'unknown')}, full message: {message}")
                    logger.debug(f"Received message: {message.get('method', 'unknown')}")
                    
                    try:
                        response = await self.handle_message(message)
                        logger.info(f"[MCP] handle_message completed for {message.get('method')}")
                        
                        # 只有非通知消息才需要回應
                        if response is not None:
                            # 設定 response ID
                            if 'id' in message:
                                response['id'] = message['id']
                            
                            # 將回應寫入 stdout (使用 UTF-8 編碼)
                            try:
                                logger.info(f"[MCP] About to serialize response for {message.get('method')}")
                                output = json.dumps(response, ensure_ascii=False)
                                logger.info(f"[MCP] JSON serialization successful, sending response")
                                print(output)
                                sys.stdout.flush()
                                logger.info(f"[MCP] Response sent successfully for {message.get('method')}")
                            except Exception as json_error:
                                logger.error(f"JSON serialization error: {json_error}")
                                # 發送錯誤回應而不是降級到 ASCII
                                if 'id' in message:
                                    error_response = {
                                        'jsonrpc': '2.0',
                                        'id': message['id'],
                                        'error': {
                                            'code': -32603,
                                            'message': 'JSON serialization error',
                                            'data': str(json_error)
                                        }
                                    }
                                    try:
                                        print(json.dumps(error_response, ensure_ascii=False))
                                        sys.stdout.flush()
                                    except Exception as error_json_error:
                                        logger.error(f"Failed to send error response: {error_json_error}")
                                continue
                    
                    except Exception as handle_error:
                        logger.error(f"Error handling message: {handle_error}")
                        # 發送錯誤回應
                        if 'id' in message:
                            error_response = {
                                'jsonrpc': '2.0',
                                'id': message['id'],
                                'error': {
                                    'code': -32603,
                                    'message': 'Internal error',
                                    'data': str(handle_error)
                                }
                            }
                            try:
                                print(json.dumps(error_response, ensure_ascii=False))
                                sys.stdout.flush()
                            except Exception as error_json_error:
                                logger.error(f"Failed to send error response: {error_json_error}")
                        continue
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
                    continue
                    
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            logger.info("Server shutdown complete")

def create_backend(backend_type: str, db_path: str = None) -> MemoryBackend:
    """根據類型創建記憶後端"""
    if backend_type == "markdown":
        return MarkdownMemoryManager()
    elif backend_type == "sqlite":
        if not db_path or not str(db_path).strip():
            raise ValueError("SQLite backend requires --db-path to be provided. Example: --db-path=~/.mcp/ai-memory/memory.db")
        # 展開 ~ 家目錄符號
        expanded_path = os.path.expanduser(db_path)
        return SQLiteBackend(expanded_path)
    else:
        raise ValueError(f"Unknown backend type: {backend_type}")

def main():
    """主程式入口點"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Markdown Memory MCP Server")
    parser.add_argument(
        "--backend", 
        choices=["markdown", "sqlite"], 
        default="sqlite",
        help="選擇記憶後端類型 (default: markdown)"
    )
    parser.add_argument(
        "--info", 
        action="store_true",
        help="顯示當前配置資訊"
    )
    parser.add_argument(
        "--sync-from-markdown",
        action="store_true",
        help="將 Markdown 專案同步到 SQLite 後端"
    )
    parser.add_argument(
        "--sync-mode",
        choices=["auto", "interactive", "preview"],
        default="auto",
        help="同步模式: auto(自動), interactive(互動), preview(預覽)"
    )
    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.8,
        help="相似度閾值 (0.0-1.0)，用於決定是否自動合併"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        help="[必填於 sqlite 模式] SQLite 資料庫路徑，支援 ~。例如: ~/.mcp/ai-memory/memory.db"
    )
    
    args = parser.parse_args()
    
    if args.info:
        print(f"Markdown Memory MCP Server")
        print(f"Backend: {args.backend}")
        print(f"Python version: {sys.version}")
        print(f"Working directory: {os.getcwd()}")
        print(f"Script path: {__file__}")
        
        # 顯示後端特定資訊（不初始化）
        if args.backend == "sqlite":
            if not args.db_path:
                print("Error: --db-path is required for sqlite backend.")
                print("Example: --db-path=~/.mcp/ai-memory/memory.db")
                return
            db_path = Path(os.path.expanduser(args.db_path)).resolve()
            print(f"SQLite database: {db_path}")
            print(f"Database exists: {db_path.exists()}")
        elif args.backend == "markdown":
            memory_dir = Path(__file__).parent.resolve() / "ai-memory"
            print(f"Memory directory: {memory_dir}")
            print(f"Directory exists: {memory_dir.exists()}")
            
        return
    
    # 處理同步功能
    if args.sync_from_markdown:
        if args.backend != "sqlite":
            print("錯誤: 同步功能只能在 SQLite 後端模式下使用")
            print("請使用: python memory_mcp_server_dev.py --backend=sqlite --sync-from-markdown")
            sys.exit(1)
        
        try:
            # 創建兩個後端實例
            markdown_backend = MarkdownMemoryManager()
            sqlite_backend = SQLiteBackend()
            
            # 創建同步管理器
            sync_manager = DataSyncManager(markdown_backend, sqlite_backend)
            
            print(f"開始同步 Markdown 專案到 SQLite...")
            print(f"同步模式: {args.sync_mode}")
            print(f"相似度閾值: {args.similarity_threshold}")
            print("-" * 50)
            
            # 執行同步
            result = sync_manager.sync_all_projects(
                mode=args.sync_mode,
                similarity_threshold=args.similarity_threshold
            )
            
            # 顯示結果
            print(f"\n同步完成!")
            print(f"總專案數: {result['total_projects']}")
            print(f"已同步: {result['synced']}")
            print(f"跳過: {result['skipped']}")
            print(f"錯誤: {result['errors']}")
            
            if result['log']:
                print("\n詳細日誌:")
                for log_entry in result['log']:
                    status_icon = {
                        'synced': '✅',
                        'skipped': '⏭️',
                        'error': '❌',
                        'preview': '👁️'
                    }.get(log_entry['action'], '❓')
                    
                    print(f"{status_icon} {log_entry['project_id']}: {log_entry['message']}")
            
            print(f"\n同步操作完成!")
            
        except Exception as e:
            print(f"同步過程中發生錯誤: {e}")
            logger.error(f"Sync error: {e}")
            sys.exit(1)
        
        return
    
    # 創建後端（只有實際運行時才初始化）
    try:
        if args.backend == "sqlite" and not args.db_path:
            logger.error("--db-path is required when using sqlite backend. Example: --db-path=~/.mcp/ai-memory/memory.db")
            sys.exit(1)
        backend = create_backend(args.backend, args.db_path)
        if args.backend == "sqlite":
            logger.info(f"Using sqlite backend with db path: {args.db_path}")
        else:
            logger.info(f"Using {args.backend} backend")
    except Exception as e:
        logger.error(f"Failed to create backend: {e}")
        sys.exit(1)
    
    # 確保輸出是 UTF-8
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    
    # 添加調試資訊
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"Script path: {__file__}")
    
    server = MCPServer(backend)
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("Server interrupted")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
