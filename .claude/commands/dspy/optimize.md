---
description: DSPy agent optimization with GEPA
category: ai-agents
allowed-tools: Bash(dspy-agent:*)
argument-hint: "[agent-name] --iterations [num]"
---

# DSPy Agent Optimization

Optimize DSPy agents using GEPA (Genetic Evolution of Prompt Architectures) for improved performance.

## Optimization Commands

**Optimize an agent**
```bash
dspy-agent optimize {{args}}
```

**Test optimized agent**
```bash
dspy-agent test {{args}}
```

## GEPA Features

- **Genetic Evolution** - Evolves prompt architectures automatically
- **Performance Metrics** - Tracks improvement over iterations
- **Multi-objective** - Optimizes for accuracy, speed, and cost
- **Automatic Tuning** - Self-improving agent performance
- **Validation** - Built-in testing during optimization

## Usage Examples

- `dspy-agent optimize qa --iterations 20`
- `dspy-agent optimize code --metric accuracy`
- `dspy-agent optimize rag_memory --dataset validation.json`