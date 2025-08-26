# RAG Enhancement Proposal for Memory MCP Server

## 現狀分析 / Current State Analysis

### ✅ 已具備的RAG組件
- **文檔存儲**: SQLite + FTS5全文搜索
- **檢索接口**: search_memory, search_index
- **內容分塊**: 按條目組織，支持階層結構
- **元數據**: title, category, timestamp, hierarchy_level
- **多格式支持**: Markdown, JSON, CSV導入導出

### 🔄 需要增強的部分

#### 1. 向量化檢索 (Vector Search)
```python
# 新增向量化功能
class VectorizedMemoryBackend(SQLiteBackend):
    def __init__(self, db_path: str, embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"):
        super().__init__(db_path)
        self.embedding_model = self._load_embedding_model(embedding_model)
        self._init_vector_tables()
    
    def _init_vector_tables(self):
        """初始化向量存儲表"""
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_embeddings (
                    entry_id INTEGER PRIMARY KEY,
                    embedding BLOB,  -- 存儲向量
                    embedding_model TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (entry_id) REFERENCES memory_entries(id)
                )
            """)
    
    def add_memory_with_embedding(self, project: str, title: str, entry: str, **kwargs):
        """添加記憶並生成向量"""
        entry_id = super().add_memory(project, title, entry, **kwargs)
        
        # 生成向量
        embedding = self._generate_embedding(f"{title} {entry}")
        
        # 存儲向量
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO memory_embeddings (entry_id, embedding, embedding_model)
                VALUES (?, ?, ?)
            """, (entry_id, embedding.tobytes(), self.embedding_model.name))
        
        return entry_id
    
    def semantic_search(self, project: str, query: str, limit: int = 10):
        """語義搜索"""
        query_embedding = self._generate_embedding(query)
        
        # 使用余弦相似度搜索
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT me.*, 
                       cosine_similarity(mem.embedding, ?) as similarity
                FROM memory_entries me
                JOIN memory_embeddings mem ON me.id = mem.entry_id
                WHERE me.project = ?
                ORDER BY similarity DESC
                LIMIT ?
            """, (query_embedding.tobytes(), project, limit))
            
            return [dict(row) for row in cursor.fetchall()]
```

#### 2. 混合檢索策略 (Hybrid Retrieval)
```python
def hybrid_search(self, project: str, query: str, limit: int = 10, 
                 semantic_weight: float = 0.7, keyword_weight: float = 0.3):
    """混合檢索：語義搜索 + 關鍵詞搜索"""
    
    # 語義搜索結果
    semantic_results = self.semantic_search(project, query, limit * 2)
    
    # 關鍵詞搜索結果 (現有的FTS5)
    keyword_results = self.search_mem_entries(project, query, limit * 2)
    
    # 結果融合和重排序
    combined_results = self._merge_and_rerank(
        semantic_results, keyword_results, 
        semantic_weight, keyword_weight
    )
    
    return combined_results[:limit]
```

#### 3. 智能分塊策略 (Smart Chunking)
```python
def intelligent_chunking(self, content: str, max_chunk_size: int = 512):
    """智能分塊：保持語義完整性"""
    
    # 按段落分割
    paragraphs = content.split('\n\n')
    chunks = []
    current_chunk = ""
    
    for paragraph in paragraphs:
        if len(current_chunk + paragraph) <= max_chunk_size:
            current_chunk += paragraph + '\n\n'
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = paragraph + '\n\n'
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks
```

#### 4. RAG查詢接口
```python
async def rag_query(self, project_id: str, question: str, 
                   context_limit: int = 5, max_tokens: int = 2000):
    """RAG查詢：檢索相關內容並生成回答"""
    
    # 1. 檢索相關內容
    relevant_docs = self.hybrid_search(project_id, question, context_limit)
    
    # 2. 構建上下文
    context = self._build_context(relevant_docs, max_tokens)
    
    # 3. 構建提示詞
    prompt = f"""基於以下專案記憶內容回答問題：

上下文：
{context}

問題：{question}

請基於上述內容提供準確的回答。如果內容中沒有相關信息，請明確說明。
"""
    
    return {
        'prompt': prompt,
        'context_sources': [
            {
                'title': doc['title'],
                'timestamp': doc['created_at'],
                'similarity': doc.get('similarity', 0),
                'content_preview': doc['entry'][:200] + '...'
            }
            for doc in relevant_docs
        ]
    }
```

## 實施建議 / Implementation Recommendations

### 階段1：最小可行RAG (2-3天)
- [x] 現有搜索功能已足夠基礎RAG
- [ ] 添加`rag_query`工具到MCP接口
- [ ] 優化現有搜索結果排序

### 階段2：向量化增強 (1-2週)
- [ ] 集成sentence-transformers
- [ ] 添加向量存儲表
- [ ] 實現語義搜索

### 階段3：高級RAG (2-3週)  
- [ ] 混合檢索策略
- [ ] 智能分塊
- [ ] 查詢重寫和擴展
- [ ] 結果重排序

## 技術選型建議

### 向量化模型
- **輕量級**: `sentence-transformers/all-MiniLM-L6-v2` (22MB)
- **中等**: `sentence-transformers/all-mpnet-base-v2` (420MB)  
- **多語言**: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`

### 向量數據庫
- **SQLite + 自定義**: 利用現有架構，添加向量列
- **Chroma**: 輕量級向量數據庫
- **FAISS**: Facebook的向量搜索庫

## 工作量評估

### 🟢 低工作量 (1-2天)
使用現有搜索功能實現基礎RAG，只需添加：
```python
# 新增MCP工具
{
    'name': 'rag_query',
    'description': '基於專案記憶的RAG查詢',
    'inputSchema': {
        'type': 'object',
        'properties': {
            'project_id': {'type': 'string'},
            'question': {'type': 'string'},
            'context_limit': {'type': 'integer', 'default': 5}
        }
    }
}
```

### 🟡 中等工作量 (1-2週)
添加向量化搜索，需要：
- 集成embedding模型
- 修改數據庫schema
- 實現語義搜索

### 🔴 高工作量 (3-4週)
完整RAG系統，包括：
- 高級檢索策略
- 查詢優化
- 性能調優
- 完整測試

## 結論

你的系統已經具備了RAG的基礎架構！最快1-2天就能實現基礎RAG功能，主要是添加一個`rag_query`工具來整合現有的搜索和內容組織能力。

要不要我幫你實現一個基礎版本的RAG查詢功能？