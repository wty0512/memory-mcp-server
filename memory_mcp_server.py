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
        # 如果是相對路徑，轉換為絕對路徑
        if not Path(memory_dir).is_absolute():
            # 使用腳本所在目錄作為基準
            script_dir = Path(__file__).parent
            self.memory_dir = script_dir / memory_dir
        else:
            self.memory_dir = Path(memory_dir)
        
        # 確保目錄存在
        try:
            self.memory_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Memory directory initialized: {self.memory_dir.absolute()}")
        except OSError as e:
            logger.error(f"Failed to create memory directory: {e}")
            # 如果無法創建，使用臨時目錄
            import tempfile
            self.memory_dir = Path(tempfile.mkdtemp(prefix="ai-memory-"))
            logger.warning(f"Using temporary directory: {self.memory_dir.absolute()}")

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
            else:
                return self._error_response(-32601, f"Method not found: {method}")
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            return self._error_response(-32603, str(e))

    async def handle_initialize(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """處理初始化請求"""
        return {
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
            }
        ]
        
        return {
            'result': {
                'tools': tools
            }
        }

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

            else:
                return self._error_response(-32601, f"Unknown tool: {tool_name}")

        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            return self._error_response(-32603, str(e))

    def _success_response(self, text: str) -> Dict[str, Any]:
        """建立成功回應"""
        return {
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