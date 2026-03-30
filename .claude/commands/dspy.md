---
description: DSPy Agent System - Advanced AI agent framework
category: ai-agents
allowed-tools: Bash(dspy-agent:*)
argument-hint: "[list|create|describe|test|optimize|install|request|memory|session] [options]"
---

# DSPy Agent System

Advanced AI agent framework with 9 specialized agents, memory management, and session persistence.

## Available Agents

- **base** - Foundation agent template
- **gepa_optimizer** - GEPA optimization agent
- **qa** - Question answering agent
- **code** - Code analysis and generation
- **summarizer** - Text summarization
- **rag_memory** - RAG with memory capabilities
- **lightweight_rag** - Lightweight RAG implementation
- **enhanced_memory** - Enhanced memory agent
- **commit_message** - Git commit message generation

## Core Commands

**`list`** - List available agents
- Usage: `dspy-agent list`

**`create`** - Create a new agent
- Usage: `dspy-agent create agent-name --template base`

**`describe`** - Get agent details
- Usage: `dspy-agent describe agent-name`

**`test`** - Test an agent
- Usage: `dspy-agent test agent-name --input "test query"`

**`optimize`** - Optimize with GEPA
- Usage: `dspy-agent optimize agent-name --iterations 10`

**`request`** - Natural language agent requests
- Usage: `dspy-agent request "I need an agent for data analysis"`

## Advanced Features

**Memory Management**
- `dspy-agent memory load` - Load CLAUDE.md into memory
- `dspy-agent memory query "search term"` - Query project memory
- `dspy-agent memory stats` - Show memory statistics

**Session Management**
- `dspy-agent session save` - Save current session
- `dspy-agent session list` - List saved sessions
- `dspy-agent session load session-id` - Load a session

## Execution

Run DSPy agent commands:

```bash
dspy-agent {{args}}
```