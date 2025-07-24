# Python Memory MCP Server

A Python-based Model Context Protocol (MCP) server providing intelligent memory management with SQLite and Markdown dual backend storage support.

## 🚀 Features

- 🗄️ **SQLite Backend** (Default): High-performance database storage with complex query support
- 📝 **Markdown Backend**: Human-readable file format, version control friendly
- 🔄 **Intelligent Sync**: Automatically sync Markdown projects to SQLite
- 📤 **Multi-format Export**: Support export to Markdown, JSON, CSV, TXT formats
- 🔍 Powerful search functionality (SQLite supports full-text search)
- 📊 Project categorization and statistical analysis
- 🕒 Timestamp tracking and history records
- ✏️ Edit and delete specific memory entries
- 🎯 Precise entry management (by ID, timestamp, title, category, content matching)
- 📋 Entry listing functionality for easy viewing and management
- 🚀 **Auto project list display on startup** for enhanced user experience
- 🎯 Perfect integration with Claude Desktop / Claude Code / Cursor / Rovo Dev
- 🚀 Support for Rovo Dev's `acli` command management
- 🌐 **Global Memory**: Cross-project knowledge base for storing universal standards and best practices
- 🐍 Pure Python implementation with no additional dependencies

## 🛠️ Installation and Setup

### 1. System Requirements

- Python 3.8+
- Claude Code or Cursor IDE
- Operating Systems: Windows, macOS, Linux

### 2. Quick Installation

```bash
# Clone the project
git clone https://github.com/wty0512/memory-mcp-server.git
cd memory-mcp-server

# Create virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Check dependencies (currently uses Python standard library, no additional dependencies needed)
# pip install -r requirements.txt  # Currently not needed

# Set execution permissions (macOS/Linux)
chmod +x memory_mcp_server.py
chmod +x start_server.sh

# 🚀 First startup will automatically sync existing Markdown projects to SQLite
# If you have existing Markdown memory files, the system will handle them automatically
```

### 3. Claude Desktop Configuration

Edit your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "memory-server": {
      "command": "python3",
      "args": ["/absolute/path/to/memory_mcp_server.py", "--backend=sqlite"],
      "transport": "stdio",
      "env": {
        "PYTHONPATH": "/absolute/path/to/project"
      }
    }
  }
}
```

### 4. Backend Options

- **SQLite Backend** (Recommended): `--backend=sqlite`
- **Markdown Backend**: `--backend=markdown`
- **Default**: Uses Markdown backend if no parameter specified (backward compatibility)

## 📖 Usage Examples

### Basic Memory Operations

```
# Save memory
Save the following information to project "my-project": Today I learned about Python decorators.

# Search memory
Search for "decorators" in project "my-project"

# List all projects
Show me all my memory projects

# Get recent memories
Show me the latest 5 entries from project "my-project"
```

### Advanced Operations

```
# Edit specific entry
Edit entry #3 in project "my-project" and change the title to "Python Decorators Deep Dive"

# Delete specific entry
Delete entry with title "old notes" from project "my-project"

# Project statistics
Show me statistics for project "my-project"
```

## 🔧 Advanced Configuration

### Using Different Backends

```bash
# Use SQLite backend (recommended)
python3 memory_mcp_server.py --backend=sqlite

# Use Markdown backend
python3 memory_mcp_server.py --backend=markdown

# Sync existing Markdown to SQLite
python3 memory_mcp_server.py --backend=sqlite --sync-from-markdown
```

### IDE Configuration Examples

#### Cursor IDE
Create `.cursor/mcp.json` in your project:

```json
{
  "mcpServers": {
    "memory-server": {
      "command": "python3",
      "args": ["./memory_mcp_server.py", "--backend=sqlite"],
      "transport": "stdio"
    }
  }
}
```

#### Claude Code
Global configuration in `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "memory-server": {
      "command": "python3",
      "args": ["/absolute/path/to/memory_mcp_server.py", "--backend=sqlite"],
      "transport": "stdio"
    }
  }
}
```

## 🎯 Available Tools

### Project Memory Tools
| Tool | Description |
|------|-------------|
| `save_project_memory` | Save information to project memory |
| `🧠 start_intelligent_save` | Start intelligent save process with AI project recommendations |
| `🧠 handle_save_choice` | Handle user choice in intelligent save process |
| `get_project_memory` | Get full project memory content |
| `search_project_memory` | Search for specific content |
| `list_memory_projects` | List all projects with statistics |
| `get_recent_project_memory` | Get recent memory entries |
| `get_project_memory_stats` | Get project statistics |
| `delete_project_memory` | Delete entire project memory |
| `delete_project_memory_entry` | Delete specific memory entries |
| `edit_project_memory_entry` | Edit specific memory entries |
| `list_project_memory_entries` | List all entries with IDs |
| `sync_markdown_to_sqlite` | Sync Markdown projects to SQLite |
| `export_project_memory` | Export project memory to multiple formats |

### Global Memory Tools
| Tool | Description |
|------|-------------|
| `🌐 save_global_memory` | Save content to global memory |
| `🌐 get_global_memory` | Get all global memory content |
| `🌐 search_global_memory` | Search global memory content |
| `🌐 get_global_memory_stats` | Get global memory statistics |

## 📚 Usage Guide

### Project Memory Operations

Project memory is used for storing project-specific information, discussions, decisions, and progress.

**Example: Save project memory**
```
Please save this discussion summary:
- Implemented Python MCP server
- Added SQLite and Markdown dual backend support
- Integrated full-text search functionality

Project: my-project
Title: MCP Server Development Progress
Category: development
```

**Example: Search project memory**
```
Search for "SQLite" in my-project
```


### Global Memory Operations

Global memory is used for storing cross-project shared knowledge such as development standards, best practices, and common templates.

**Example: Save global memory**
```
Please save this Git commit message standard to global memory:

[TAG] module_name: Brief description of changes (≤ 50 chars)

Tag descriptions:
- [FIX] Bug fixes
- [ADD] New features
- [IMP] Improvements
- [REF] Code refactoring

Title: Git Commit Standards
Category: development-standards
```

**Example: Query global memory**
```
Please check all content in global memory
```

**Example: Search global memory**
```
Search for "Git" in global memory
```

**Usage Recommendations**:
- 🎯 **Project Memory**: Store project-specific discussions, decisions, progress
- 🌐 **Global Memory**: Store universal standards, templates, best practices
- 💡 **Active Reference**: Explicitly ask AI to reference relevant memory when needed

## 🔍 Troubleshooting

### Common Issues

1. **Server not starting**
   - Check Python version (3.8+ required)
   - Verify file permissions
   - Check configuration file syntax

2. **Memory not saving**
   - Ensure write permissions in memory directory
   - Check disk space
   - Verify project ID format

3. **Search not working**
   - For SQLite: Check FTS5 support
   - For Markdown: Verify file encoding

### Debug Mode

```bash
# Enable debug logging
python3 memory_mcp_server.py --backend=sqlite --debug
```

## 🤝 Contributing

We welcome contributions! Please feel free to submit issues and pull requests.

### Development Setup

```bash
# Clone for development
git clone https://github.com/wty0512/memory-mcp-server.git
cd memory-mcp-server

# Create development environment
python3 -m venv venv
source venv/bin/activate

# Run tests
python3 -m pytest tests/
```

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Built for the Model Context Protocol (MCP) ecosystem
- Inspired by the need for persistent AI memory management
- Thanks to the Claude and Cursor communities for feedback

---

**中文版本請參閱 [README.md](README.md)**