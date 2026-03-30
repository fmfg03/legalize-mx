---
description: Start the development server
category: development
allowed-tools: Bash(npm:*), Bash(yarn:*), Bash(pnpm:*), Bash(cargo:*)
argument-hint: ""
---

# Start Development Server

Launch the development server for the current project.

## Supported Development Servers

- **Node.js**: `npm start`, `npm run dev`, `yarn start`, `yarn dev`
- **Python**: `python manage.py runserver`, `flask run`
- **Rust**: `cargo run`
- **Go**: `go run .`

## Execution

Start development server:

```bash
npm start || npm run dev || yarn start || yarn dev || pnpm start || pnpm dev || python manage.py runserver || flask run || cargo run || go run .
```

The command will detect and start the appropriate development server.
