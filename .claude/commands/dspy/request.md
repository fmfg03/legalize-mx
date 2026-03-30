---
description: Natural language agent requests
category: ai-agents
allowed-tools: Bash(dspy-agent:*)
argument-hint: "\"I need an agent for [task description]\""
---

# Natural Language Agent Requests

Request specialized agents using natural language descriptions. The system will create or recommend the best agent for your needs.

## Request Command

**Create agent from description**
```bash
dspy-agent request "{{args}}"
```

## Example Requests

- `dspy-agent request "I need an agent for data analysis"`
- `dspy-agent request "Create an agent that writes technical documentation"`
- `dspy-agent request "I want an agent for code review and optimization"`
- `dspy-agent request "Build an agent for customer support automation"`

## AI-Powered Agent Creation

- **Intent Recognition** - Understands what type of agent you need
- **Template Selection** - Chooses optimal base template
- **Capability Mapping** - Assigns appropriate tools and skills
- **Automatic Setup** - Configures agent parameters
- **Ready to Use** - Agent is immediately available after creation

## Agent Types Supported

- Code analysis and generation
- Data processing and analysis  
- Text summarization and Q&A
- Documentation generation
- Memory and knowledge management
- Custom domain-specific agents