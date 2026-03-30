---
description: Format code in the project
category: development
allowed-tools: Bash(npm:*), Bash(prettier:*), Bash(black:*), Bash(cargo:*)
argument-hint: ""
---

# Format Code

Apply consistent code formatting across the project.

## Supported Formatters

- **JavaScript/TypeScript**: Prettier
- **Python**: black, autopep8
- **Rust**: cargo fmt
- **Go**: gofmt

## Execution

Format code:

```bash
npm run format || prettier --write . || black . || cargo fmt || gofmt -w .
```

The command will detect and run the appropriate code formatter.
