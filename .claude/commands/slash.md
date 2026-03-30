---
description: Access Claude Code Supercharged command menu
category: system
allowed-tools: Bash(claude-slash:*)
argument-hint: "[menu|help] [command-name]"
---

# Claude Code Supercharged Menu

Access the complete interactive menu of all 67+ supercharged commands across 8 categories.

## Commands

**`menu`** - Show interactive command menu
- Usage: `claude-slash menu` or `slash menu`
- Displays: All 67+ commands organized by category
- Interactive: Type commands directly from the menu

**`help`** - Get help for specific command
- Usage: `claude-slash help command-name`
- Example: `claude-slash help /orchestrator`

## Categories Available

- 🎭 **Magic Orchestration** - Multi-agent coordination
- 🔄 **Enterprise Workflows** - Development pipelines  
- 🧠 **Learning & Memory** - Pattern recognition
- 🧠 **Cross-Project Intelligence** - Knowledge sharing
- 📊 **Analytics & Performance** - Agent monitoring
- 🤖 **Agent Creation** - Custom agent development
- 📊 **Auto-Analyst** - Data analytics automation
- 🛠️ **Development Tools** - Project utilities

## Execution

Access the supercharged command menu:

```bash
claude-slash {{args}}
```

If no arguments provided, defaults to showing the menu.
