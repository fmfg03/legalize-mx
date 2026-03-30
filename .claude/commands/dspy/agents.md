---
description: List and manage DSPy agents
category: ai-agents
allowed-tools: Bash(dspy-agent:*)
argument-hint: "[list|describe|create] [agent-name]"
---

# DSPy Agents Management

Manage the 9 specialized DSPy AI agents for various tasks.

## Commands

**List all agents**
```bash
dspy-agent list
```

**Describe specific agent**
```bash
dspy-agent describe {{args}}
```

**Create new agent**
```bash
dspy-agent create {{args}}
```

## Available Agents

- **qa** - Question answering with context
- **code** - Code analysis and generation  
- **summarizer** - Text summarization
- **rag_memory** - RAG with persistent memory
- **lightweight_rag** - Fast RAG implementation
- **enhanced_memory** - Advanced memory capabilities
- **commit_message** - Git commit message generation
- **gepa_optimizer** - GEPA optimization agent
- **base** - Foundation template for custom agents