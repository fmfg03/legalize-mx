---
description: Enterprise development workflows and pipelines
category: development
allowed-tools: Bash(claude-workflows:*), Read, Write
argument-hint: "[list|run|info] [workflow-name]"
---

# Enterprise Development Workflows

Execute comprehensive development pipelines including feature development, bug fixes, API development, performance optimization, and security audits.

## Available Workflows

**`feature-complete`** - Complete feature development (5 steps, 180min)
- Analyze → Implement → Test → Review → Document

**`bug-fix`** - Systematic debugging (4 steps, 60min) 
- Diagnose → Fix → Test → Regression Check

**`api-development`** - Complete API with docs (5 steps, 240min)
- Design → Implement → Secure → Test → Document

**`performance-optimization`** - Comprehensive optimization (5 steps, 300min)
- Baseline → Identify Bottlenecks → Optimize → Validate

**`security-audit`** - Security hardening (5 steps, 200min)
- Scan → Analyze → Fix → Harden → Validate

## Commands

- `claude-workflows list` - Show all available workflows
- `claude-workflows run workflow-name` - Execute a workflow
- `claude-workflows info workflow-name` - Get workflow details

## Execution

Run enterprise workflows:

```bash
claude-workflows {{args}}
```