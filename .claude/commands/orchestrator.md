---
description: Magic DSPy Orchestrator for multi-agent coordination
category: orchestration
allowed-tools: Bash(magic-orchestrator:*), Read, Write
argument-hint: "[run|compete|collaborate|iterate] \"task\" [options]"
---

# Magic DSPy Orchestrator

Coordinate multiple AI agents to solve complex tasks using adaptive, competitive, collaborative, or iterative execution modes.

## Execution Modes

**`run`** - Adaptive multi-agent coordination
- Usage: `magic-orchestrator run "task description"`
- Example: `magic-orchestrator run "build React app with tests"`

**`compete`** - Competitive execution (best solution wins)
- Usage: `magic-orchestrator compete "task" --agents agent1,agent2,agent3`
- Example: `magic-orchestrator compete "optimize performance" --agents react-expert,vite-expert`

**`collaborate`** - Collaborative execution (agents work together)
- Usage: `magic-orchestrator collaborate "task" --agents agent1,agent2`
- Example: `magic-orchestrator collaborate "design architecture" --agents backend-architect,database-expert`

**`iterate`** - Progressive iterative refinement
- Usage: `magic-orchestrator iterate "task" --rounds 3`
- Example: `magic-orchestrator iterate "improve auth system" --rounds 3`

## Additional Commands

- `magic-orchestrator list-agents` - List all 99+ available agents
- `magic-orchestrator stats` - Show orchestrator statistics

## Execution

Execute the Magic DSPy Orchestrator:

```bash
magic-orchestrator {{args}}
```