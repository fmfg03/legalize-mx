---
description: Auto-Analyst data analytics automation system
category: analytics
allowed-tools: Bash(claude-auto-analyst:*), Bash(python:*), Read, Write
argument-hint: "[analyze|quick-ml|visualize|agents] [options]"
---

# Auto-Analyst Data Analytics System

Execute automated data analytics using specialized AI agents for preprocessing, statistical analysis, machine learning, and visualization.

## Available Subcommands

**`analyze`** - Complete data analysis pipeline
- Usage: `claude-auto-analyst analyze "goal" -d data.csv`
- Example: `claude-auto-analyst analyze "customer insights" -d customers.csv`

**`quick-ml`** - Rapid machine learning analysis
- Usage: `claude-auto-analyst quick-ml "prediction task" -d data.csv`
- Example: `claude-auto-analyst quick-ml "predict sales" -d sales.csv`

**`visualize`** - Generate comprehensive visualizations
- Usage: `claude-auto-analyst visualize "dashboard" -d data.csv`
- Example: `claude-auto-analyst visualize "customer dashboard" -d metrics.csv`

**`agents`** - List available data analytics agents
- Usage: `claude-auto-analyst agents`

## Execution

Run the Auto-Analyst system with your specified command:

```bash
claude-auto-analyst {{args}}
```