---
description: Install project dependencies
category: development
allowed-tools: Bash(npm:*), Bash(yarn:*), Bash(pnpm:*)
argument-hint: ""
---

# Install Dependencies

Auto-detects the package manager and installs project dependencies.

## Detection Order

1. **pnpm** - if `pnpm-lock.yaml` exists
2. **yarn** - if `yarn.lock` exists  
3. **npm** - fallback default

## Execution

Install project dependencies:

```bash
npm install || yarn install || pnpm install
```

The command will try each package manager until one succeeds.
