# Python Memory MCP Server

A Python-based Model Context Protocol (MCP) server providing intelligent memory management with SQLite and Markdown dual backend storage support.

## 🚀 Features

- 🗄️ **SQLite Backend** (Default): High-performance database storage with complex query support
- 📝 **Markdown Backend**: Human-readable file format, version control friendly
- 🔄 **Intelligent Sync**: Automatically sync Markdown projects to SQLite
- 🔍 Powerful search functionality (SQLite supports full-text search)
- 📊 Project categorization and statistical analysis
- 🕒 Timestamp tracking and history records
- ✏️ Edit and delete specific memory entries
- 🎯 Precise entry management (by ID, timestamp, title, category, content matching)
- 📋 Entry listing functionality for easy viewing and management
- 🚀 **Auto project list display on startup** for enhanced user experience
- 🎯 Perfect integration with Claude Desktop / Claude Code / Cursor / Rovo Dev
- 🚀 Support for Rovo Dev's `acli` command management
- 🐍 Pure Python implementation with no additional dependencies

## 🛠️ Installation and Setup

### 1. System Requirements

- Python 3.8+
- Claude Code or Cursor IDE
- Operating Systems: Windows, macOS, Linux

### 2. Quick Installation

```bash
# Clone the project
git clone https://github.com/wty0512/markdown-memory-mcp-server.git
cd markdown-memory-mcp-server

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

| Tool | Description |
|------|-------------|
| `save_project_memory` | Save information to project memory |
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
git clone https://github.com/wty0512/markdown-memory-mcp-server.git
cd markdown-memory-mcp-server

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