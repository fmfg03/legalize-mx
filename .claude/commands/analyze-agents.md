---
description: Analyze all 41 agent classes and provide optimization recommendations
allowed-tools: Read, Glob, Grep, Bash(find:*, wc:*, grep:*)
category: ai-assistant
---

# Agent Analysis and Optimization

## Step 1: Discover All Agent Classes

Find all Python files containing agent class definitions in the project:

!find /root/samchat/src/devnous -type f -name "*.py" -exec grep -l "class.*Agent" {} \; 2>/dev/null

## Step 2: Analyze Agent Architecture

For each agent file discovered:

1. **Read the agent implementation** - Examine class structure, methods, and dependencies
2. **Identify patterns** - Look for:
   - Common base classes and inheritance patterns
   - Shared utilities and duplicate code
   - LLM provider usage and configuration
   - Async/await patterns and concurrency
   - Error handling and logging practices
   - Memory management and caching

## Step 3: Performance Analysis

Evaluate each agent for:

- **Efficiency**: Are LLM calls optimized? Are there unnecessary API calls?
- **Concurrency**: Does the agent properly leverage async/await?
- **Resource usage**: Memory footprint, token consumption
- **Caching**: Are responses cached appropriately?
- **Error handling**: Robust retry logic and fallback mechanisms?

## Step 4: Code Quality Assessment

Check for:

- **Type hints**: Proper typing throughout the codebase
- **Documentation**: Docstrings, comments, and inline documentation
- **Test coverage**: Existence of unit and integration tests
- **Security**: Input validation, sanitization, secret management
- **Maintainability**: Code complexity, duplication, modularity

## Step 5: Provide Recommendations

Generate a comprehensive report with:

### 🎯 High-Priority Optimizations
List critical issues that should be addressed immediately

### ⚡ Performance Improvements
Specific recommendations for speed and efficiency gains

### 🔧 Refactoring Opportunities
Areas where code can be simplified or deduplicated

### 🧪 Testing Gaps
Missing test coverage and recommended test cases

### 📚 Documentation Needs
Areas lacking proper documentation

### 🏗️ Architectural Suggestions
Higher-level structural improvements

## Output Format

Present findings as a structured markdown report with:
- Executive summary with key metrics
- Agent-by-agent analysis table
- Priority-ranked recommendations
- Code examples for suggested improvements
- Estimated impact and effort for each recommendation
