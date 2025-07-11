#!/usr/bin/env python3
"""
Markdown Memory MCP Server
一個基於 Python 的 Model Context Protocol 伺服器，使用 Markdown 檔案管理 AI 記憶
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MarkdownMemoryManager:
    """Markdown 記憶管理器"""
    
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
        """儲存記憶到 markdown 檔案"""
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
            
            # 寫入檔案
            if memory_file.exists():
                with open(memory_file, 'a', encoding='utf-8') as f:
                    f.write(entry)
            else:
                header = f"# AI Memory for {project_id}\n\n"
                header += f"Created: {timestamp}\n\n"
                with open(memory_file, 'w', encoding='utf-8') as f:
                    f.write(header + entry)
            
            logger.info(f"Memory saved for project: {project_id}")
            return True
            
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
        """列出所有專案及其統計資訊"""
        projects = []
        for file in self.memory_dir.glob("*.md"):
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
        """刪除專案記憶檔案"""
        try:
            memory_file = self.get_memory_file(project_id)
            if memory_file.exists():
                memory_file.unlink()
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
        """重建記憶檔案"""
        try:
            memory_file = self.get_memory_file(project_id)
            
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
            
            # 寫入檔案
            with open(memory_file, 'w', encoding='utf-8') as f:
                f.write("".join(content_parts))
            
            logger.info(f"Memory file rebuilt for project: {project_id}")
            return True
            
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

class MCPServer:
    """Model Context Protocol 伺服器"""
    
    def __init__(self):
        self.memory_manager = MarkdownMemoryManager()
        self.version = "1.0.0"

    async def handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """處理 MCP 訊息"""
        try:
            method = message.get('method')
            
            if method == 'initialize':
                return await self.handle_initialize(message)
            elif method == 'tools/list':
                return await self.list_tools()
            elif method == 'tools/call':
                return await self.call_tool(message['params'])
            elif method == 'resources/list':
                return await self.list_resources()
            elif method == 'prompts/list':
                return await self.list_prompts()
            elif method == 'notifications/initialized':
                return await self.handle_initialized()
            else:
                return self._error_response(-32601, f"Method not found: {method}")
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            return self._error_response(-32603, str(e))

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
                'name': 'save_memory',
                'description': 'Save information to markdown memory with optional title and category',
                'inputSchema': {
                    'type': 'object',
                    'properties': {
                        'project_id': {
                            'type': 'string',
                            'description': 'Project identifier (will be sanitized for filename)'
                        },
                        'content': {
                            'type': 'string',
                            'description': 'Content to save'
                        },
                        'title': {
                            'type': 'string',
                            'description': 'Optional title for the memory entry'
                        },
                        'category': {
                            'type': 'string',
                            'description': 'Optional category/tag for the memory entry'
                        }
                    },
                    'required': ['project_id', 'content']
                }
            },
            {
                'name': 'get_memory',
                'description': 'Get full memory content for a project',
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
                'name': 'search_memory',
                'description': 'Search memory for specific content',
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
                'name': 'list_projects',
                'description': 'List all projects with memory and their statistics',
                'inputSchema': {
                    'type': 'object',
                    'properties': {}
                }
            },
            {
                'name': 'get_recent_memory',
                'description': 'Get recent memory entries for a project',
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
                'name': 'get_memory_stats',
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
                'name': 'delete_memory',
                'description': 'Delete all memory for a project (use with caution)',
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
                'name': 'delete_memory_entry',
                'description': 'Delete specific memory entries based on various criteria',
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
                'name': 'edit_memory_entry',
                'description': 'Edit specific memory entry content',
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
                'name': 'list_memory_entries',
                'description': 'List all memory entries with their IDs for easy reference',
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
        return None

    async def call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """執行工具調用"""
        tool_name = params.get('name')
        arguments = params.get('arguments', {})

        try:
            if tool_name == 'save_memory':
                success = self.memory_manager.save_memory(
                    arguments['project_id'],
                    arguments['content'],
                    arguments.get('title', ''),
                    arguments.get('category', '')
                )
                return self._success_response(
                    f"Memory {'saved' if success else 'failed to save'} for project: {arguments['project_id']}"
                )

            elif tool_name == 'get_memory':
                memory = self.memory_manager.get_memory(arguments['project_id'])
                return self._success_response(
                    memory or f"No memory found for project: {arguments['project_id']}"
                )

            elif tool_name == 'search_memory':
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

            elif tool_name == 'list_projects':
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

            elif tool_name == 'get_recent_memory':
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

            elif tool_name == 'get_memory_stats':
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

            elif tool_name == 'delete_memory':
                success = self.memory_manager.delete_memory(arguments['project_id'])
                return self._success_response(
                    f"Memory {'deleted' if success else 'not found'} for project: {arguments['project_id']}"
                )

            elif tool_name == 'delete_memory_entry':
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

            elif tool_name == 'edit_memory_entry':
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

            elif tool_name == 'list_memory_entries':
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

if __name__ == "__main__":
    # 確保輸出是 UTF-8
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    
    # 添加調試資訊
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"Script path: {__file__}")
    
    server = MCPServer()
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("Server interrupted")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)