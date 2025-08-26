# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Server
```bash
# Start the memory MCP server with default SQLite backend
python3 memory_mcp_server.py

# Start with specific database path
./start_server.sh /path/to/custom.db

# Set executable permissions (first time setup)
chmod +x memory_mcp_server.py
chmod +x start_server.sh
```

### Testing
```bash
# Run the test client example
python3 examples/test_client.py

# Manual server testing
python3 -c "from memory_mcp_server import MCPServer; print('✅ Server imports successfully')"
```

## Architecture Overview

This is a **Python Memory MCP Server** that provides intelligent memory management with dual backend storage support (SQLite + Markdown). The codebase has undergone a major 2.0 architectural refactoring, simplifying from 25+ tables to 7 tables (72% reduction).

### Core Components

#### Main Server (`memory_mcp_server.py`)
- **Dual Backend Architecture**: SQLite (default, high-performance) and Markdown (human-readable)
- **Unified Data Model**: Single main table design with 7 core tables total
- **Full-Text Search**: SQLite FTS5 + Trigram tokenizer with perfect Chinese search support
- **Auto-sync**: Automatically syncs Markdown projects to SQLite on startup
- **Cross-platform File Locking**: Supports Windows, macOS, and Linux

#### Backend Storage Systems
- **SQLiteBackend**: High-performance database with complex query support
- **MarkdownBackend**: Version control friendly, human-readable format
- **Auto Migration**: 100% data migration guarantee from older versions

### Database Schema (SQLite 2.0)
```
memory_entries (main table)
├── id (unique identifier)
├── project (project name)
├── category (category tag)
├── entry_type (entry type)
├── title (title)
├── summary (summary)
├── entry (content)
├── created_at (creation timestamp)
└── updated_at (update timestamp)

Supporting structures:
├── memory_fts (FTS5 search table)
├── Auto triggers (INSERT/UPDATE/DELETE)
└── Indexes (project, category, time-based)
```

### Key Features Implementation

#### Memory Management
- **Project Memory**: Scoped to specific projects with search and categorization
- **Global Memory**: Cross-project shared knowledge base for standards and best practices
- **Entry Management**: CRUD operations with precise targeting by ID, timestamp, title, category, or content
- **Multi-format Export**: Support for Markdown, JSON, CSV, TXT formats

#### Search & Intelligence
- **Full-Text Search**: FTS5 implementation with trigram tokenization
- **Smart Routing**: Intelligent query analysis to choose optimal search strategy
- **Index-based Search**: High-performance search with minimal token usage
- **Hybrid Search**: Combines multiple strategies for optimal results

## Configuration

### MCP Server Setup
The server supports multiple client integrations:

- **Claude Desktop**: Configure in `claude_desktop_config.json`
- **Claude Code/Cursor**: Configure in `.cursor/mcp.json`
- **Rovo Dev**: Configure in `~/.rovodev/mcp.json`

### Environment Requirements
- Python 3.8+
- No external dependencies (uses Python standard library only)
- Cross-platform support (Windows, macOS, Linux)

## Memory Storage Location
- **SQLite**: `ai-memory/memory.db` (default)
- **Markdown**: `ai-memory/` directory with project-based files
- **Auto-creation**: Memory directory created automatically on first run

## Development Patterns

### Backend Abstraction
The codebase uses an abstract `Backend` class with concrete implementations:
- Implement new backends by extending `Backend` ABC
- All backends must support the same interface for seamless switching

### Error Handling
- Cross-platform file locking with graceful fallbacks
- Comprehensive logging with structured error messages
- Safe migration patterns with data integrity validation

### Memory Operations
Key operational patterns:
- All memory operations are project-scoped unless explicitly global
- Timestamps are automatically managed (created_at, updated_at)
- Content is stored with metadata for rich querying capabilities
- Search operations support both exact and fuzzy matching

## Smart Features

### Intelligent Query Analysis
The system includes smart routing (`smart_routing_implementation.py`) that:
- Analyzes query types to choose optimal search strategies
- Automatically selects token-efficient approaches
- Provides seamless user experience without exposing implementation details

### Auto-sync Behavior
- Markdown files are automatically synced to SQLite on startup
- Existing Markdown projects are preserved and migrated
- System handles both fresh installs and upgrades transparently