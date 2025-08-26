# 推薦實現：智能路由 + 優化描述

# 1. 優化工具描述（方法1的精華）
OPTIMIZED_TOOL_DESCRIPTIONS = {
    'search_project_memory': {
        'name': 'search_project_memory',
        'description': '搜尋專案內容，回答任何專案相關問題 / Search project content to answer any project-related questions',
        # 移除技術細節，強調功能目的
    },
    
    'list_memory_projects': {
        'name': 'list_memory_projects', 
        'description': '查看所有專案列表 / View all available projects',
        # 去掉"記憶"這個詞
    }
}

# 2. 後端智能路由（方法2的核心）
def search_memory(self, project_id: str, query: str, limit: int = 10):
    """
    智能搜索：自動選擇最省token的策略
    用戶無感知，AI助手也無需知道內部實現
    """
    
    # 智能判斷查詢類型
    query_type = self._analyze_query_type(query)
    
    if query_type == 'simple_lookup':
        # 簡單查找：用search_index（超省token）
        results = self.search_index(project_id, query, limit)
        return self._format_index_results(results)
        
    elif query_type == 'complex_question':
        # 複雜問題：用RAG策略（智能省token）
        return self._rag_search(project_id, query, limit)
        
    else:
        # 默認：混合策略
        return self._hybrid_search(project_id, query, limit)

def _analyze_query_type(self, query: str) -> str:
    """分析查詢類型，決定使用哪種策略"""
    
    query_lower = query.lower()
    
    # 簡單查找關鍵詞
    simple_keywords = ['列表', 'list', '有哪些', '找到', 'find', '搜尋', 'search']
    if any(keyword in query_lower for keyword in simple_keywords):
        return 'simple_lookup'
    
    # 複雜問題關鍵詞  
    complex_keywords = ['為什麼', 'why', '如何', 'how', '解釋', 'explain', '分析', 'analyze']
    if any(keyword in query_lower for keyword in complex_keywords):
        return 'complex_question'
    
    # 根據長度判斷
    if len(query) > 50:
        return 'complex_question'
    
    return 'simple_lookup'

def _rag_search(self, project_id: str, query: str, limit: int) -> List[Dict]:
    """RAG策略：最大化相關性，最小化token"""
    
    # 第一階段：輕量級篩選
    candidates = self.search_index(project_id, query, limit * 3)
    
    # 第二階段：智能選擇最相關的內容
    selected = []
    total_tokens = 0
    max_tokens = 1500  # 控制總token數
    
    for candidate in candidates:
        if total_tokens >= max_tokens:
            break
            
        # 獲取完整內容
        full_content = self.get_memory_entry(candidate['id'])
        content_tokens = len(full_content['entry']) // 4
        
        if total_tokens + content_tokens <= max_tokens:
            selected.append({
                'timestamp': full_content['created_at'],
                'title': full_content['title'], 
                'category': full_content['category'],
                'content': full_content['entry'],
                'relevance': candidate.get('similarity', 0)
            })
            total_tokens += content_tokens
    
    return selected

# 3. 保持MCP接口不變
async def call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
    """工具調用保持完全不變"""
    
    tool_name = params.get('name')
    arguments = params.get('arguments', {})
    
    if tool_name == 'search_project_memory':
        # 內部自動使用智能路由，用戶無感知
        results = self.memory_manager.search_memory(
            arguments['project_id'],
            arguments['query'], 
            arguments.get('limit', 10)
        )
        # 格式化輸出保持不變...
        
    elif tool_name == 'list_memory_projects':
        # 保持原有邏輯...
        pass