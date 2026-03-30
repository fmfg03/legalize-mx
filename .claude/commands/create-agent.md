---
description: Create custom agents from natural language descriptions
category: development
allowed-tools: Bash(claude-create:*), Read, Write
argument-hint: "\"I need an agent that validates APIs\""
---

# Natural Language Agent Creation

Generate specialized AI agents from natural language descriptions, automatically determining the optimal capabilities, tools, and implementation patterns.

## Commands

**`agent`** - Create a new specialized agent
- Usage: `claude-create agent "agent description"`
- Example: `claude-create agent "I need an agent for API validation and OpenAPI compliance"`

**`analyze`** - Analyze requirements without creating
- Usage: `claude-create analyze "agent description"`
- Example: `claude-create analyze "database optimization agent"`

## Agent Creation Process

1. **Intent Analysis** - Understands what kind of agent is needed
2. **Complexity Assessment** - Determines appropriate sophistication level  
3. **Template Selection** - Chooses optimal agent template
4. **Capability Mapping** - Assigns relevant tools and skills
5. **Code Generation** - Creates fully functional agent

## Agent Types

- **Testing Specialists** - Test automation, coverage analysis
- **Performance Optimizers** - Code optimization, profiling
- **Security Auditors** - Vulnerability scanning, compliance
- **Database Experts** - Query optimization, schema design
- **API Architects** - REST/GraphQL design, documentation
- **DevOps Engineers** - CI/CD, containerization, deployment

## Execution

Create custom agents from descriptions:

```bash
claude-create {{args}}
```