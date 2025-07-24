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
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from abc import ABC, abstractmethod
from contextlib import contextmanager
import difflib
import re
import time

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

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FileLock:
    """跨平台檔案鎖定工具類"""
    
    def __init__(self, file_path: Path, timeout: float = 30.0, retry_delay: float = 0.1):
        self.file_path = file_path
        self.timeout = timeout
        self.retry_delay = retry_delay
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
            
        except Exception as e:
            logger.warning(f"Error releasing lock for {self.file_path}: {e}")
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
            except Exception as e:
                logger.error(f"Failed to complete atomic write for {self.file_path}: {e}")
                # 清理臨時檔案
                try:
                    self.temp_path.unlink()
                except FileNotFoundError:
                    pass
                raise
        else:
            # 失敗：清理臨時檔案
            try:
                self.temp_path.unlink()
            except FileNotFoundError:
                pass


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
        # 清理專案 ID，移除不安全字符
        clean_id = "".join(c for c in project_id if c.isalnum() or c in ('-', '_'))
        return self.memory_dir / f"{clean_id}.md"

    def get_memory(self, project_id: str) -> Optional[str]:
        """讀取完整專案記憶"""
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
        except Exception as e:
            logger.error(f"Error saving memory for {project_id}: {e}")
            return False

    def search_memory(self, project_id: str, query: str, limit: int = 10) -> List[Dict[str, str]]:
        """搜尋記憶內容"""
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

    def rename_project(self, old_project_id: str, new_project_id: str) -> bool:
        """重新命名專案（移動檔案並更新標題）"""
        try:
            old_file = self.get_memory_file(old_project_id)
            new_file = self.get_memory_file(new_project_id)
            
            # 檢查舊檔案是否存在
            if not old_file.exists():
                logger.error(f"Project {old_project_id} does not exist")
                return False
            
            # 檢查新檔案是否已存在
            if new_file.exists():
                logger.error(f"Project {new_project_id} already exists")
                return False
            
            # 使用檔案鎖定進行安全重命名
            with FileLock(old_file):
                # 讀取原始內容
                content = old_file.read_text(encoding='utf-8')
                
                # 更新檔案標題
                lines = content.split('\n')
                if lines and lines[0].startswith('# AI Memory for '):
                    lines[0] = f"# AI Memory for {new_project_id}"
                
                updated_content = '\n'.join(lines)
                
                # 寫入新檔案
                with AtomicFileWriter(new_file) as f:
                    f.write(updated_content)
                
                # 刪除舊檔案
                old_file.unlink()
                
                logger.info(f"Project renamed from {old_project_id} to {new_project_id}")
                return True
                
        except TimeoutError as e:
            logger.error(f"Timeout acquiring lock for renaming {old_project_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error renaming project from {old_project_id} to {new_project_id}: {e}")
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
    
    def __init__(self, db_path: str = "ai-memory/memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    @contextmanager
    def get_connection(self):
        """取得資料庫連接"""
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
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
            # 建立專案表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 建立記憶條目表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    title TEXT,
                    category TEXT,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                )
            """)
            
            # 建立索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_project ON memory_entries(project_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_category ON memory_entries(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_created ON memory_entries(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_updated ON memory_entries(updated_at)")
            
            # 建立全文搜尋表
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    content,
                    title,
                    category,
                    content='memory_entries',
                    content_rowid='id'
                )
            """)
            
            # 建立觸發器維護全文搜尋索引
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS memory_fts_insert AFTER INSERT ON memory_entries BEGIN
                    INSERT INTO memory_fts(rowid, content, title, category) 
                    VALUES (new.id, new.content, COALESCE(new.title, ''), COALESCE(new.category, ''));
                END
            """)
            
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS memory_fts_delete AFTER DELETE ON memory_entries BEGIN
                    DELETE FROM memory_fts WHERE rowid = old.id;
                END
            """)
            
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS memory_fts_update AFTER UPDATE ON memory_entries BEGIN
                    DELETE FROM memory_fts WHERE rowid = old.id;
                    INSERT INTO memory_fts(rowid, content, title, category) 
                    VALUES (new.id, new.content, COALESCE(new.title, ''), COALESCE(new.category, ''));
                END
            """)
            
            conn.commit()
            logger.info(f"SQLite database initialized at: {self.db_path}")
    
    def save_memory(self, project_id: str, content: str, title: str = "", category: str = "") -> bool:
        """儲存記憶到 SQLite 資料庫"""
        try:
            with self.get_connection() as conn:
                # 確保專案存在
                conn.execute("""
                    INSERT OR IGNORE INTO projects (id, name) 
                    VALUES (?, ?)
                """, (project_id, project_id.replace('-', ' ').title()))
                
                # 插入記憶條目
                conn.execute("""
                    INSERT INTO memory_entries (project_id, title, category, content)
                    VALUES (?, ?, ?, ?)
                """, (project_id, title or None, category or None, content))
                
                # 更新專案的 updated_at
                conn.execute("""
                    UPDATE projects SET updated_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                """, (project_id,))
                
                conn.commit()
                logger.info(f"Memory saved for project: {project_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error saving memory for {project_id}: {e}")
            return False
    
    def get_memory(self, project_id: str) -> Optional[str]:
        """讀取完整專案記憶，轉換為 Markdown 格式"""
        try:
            with self.get_connection() as conn:
                # 取得所有記憶條目
                cursor = conn.execute("""
                    SELECT title, category, content, created_at
                    FROM memory_entries 
                    WHERE project_id = ?
                    ORDER BY created_at ASC
                """, (project_id,))
                
                entries = cursor.fetchall()
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
                    entry_md = "".join(header_parts) + f"\n\n{entry['content']}\n\n---\n\n"
                    markdown_parts.append(entry_md)
                
                return "".join(markdown_parts)
                
        except Exception as e:
            logger.error(f"Error reading memory for {project_id}: {e}")
            return None
    
    def search_memory(self, project_id: str, query: str, limit: int = 10) -> List[Dict[str, str]]:
        """使用 FTS5 搜尋記憶內容，如果失敗則使用 LIKE 備用搜尋"""
        try:
            # 首先嘗試 FTS5 全文搜尋
            fts_results = self._fts_search(project_id, query, limit)
            
            # 如果 FTS5 搜尋結果為空，使用 LIKE 備用搜尋
            if not fts_results:
                logger.info(f"FTS5 search returned no results for '{query}', trying LIKE search")
                like_results = self._like_search(project_id, query, limit)
                if like_results:
                    logger.info(f"LIKE search found {len(like_results)} results for '{query}'")
                return like_results
            
            return fts_results
                
        except Exception as e:
            logger.error(f"Error searching memory for {project_id}: {e}")
            # 如果 FTS5 搜尋出現異常，嘗試 LIKE 備用搜尋
            try:
                logger.info(f"FTS5 search failed, trying LIKE search as fallback")
                return self._like_search(project_id, query, limit)
            except Exception as fallback_error:
                logger.error(f"Fallback LIKE search also failed: {fallback_error}")
                return []
    
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
        """列出所有專案及其統計資訊（排除全局記憶）"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT p.id, p.name, p.created_at, p.updated_at,
                           COUNT(me.id) as entries_count,
                           GROUP_CONCAT(DISTINCT me.category) as categories
                    FROM projects p
                    LEFT JOIN memory_entries me ON p.id = me.project_id
                    WHERE p.id != '__global__'
                    GROUP BY p.id, p.name, p.created_at, p.updated_at
                    ORDER BY p.updated_at DESC
                """)
                
                projects = []
                for row in cursor.fetchall():
                    # 處理分類
                    categories = []
                    if row['categories']:
                        categories = [cat.strip() for cat in row['categories'].split(',') if cat.strip()]
                    
                    # 格式化時間
                    updated_at = row['updated_at']
                    if isinstance(updated_at, str):
                        try:
                            dt = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                            formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except:
                            formatted_time = updated_at
                    else:
                        formatted_time = str(updated_at)
                    
                    projects.append({
                        'id': row['id'],
                        'name': row['name'],
                        'file_path': f"SQLite: {self.db_path}",
                        'entries_count': row['entries_count'],
                        'last_modified': formatted_time,
                        'categories': categories
                    })
                
                return projects
                
        except Exception as e:
            logger.error(f"Error listing projects: {e}")
            return []
    
    def get_recent_memory(self, project_id: str, limit: int = 5) -> List[Dict[str, str]]:
        """取得最近的記憶條目"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT title, category, content, created_at
                    FROM memory_entries 
                    WHERE project_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (project_id, limit))
                
                results = []
                for row in cursor.fetchall():
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
                    
                    results.append({
                        'timestamp': formatted_time,
                        'title': row['title'] or '',
                        'category': row['category'] or '',
                        'content': row['content']
                    })
                
                return list(reversed(results))  # 返回時間順序（舊到新）
                
        except Exception as e:
            logger.error(f"Error getting recent memory for {project_id}: {e}")
            return []
    
    def delete_memory(self, project_id: str) -> bool:
        """刪除專案記憶"""
        try:
            with self.get_connection() as conn:
                # 刪除記憶條目（觸發器會自動清理 FTS）
                cursor = conn.execute("DELETE FROM memory_entries WHERE project_id = ?", (project_id,))
                deleted_entries = cursor.rowcount
                
                # 刪除專案
                cursor = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
                deleted_project = cursor.rowcount
                
                conn.commit()
                
                if deleted_entries > 0 or deleted_project > 0:
                    logger.info(f"Memory deleted for project: {project_id}")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Error deleting memory for {project_id}: {e}")
            return False
    
    def delete_memory_entry(self, project_id: str, entry_id: str = None, timestamp: str = None, 
                           title: str = None, category: str = None, content_match: str = None) -> Dict[str, Any]:
        """刪除特定的記憶條目"""
        try:
            with self.get_connection() as conn:
                # 建立查詢條件
                where_conditions = ["project_id = ?"]
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
                
                if title:
                    where_conditions.append("title LIKE ?")
                    params.append(f"%{title}%")
                
                if category:
                    where_conditions.append("category LIKE ?")
                    params.append(f"%{category}%")
                
                if content_match:
                    where_conditions.append("content LIKE ?")
                    params.append(f"%{content_match}%")
                
                # 先查詢要刪除的條目
                select_sql = f"""
                    SELECT id, title, created_at FROM memory_entries 
                    WHERE {' AND '.join(where_conditions)}
                """
                cursor = conn.execute(select_sql, params)
                entries_to_delete = cursor.fetchall()
                
                if not entries_to_delete:
                    return {'success': False, 'message': 'No matching entries found to delete'}
                
                # 執行刪除
                delete_sql = f"DELETE FROM memory_entries WHERE {' AND '.join(where_conditions)}"
                cursor = conn.execute(delete_sql, params)
                deleted_count = cursor.rowcount
                
                conn.commit()
                
                # 格式化回應
                deleted_entries = []
                for entry in entries_to_delete:
                    timestamp = entry['created_at']
                    if isinstance(timestamp, str):
                        try:
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
                
                return {
                    'success': True,
                    'message': f"Deleted {deleted_count} entries from project {project_id}",
                    'deleted_count': deleted_count,
                    'remaining_count': self._count_entries(conn, project_id),
                    'deleted_entries': deleted_entries
                }
                
        except Exception as e:
            logger.error(f"Error deleting memory entry for {project_id}: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    def edit_memory_entry(self, project_id: str, entry_id: str = None, timestamp: str = None,
                         new_title: str = None, new_category: str = None, new_content: str = None) -> Dict[str, Any]:
        """編輯特定的記憶條目"""
        try:
            with self.get_connection() as conn:
                # 建立查詢條件
                where_conditions = ["project_id = ?"]
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
                
                # 建立更新語句
                update_fields = []
                update_params = []
                
                if new_title is not None:
                    update_fields.append("title = ?")
                    update_params.append(new_title or None)
                
                if new_category is not None:
                    update_fields.append("category = ?")
                    update_params.append(new_category or None)
                
                if new_content is not None:
                    update_fields.append("content = ?")
                    update_params.append(new_content)
                
                if not update_fields:
                    return {'success': False, 'message': 'No fields to update'}
                
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                
                # 執行更新
                update_sql = f"""
                    UPDATE memory_entries 
                    SET {', '.join(update_fields)}
                    WHERE {' AND '.join(where_conditions)}
                """
                update_params.extend(params)
                conn.execute(update_sql, update_params)
                conn.commit()
                
                # 取得更新後的條目
                cursor = conn.execute(select_sql, params)
                updated_entry = cursor.fetchone()
                
                # 格式化時間戳
                timestamp = updated_entry['created_at']
                if isinstance(timestamp, str):
                    try:
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
        """列出專案中的所有記憶條目，帶有索引"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, title, category, content, created_at
                    FROM memory_entries 
                    WHERE project_id = ?
                    ORDER BY created_at ASC
                """, (project_id,))
                
                entries = []
                for row in cursor.fetchall():
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
                    
                    content = row['content']
                    entries.append({
                        'id': row['id'],
                        'timestamp': formatted_time,
                        'title': row['title'] or '',
                        'category': row['category'] or '',
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
        """取得記憶統計資訊"""
        try:
            with self.get_connection() as conn:
                # 檢查專案是否存在
                cursor = conn.execute("SELECT COUNT(*) FROM projects WHERE id = ?", (project_id,))
                if cursor.fetchone()[0] == 0:
                    return {'exists': False}
                
                # 取得統計資訊
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_entries,
                        SUM(LENGTH(content)) as total_characters,
                        MIN(created_at) as oldest_entry,
                        MAX(created_at) as latest_entry,
                        GROUP_CONCAT(DISTINCT category) as categories
                    FROM memory_entries 
                    WHERE project_id = ?
                """, (project_id,))
                
                stats = cursor.fetchone()
                
                # 處理分類
                categories = []
                if stats['categories']:
                    categories = [cat.strip() for cat in stats['categories'].split(',') if cat.strip()]
                
                # 格式化時間
                def format_timestamp(ts):
                    if not ts:
                        return None
                    if isinstance(ts, str):
                        try:
                            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                            return dt.strftime("%Y-%m-%d %H:%M:%S")
                        except:
                            return ts
                    return str(ts)
                
                # 計算字數（簡單估算）
                total_words = (stats['total_characters'] or 0) // 5
                
                return {
                    'exists': True,
                    'total_entries': stats['total_entries'],
                    'total_words': total_words,
                    'total_characters': stats['total_characters'] or 0,
                    'categories': categories,
                    'latest_entry': format_timestamp(stats['latest_entry']),
                    'oldest_entry': format_timestamp(stats['oldest_entry'])
                }
                
        except Exception as e:
            logger.error(f"Error getting memory stats for {project_id}: {e}")
            return {'exists': False, 'error': str(e)}

    def rename_project(self, old_project_id: str, new_project_id: str) -> bool:
        """重新命名專案（更新資料庫中的專案 ID）"""
        try:
            with self.get_connection() as conn:
                # 檢查舊專案是否存在
                cursor = conn.execute("SELECT COUNT(*) FROM projects WHERE id = ?", (old_project_id,))
                if cursor.fetchone()[0] == 0:
                    logger.error(f"Project {old_project_id} does not exist")
                    return False
                
                # 檢查新專案 ID 是否已存在
                cursor = conn.execute("SELECT COUNT(*) FROM projects WHERE id = ?", (new_project_id,))
                if cursor.fetchone()[0] > 0:
                    logger.error(f"Project {new_project_id} already exists")
                    return False
                
                # 開始事務
                conn.execute("BEGIN TRANSACTION")
                
                try:
                    # 先更新記憶條目表（子表）
                    conn.execute("""
                        UPDATE memory_entries 
                        SET project_id = ? 
                        WHERE project_id = ?
                    """, (new_project_id, old_project_id))
                    
                    # 再更新專案表（父表）- 使用 INSERT + DELETE 方式避免外鍵約束
                    # 先獲取原專案資料
                    cursor = conn.execute("""
                        SELECT name, created_at FROM projects WHERE id = ?
                    """, (old_project_id,))
                    project_data = cursor.fetchone()
                    
                    if project_data:
                        # 插入新專案記錄
                        conn.execute("""
                            INSERT INTO projects (id, name, created_at, updated_at)
                            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                        """, (new_project_id, project_data[0], project_data[1]))
                        
                        # 刪除舊專案記錄
                        conn.execute("DELETE FROM projects WHERE id = ?", (old_project_id,))
                    
                    # 提交事務
                    conn.execute("COMMIT")
                    
                    logger.info(f"Project renamed from {old_project_id} to {new_project_id}")
                    return True
                    
                except Exception as e:
                    # 回滾事務
                    conn.execute("ROLLBACK")
                    logger.error(f"Error during rename transaction: {e}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error renaming project from {old_project_id} to {new_project_id}: {e}")
            return False
    
    def _count_entries(self, conn, project_id: str) -> int:
        """計算專案的記憶條目數量"""
        cursor = conn.execute("SELECT COUNT(*) FROM memory_entries WHERE project_id = ?", (project_id,))
        return cursor.fetchone()[0]

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
            return self.import_new_project(project_id, markdown_content, mode)
    
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
            success = self.import_new_project(new_project_id, markdown_content, mode)
            if success['action'] == 'synced':
                return {'action': 'synced', 'message': f'創建新專案 {new_project_id} (原專案相似度過低: {similarity:.2f})'}
            else:
                return success
    
    def import_new_project(self, project_id, markdown_content, mode):
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
        self.memory_manager = backend or MarkdownMemoryManager()
        self.version = "1.0.0"
        
        
        # 初始化匯入器
        self.importer = ProjectMemoryImporter(self.memory_manager)

    async def handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """處理 MCP 訊息"""
        # 提取請求 ID 用於回應
        request_id = message.get('id')
        
        try:
            method = message.get('method')
            
            if method == 'initialize':
                response = await self.handle_initialize(message)
            elif method == 'tools/list':
                response = await self.list_tools()
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
        tools = [
            {
                'name': 'save_project_memory',
                'description': '儲存資訊到專案記憶 / Save information to project-specific memory with optional title and category',
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
            {
                'name': 'get_project_memory',
                'description': '取得完整專案記憶內容 / Get full project memory content',
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
                'name': 'search_project_memory',
                'description': '搜尋專案記憶內容 / Search project memory for specific content',
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
                'name': 'list_memory_projects',
                'description': '列出所有記憶專案及統計資訊 / List all projects with memory and their statistics',
                'inputSchema': {
                    'type': 'object',
                    'properties': {}
                }
            },
            {
                'name': 'get_recent_project_memory',
                'description': 'Get recent project memory entries for a project',
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
            {
                'name': 'get_project_memory_stats',
                'description': 'Get statistics about a project\'s memory',
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
                'name': 'delete_project_memory',
                'description': 'Delete all project memory for a project (use with caution)',
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
                        'old_project_id': {
                            'type': 'string',
                            'description': 'Current project identifier'
                        },
                        'new_project_id': {
                            'type': 'string',
                            'description': 'New project identifier'
                        }
                    },
                    'required': ['old_project_id', 'new_project_id']
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
                memory = self.memory_manager.get_memory(arguments['project_id'])
                return self._success_response(
                    memory or f"No memory found for project: {arguments['project_id']}"
                )

            elif tool_name == 'search_project_memory':
                results = self.memory_manager.search_memory(
                    arguments['project_id'],
                    arguments['query'],
                    arguments.get('limit', 10)
                )
                
                if results:
                    text = f"Found {len(results)} matches for \"{arguments['query']}\":\n\n"
                    for i, result in enumerate(results, 1):
                        text += f"**{i}. {result['timestamp']}"
                        if result['title']:
                            text += f" - {result['title']}"
                        if result['category']:
                            text += f" #{result['category']}"
                        text += f"**\n{result['content']}\n\n"
                else:
                    text = f"No matches found for \"{arguments['query']}\" in project {arguments['project_id']}"
                
                return self._success_response(text)

            elif tool_name == 'list_memory_projects':
                projects = self.memory_manager.list_projects()
                if projects:
                    text = f"Found {len(projects)} projects:\n\n"
                    for project in projects:
                        text += f"**{project['name']}** (`{project['id']}`)\n"
                        text += f"  - Entries: {project['entries_count']}\n"
                        text += f"  - Last modified: {project['last_modified']}\n"
                        if project['categories']:
                            text += f"  - Categories: {', '.join(project['categories'])}\n"
                        text += "\n"
                else:
                    text = "No projects found"
                
                return self._success_response(text)

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
                    arguments['old_project_id'],
                    arguments['new_project_id']
                )
                
                if success:
                    return self._success_response(
                        f"✅ Project successfully renamed from '{arguments['old_project_id']}' to '{arguments['new_project_id']}'"
                    )
                else:
                    return self._error_response(
                        f"❌ Failed to rename project from '{arguments['old_project_id']}' to '{arguments['new_project_id']}'. "
                        f"Check if the old project exists and the new name is not already taken."
                    )

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
        logger.info(f"Starting Markdown Memory MCP Server v{self.version}")
        
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
                    response = await self.handle_message(message)
                    
                    # 只有非通知消息才需要回應
                    if response is not None:
                        # 設定 response ID
                        if 'id' in message:
                            response['id'] = message['id']
                        
                        # 將回應寫入 stdout
                        print(json.dumps(response, ensure_ascii=False))
                        sys.stdout.flush()
                    
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
        if db_path:
            # 展開 ~ 家目錄符號
            expanded_path = os.path.expanduser(db_path)
            return SQLiteBackend(expanded_path)
        else:
            return SQLiteBackend()
    else:
        raise ValueError(f"Unknown backend type: {backend_type}")

def main():
    """主程式入口點"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Markdown Memory MCP Server")
    parser.add_argument(
        "--backend", 
        choices=["markdown", "sqlite"], 
        default="markdown",
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
        help="SQLite 資料庫路徑 (預設: ai-memory/memory.db)，支援 ~ 家目錄符號"
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
            if args.db_path:
                db_path = Path(os.path.expanduser(args.db_path))
                print(f"SQLite database (custom): {db_path}")
            else:
                db_path = Path("ai-memory/memory.db")
                print(f"SQLite database (default): {db_path}")
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
        backend = create_backend(args.backend, args.db_path)
        if args.backend == "sqlite" and args.db_path:
            logger.info(f"Using {args.backend} backend with custom path: {args.db_path}")
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