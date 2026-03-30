---
description: Run linting on the project
category: development
allowed-tools: Bash(npm:*), Bash(yarn:*), Bash(pnpm:*), Bash(eslint:*), Bash(pylint:*)
argument-hint: ""
---

# Lint Code

Run code linting and style checks on the project.

## Supported Linters

- **JavaScript/TypeScript**: ESLint, Prettier
- **Python**: pylint, flake8, black
- **Rust**: cargo clippy
- **Go**: golangci-lint, gofmt

## Execution

Run linting:

```bash
npm run lint || yarn lint || pnpm lint || eslint . || pylint . || cargo clippy || golangci-lint run
```

The command will detect and run the appropriate linters for your project.
