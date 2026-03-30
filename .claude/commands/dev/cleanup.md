---
description: Clean up development artifacts (node_modules, logs, temp files)
category: development
allowed-tools: Bash(find:*), Bash(rm:*), Bash(echo:*)
argument-hint: ""
---

# Development Cleanup

Remove common development artifacts that accumulate during development:

- `node_modules` directories
- `.DS_Store` files (macOS)
- Log files (`*.log`)
- Temporary files (`*.tmp`)

## Execution

Clean up development artifacts in the current directory and subdirectories:

```bash
find . -name 'node_modules' -type d -exec rm -rf {} + 2>/dev/null
find . -name '.DS_Store' -delete 2>/dev/null
find . -name '*.log' -delete 2>/dev/null
find . -name '*.tmp' -delete 2>/dev/null
echo 'Development cleanup completed'
```

**Warning**: This will permanently delete files. Use with caution.
