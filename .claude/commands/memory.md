---
description: Learning memory system for pattern recognition
category: intelligence
allowed-tools: Bash(claude-memory:*), Read, Write
argument-hint: "[learn|suggest|list|stats] [options]"
---

# Learning Memory System

Capture, learn from, and apply successful development patterns across projects for continuous improvement.

## Commands

**`learn`** - Learn from successful patterns
- Usage: `claude-memory learn "pattern-name" "solution" --language javascript`
- Example: `claude-memory learn "JWT authentication" "httpOnly cookies with bcrypt"`

**`suggest`** - Get pattern-based suggestions
- Usage: `claude-memory suggest "task description"`
- Example: `claude-memory suggest "implement user authentication"`

**`list`** - List learned patterns
- Usage: `claude-memory list --type auth --limit 10`

**`stats`** - View learning statistics
- Usage: `claude-memory stats`

## Advanced Features

- Pattern categorization by language and type
- Success rate tracking
- Cross-project pattern discovery
- Intelligent suggestions based on context

## Execution

Use the learning memory system:

```bash
claude-memory {{args}}
```