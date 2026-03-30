---
description: Run project tests
category: development
allowed-tools: Bash(npm:*), Bash(yarn:*), Bash(pnpm:*), Bash(pytest:*), Bash(cargo:*)
argument-hint: ""
---

# Run Tests

Execute the project's test suite using the appropriate test runner.

## Supported Test Frameworks

- **Node.js**: `npm test`, `yarn test`, `pnpm test`
- **Python**: `pytest`, `python -m pytest`
- **Rust**: `cargo test`
- **Go**: `go test`

## Execution

Run the test suite:

```bash
npm test || yarn test || pnpm test || pytest || python -m pytest || cargo test || go test ./...
```

The command will detect and run tests using the appropriate framework.
