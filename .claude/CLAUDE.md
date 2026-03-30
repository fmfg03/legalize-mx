# CLAUDE.md

## Core Principle: No Vibe Coding

Don't code by feel. Code by intent.

Every meaningful change should answer: **What are we building, why, and how do we know it works?**

---

## The 5-Phase Discipline

### 1. 🧠 Brainstorm
- What problem are we actually solving?
- What are the constraints and edge cases?
- What existing patterns should we follow or deliberately break?

### 2. 📝 Specify
- Define the expected behavior in concrete terms
- List inputs, outputs, and error conditions
- If you can't specify it, you don't understand it yet

### 3. 📐 Plan
- Identify files and functions that will change
- Choose patterns and dependencies explicitly
- Document architectural decisions and trade-offs

### 4. ⚡ Execute
- Build exactly what was specified—no more, no less
- If you discover the spec was wrong, stop and revise the spec
- Resist the urge to "improve" unrelated code

### 5. 📊 Verify
- Test against the specification
- Review your own diff before considering it done
- Update documentation if behavior changed

### Scaling the Discipline

| Change Size | Required Rigor |
|-------------|----------------|
| Typo/formatting | Just fix it |
| Single function change | Mental walkthrough of phases 1-5 |
| New feature or multi-file | Written plan before code |
| Architectural change | Full specification document |

---

## Code Quality Standards

### Before Writing Code

**Read before writing**
Never modify code you haven't read. Understand existing patterns, naming conventions, and architectural decisions first.

**Question the problem**
Before solving, verify you're solving the right problem. A well-understood problem often reveals a simpler solution.

### While Writing Code

**Clarity Over Cleverness**
- Names should reveal intent: `getUserActiveSubscriptions()` not `getUA()`
- If code needs a comment to explain *what* it does, rewrite it
- Comments explain *why*, not *what*

**Simplicity Standards**
- Prefer explicit over implicit
- One function, one responsibility
- No premature abstractions—wait for the third use case
- Delete dead code; don't comment it out

**Edge Cases**
- Handle errors at system boundaries (user input, APIs, file I/O)
- Trust internal code—don't defensively check everything
- Fail fast with clear error messages

### After Writing Code

1. **Re-read your diff** — Would a teammate understand this in 6 months?
2. **Run tests** — Don't commit what you haven't verified
3. **One thing per commit** — Atomic changes tell a clear story

### The Simplicity Test

Before finishing, ask:
- Can I remove any code without losing functionality?
- Is there a standard library function for this?
- Would a junior developer understand this?

---

## Anti-Patterns vs Patterns

| ❌ Don't | ✅ Do |
|----------|-------|
| "Let me just try something and see" | "Here's what I'm building and why" |
| "I'll refactor this while I'm in here" | "Separate PR for refactoring" |
| "This should work" (without testing) | "I verified it works by..." |
| Start coding before reading codebase | "I read the existing code and will follow its patterns" |
| Add features beyond what was asked | Build exactly what was specified |
| Guess at unclear requirements | Ask before assuming |

---

## When to Push Back

- If a "simple fix" requires architectural changes, say so
- If requirements are ambiguous, ask before assuming
- If the elegant solution takes 10x longer, present both options
- If something seems impossible, it might actually be out of scope

---

## Memory System

Persistent memory across Claude Code sessions.

### Quick Setup

```python
exec(open('/root/.claude/enhanced-memory/simple-memory.py').read())
```

### Usage

```python
# Store patterns
remember("jwt-auth", "const token = jwt.sign({userId}, secret)", "JWT authentication")
remember("db-query", "SELECT * FROM users WHERE active = true", "Active users query")

# Recall patterns
patterns = recall("authentication")
db_patterns = recall("database")

# Store and find error solutions
memory.remember_error("ImportError: fastapi", "pip install fastapi", "missing dependency")
solutions = solve("import error")

# Record decisions
decide("Use PostgreSQL", "Better performance than SQLite")

# Statistics
stats = memory.get_stats()
print(f"Stored {stats['total_patterns']} patterns across {len(stats['projects'])} projects")
```

### Shell Alias (Optional)

```bash
alias mem-init='python3 ~/.claude/enhanced-memory/quick-init.py'
```

### Limitations

- No startup hooks in Claude Code—requires manual initialization
- Each session is isolated
- Memory persists in files, not in session state
