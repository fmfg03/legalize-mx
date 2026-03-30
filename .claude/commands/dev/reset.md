---
description: Reset project dependencies completely
category: development
allowed-tools: Bash(rm:*), Bash(npm:*), Bash(yarn:*), Bash(pnpm:*)
argument-hint: ""
---

# Reset Dependencies

Completely reset and reinstall project dependencies. Useful for resolving dependency conflicts or corruption.

## Process

1. Remove existing dependency directories and lock files
2. Clear package manager caches
3. Reinstall all dependencies fresh

## Execution

Reset and reinstall dependencies:

```bash
rm -rf node_modules package-lock.json yarn.lock pnpm-lock.yaml
npm cache clean --force 2>/dev/null || true
yarn cache clean 2>/dev/null || true
pnpm store prune 2>/dev/null || true
npm install || yarn install || pnpm install
echo 'Dependencies reset and reinstalled'
```

**Warning**: This will delete existing dependencies and reinstall everything.
