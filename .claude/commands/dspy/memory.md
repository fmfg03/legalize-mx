---
description: DSPy memory management system
category: ai-agents
allowed-tools: Bash(dspy-agent:*)
argument-hint: "[load|query|compact|stats|scan] [options]"
---

# DSPy Memory Management

Advanced memory system for persistent context and project knowledge.

## Memory Commands

**Load project context**
```bash
dspy-agent memory load
```

**Query project memory**
```bash
dspy-agent memory query "{{args}}"
```

**Show memory statistics**
```bash
dspy-agent memory stats
```

**Compact memory database**
```bash
dspy-agent memory compact
```

**Scan and index project files**
```bash
dspy-agent memory scan
```

## Features

- **Persistent Memory** - Remembers context across sessions
- **Intelligent Indexing** - Automatically indexes project files
- **Semantic Search** - Query using natural language
- **Memory Compaction** - Optimizes storage and retrieval
- **Statistics** - Track memory usage and performance