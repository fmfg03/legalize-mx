---
description: Build the current project
category: development
allowed-tools: Bash(npm:*), Bash(yarn:*), Bash(pnpm:*), Bash(make:*), Bash(cargo:*)
argument-hint: ""
---

# Build Project

Build the current project using the appropriate build system.

## Supported Build Systems

- **Node.js**: `npm run build`, `yarn build`, `pnpm build`
- **Rust**: `cargo build`
- **Go**: `go build`
- **Make**: `make`

## Execution

Build the project:

```bash
npm run build || yarn build || pnpm build || make build || make || cargo build || go build
```

The command will try each build system until one succeeds.
