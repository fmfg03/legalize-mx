---
description: Intelligent project context analysis and configuration
category: intelligence
allowed-tools: Bash(claude-context:*), Read, Write
argument-hint: "[analyze|init|recommend] [options]"
---

# Intelligent Project Context

Automatically analyze project structure, detect technologies, and recommend optimal AI agent configurations for maximum development efficiency.

## Commands

**`analyze`** - Analyze current project context
- Usage: `claude-context analyze`
- Detects: Languages, frameworks, build tools, testing frameworks
- Output: Comprehensive project analysis report

**`init`** - Initialize with optimal configuration
- Usage: `claude-context init --auto-configure`
- Creates: Project-specific CLAUDE.md with agent recommendations
- Configures: Optimal agent selection based on tech stack

**`recommend`** - Get intelligent recommendations
- Usage: `claude-context recommend`
- Provides: Agent suggestions for current project
- Based on: Tech stack analysis and best practices

## Project Types Supported

- React/Next.js applications
- Django/Flask Python projects  
- Node.js/Express backends
- Go microservices
- Rust systems programming
- And 20+ other project types

## Execution

Analyze and configure your project context:

```bash
claude-context {{args}}
```