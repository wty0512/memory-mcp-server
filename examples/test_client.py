#!/usr/bin/env python3
"""
測試客戶端範例
用於測試 Markdown Memory MCP Server 的功能
"""

import json
import subprocess
import sys
from typing import Dict, Any

class MCPTestClient:
    """MCP 測試客戶端"""
    
    def __init__(self, server_path: str = "./memory_mcp_server.py"):
        self.server_path = server_path
        self.request_id = 1
    
    def send_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """發送請求到 MCP 伺服器"""
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method
        }
        
        if params:
            request["params"] = params
        
        self.request_id += 1
        
        # 這裡應該實作實際的 MCP 通訊
        # 目前只是範例結構
        print(f"Sending request: {json.dumps(request, ensure_ascii=False)}")
        
        # 模擬回應
        return {
            "jsonrpc": "2.0",
            "id": request["id"],
            "result": {"message": "Test response"}
        }
    
    def test_save_memory(self):
        """測試儲存記憶功能"""
        print("Testing save_memory...")
        response = self.send_request("tools/call", {
            "name": "save_memory",
            "arguments": {
                "project_id": "test-project",
                "content": "這是一個測試記憶條目",
                "title": "測試標題",
                "category": "testing"
            }
        })
        print(f"Response: {response}")
    
    def test_get_memory(self):
        """測試取得記憶功能"""
        print("Testing get_memory...")
        response = self.send_request("tools/call", {
            "name": "get_memory",
            "arguments": {
                "project_id": "test-project"
            }
        })
        print(f"Response: {response}")
    
    def test_search_memory(self):
        """測試搜尋記憶功能"""
        print("Testing search_memory...")
        response = self.send_request("tools/call", {
            "name": "search_memory",
            "arguments": {
                "project_id": "test-project",
                "query": "測試",
                "limit": 5
            }
        })
        print(f"Response: {response}")
    
    def run_tests(self):
        """執行所有測試"""
        print("Starting MCP Server tests...")
        print("=" * 50)
        
        self.test_save_memory()
        print()
        
        self.test_get_memory()
        print()
        
        self.test_search_memory()
        print()
        
        print("Tests completed!")

if __name__ == "__main__":
    client = MCPTestClient()
    client.run_tests()