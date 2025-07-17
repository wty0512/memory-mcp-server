# Installation Guide

## System Requirements

- Python 3.8 or higher
- Claude Code or Cursor IDE
- Supported OS: Windows, macOS, Linux

## Backend Selection

This system supports two storage backends:

- **SQLite** (Default Recommended): High-performance database with full-text search and complex queries
- **Markdown**: Human-readable format, version control friendly and manual editing support

The system automatically syncs existing Markdown projects to SQLite without manual conversion.

## Installation Steps

### 1. Download Project

```bash
git clone https://github.com/your-username/markdown-memory-mcp.git
cd markdown-memory-mcp
```

### 2. Setup Python Environment

```bash
# Create virtual environment (recommended)
python3 -m venv venv

# Activate virtual environment
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Install dependencies (currently no additional dependencies)
pip install -r requirements.txt
```

### 3. Set Execution Permissions

```bash
chmod +x memory_mcp_server.py
chmod +x start_server.sh
```

### 4. Test Installation

```bash
python3 memory_mcp_server.py --help
```

## IDE Configuration

### Claude Code / Cursor Configuration

#### Global Configuration
Edit `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "memory-server": {
      "command": "python3",
      "args": ["/absolute/path/to/memory_mcp_server.py", "--backend=sqlite"],
      "transport": "stdio",
      "env": {
        "PYTHONPATH": "/absolute/path/to/markdown-memory-mcp"
      }
    }
  }
}
```

#### Project Configuration
Create `.cursor/mcp.json` in project root:

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

#### Backend Options
- Use SQLite (Default Recommended): `--backend=sqlite`
- Use Markdown: `--backend=markdown`
- Default uses Markdown when no parameter specified (backward compatibility)

## Verify Installation

1. Start server:
```bash
./start_server.sh
```

2. Test in Claude Code:
```
List all projects with memory
```

If you see a response, installation is successful!

## Advanced Configuration

### Backend Migration

```bash
# Sync existing Markdown projects to SQLite
python3 memory_mcp_server.py --backend=sqlite --sync-from-markdown

# Preview sync without making changes
python3 memory_mcp_server.py --backend=sqlite --sync-from-markdown --sync-mode=preview
```

### Performance Tuning

For SQLite backend, you can optimize performance:

```bash
# Use SQLite with custom database path
python3 memory_mcp_server.py --backend=sqlite --db-path=/path/to/custom/memory.db
```

### Development Mode

```bash
# Run in development mode with debug logging
python3 memory_mcp_server_dev.py --backend=sqlite --debug
```

## Troubleshooting

### Common Issues

1. **Permission Denied**
   ```bash
   chmod +x memory_mcp_server.py
   ```

2. **Python Version Issues**
   ```bash
   python3 --version  # Should be 3.8+
   ```

3. **Module Not Found**
   ```bash
   pip install -r requirements.txt
   ```

4. **SQLite Issues**
   - Ensure SQLite3 is available: `python3 -c "import sqlite3; print('OK')"`
   - Check disk space for database file

5. **Configuration Issues**
   - Validate JSON syntax in configuration files
   - Check file paths are absolute and correct
   - Verify Python executable path

### Debug Mode

Enable detailed logging:

```bash
python3 memory_mcp_server.py --backend=sqlite --debug
```

### Log Files

Check log files for detailed error information:
- Server logs: Console output
- Database logs: SQLite error messages
- File system logs: Permission and access errors

## Next Steps

After successful installation:

1. **Test Basic Functionality**: Save and retrieve a test memory
2. **Configure Your IDE**: Set up MCP server in your preferred IDE
3. **Import Existing Data**: Use sync functionality if you have existing Markdown files
4. **Explore Features**: Try different tools and search capabilities

---

**中文版本請參閱 [installation.md](installation.md)**