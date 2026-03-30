---
description: DSPy session management system
category: ai-agents
allowed-tools: Bash(dspy-agent:*)
argument-hint: "[save|list|load|search|delete] [session-id]"
---

# DSPy Session Management

Persistent session management for DSPy agents with save/load capabilities.

## Session Commands

**Save current session**
```bash
dspy-agent session save
```

**List all sessions**
```bash
dspy-agent session list
```

**Load a session**
```bash
dspy-agent session load {{args}}
```

**Search sessions**
```bash
dspy-agent session search "{{args}}"
```

**Delete a session**
```bash
dspy-agent session delete {{args}}
```

## Features

- **Session Persistence** - Save and restore complete agent states
- **Session History** - Track all previous sessions
- **Search Capability** - Find sessions by content or metadata
- **Session Metadata** - Automatic timestamping and tagging
- **Clean Management** - Delete old or unused sessions