---
description: Agent performance analytics and monitoring
category: analytics
allowed-tools: Bash(claude-analytics:*), Read, Write
argument-hint: "[performance|top|trends] [agent-name]"
---

# Agent Performance Analytics

Track and analyze the performance of AI agents over time to optimize development workflows and identify the most effective agents for specific tasks.

## Commands

**`performance`** - Get agent performance metrics
- Usage: `claude-analytics performance agent-name`
- Example: `claude-analytics performance react-expert`
- Metrics: Success rate, completion time, quality scores

**`top`** - View top performing agents
- Usage: `claude-analytics top`
- Shows: Ranking of agents by performance
- Categories: By task type, recent performance, overall success

**`trends`** - Analyze performance trends
- Usage: `claude-analytics trends`
- Analysis: Performance over time, improvement patterns
- Insights: Which agents are improving/declining

## Performance Metrics

- **Success Rate**: Task completion percentage
- **Quality Score**: Output quality assessment
- **Speed**: Average task completion time
- **Specialization**: Best use cases for each agent
- **Improvement Trends**: Performance evolution over time

## Execution

Monitor agent performance:

```bash
claude-analytics {{args}}
```