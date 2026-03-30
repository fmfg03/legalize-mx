#!/usr/bin/env node

const { Command } = require('commander');
const program = new Command();

program
  .name('context-engine')
  .description('Unified Context Engineering System - Memory + .ai/ + DSPy + GEPA')
  .argument('[action]', 'Action to perform: init|retrieve|offload|stats|workflow|optimize', 'init')
  .option('-p, --project <path>', 'Project directory', '.')
  .option('-q, --query <query>', 'Search query for retrieval')
  .option('-k, --key <key>', 'Storage key for offloading')
  .option('-c, --content <content>', 'Content to store')
  .option('-w, --workflow <name>', 'Workflow template to run')
  .option('-b, --budget <tokens>', 'Token budget', '2000')
  .option('--compact', 'Use compact output format')
  .action((action, options) => {
    const actions = {
      'init': initContextEngine,
      'retrieve': retrieveContext,
      'offload': offloadContext,
      'stats': showStats,
      'workflow': runWorkflow,
      'optimize': optimizeContext
    };

    const handler = actions[action] || showHelp;
    handler(options);
  });

program.parse();

function initContextEngine(options) {
  console.log(`
╔═══════════════════════════════════════════════════════════════╗
║  🚀 Unified Context Engineering System                        ║
║  Integrating: Memory + create-ai-chat-context + DSPy + GEPA  ║
╚═══════════════════════════════════════════════════════════════╝

Initializing context engineering system in: ${options.project}

This will:
  1. Initialize Memory Module (global patterns)
  2. Create .ai/ directory (project-specific docs)
  3. Set up DSPy hybrid RAG module
  4. Install GEPA workflow templates

Running initialization...
  `);

  return {
    template: 'prompt',
    prompt: `You are initializing the Unified Context Engineering System.

**Tasks:**

1. **Initialize Memory Module**
   - Run: exec(open('/root/.claude/enhanced-memory/simple-memory.py').read())
   - Verify it works with: memory.get_stats()

2. **Initialize create-ai-chat-context**
   - Run: aic init in project directory ${options.project}
   - Verify .ai/ directory was created

3. **Set up DSPy Hybrid RAG**
   - Make executable: chmod +x /root/.claude/context-engine/modules/dspy_hybrid_rag.py
   - Test with: python3 /root/.claude/context-engine/modules/dspy_hybrid_rag.py "test task"

4. **Show available workflows**
   - List: ls -la /root/.claude/context-engine/workflows/

5. **Display success message and next steps**

Be concise and confirm each component is working.`
  };
}

function retrieveContext(options) {
  if (!options.query) {
    console.error('Error: --query required for retrieval');
    process.exit(1);
  }

  return {
    template: 'prompt',
    prompt: `Retrieve context using the Hybrid RAG system.

**Task:** Find relevant context for: "${options.query}"

**Steps:**

1. Use the DSPy Hybrid RAG module:
   \`\`\`bash
   python3 /root/.claude/context-engine/modules/dspy_hybrid_rag.py \\
     "${options.query}" \\
     --project ${options.project} \\
     --budget ${options.budget} \\
     ${options.compact ? '--compact' : ''}
   \`\`\`

2. Show the results in a clear format

3. Explain what was retrieved from:
   - Global memory patterns
   - Project .ai/ docs
   - Token usage

Keep output concise and actionable.`
  };
}

function offloadContext(options) {
  if (!options.key || !options.content) {
    console.error('Error: --key and --content required for offloading');
    process.exit(1);
  }

  return {
    template: 'prompt',
    prompt: `Offload context to the appropriate storage.

**Task:** Store content with key "${options.key}"

**Steps:**

1. Use the Unified Context Manager:
   \`\`\`bash
   python3 /root/.claude/context-engine/unified-context-manager.py \\
     offload \\
     --project ${options.project} \\
     --key "${options.key}" \\
     --content "${options.content}"
   \`\`\`

2. Confirm storage location (memory or .ai/)
3. Show the lightweight reference created

Be brief and show the reference token.`
  };
}

function showStats(options) {
  return {
    template: 'prompt',
    prompt: `Show comprehensive context usage statistics.

**Steps:**

1. Get stats from Unified Context Manager:
   \`\`\`bash
   python3 /root/.claude/context-engine/unified-context-manager.py \\
     stats \\
     --project ${options.project}
   \`\`\`

2. Also get .ai/ stats:
   \`\`\`bash
   cd ${options.project} && aic stats && aic tokens
   \`\`\`

3. Present in a clear summary:
   - Memory Module usage
   - Project .ai/ token count
   - Context budget remaining
   - Optimization opportunities

Format nicely with tables if possible.`
  };
}

function runWorkflow(options) {
  if (!options.workflow) {
    console.log(`
Available Context Engineering Workflows:

1. **hybrid-rag-workflow**
   - Parallel retrieval from memory + .ai/ + codebase
   - DSPy ranking and optimization
   - Use: --workflow hybrid-rag-workflow

2. **minimal-toolload-workflow**
   - Specialized agents with minimal tool sets
   - 85% context reduction vs single agent
   - Use: --workflow minimal-toolload-workflow

3. **context-quarantine-workflow**
   - Multi-tenant data isolation
   - Complete context quarantine
   - Use: --workflow context-quarantine-workflow

Usage: /context-engine workflow --workflow <name>
    `);
    return;
  }

  return {
    template: 'prompt',
    prompt: `Run the ${options.workflow} context engineering workflow.

**Steps:**

1. Load workflow definition:
   \`\`\`bash
   cat /root/.claude/context-engine/workflows/${options.workflow}.json
   \`\`\`

2. Explain the workflow strategy:
   - Context engineering approach
   - Agents involved
   - Expected efficiency gains

3. Ask user for task details to execute the workflow

4. Execute the workflow using the appropriate agents and strategies

Present the workflow clearly before execution.`
  };
}

function optimizeContext(options) {
  return {
    template: 'prompt',
    prompt: `Analyze and optimize current context usage.

**Analysis Tasks:**

1. **Context Audit:**
   - Current project: ${options.project}
   - Check .ai/ directory size and structure
   - Check memory module usage
   - Identify context bloat

2. **Optimization Recommendations:**
   - Which content should be offloaded?
   - Which .ai/ files should be pruned/summarized?
   - Are there duplicate patterns in memory?
   - Token budget analysis

3. **Apply Optimizations:**
   - Offer to run chat-finish to update .ai/
   - Suggest summarization for old logs
   - Recommend memory compaction if needed

4. **Before/After Metrics:**
   - Tokens before optimization
   - Tokens after optimization
   - Efficiency gained

Provide specific, actionable recommendations.`
  };
}

function showHelp() {
  console.log(`
Unified Context Engineering System

Commands:
  init              Initialize all context systems (Memory + .ai/ + DSPy + GEPA)
  retrieve          Retrieve context using hybrid RAG
  offload           Offload content to memory or .ai/
  stats             Show context usage statistics
  workflow          Run pre-built context engineering workflow
  optimize          Analyze and optimize context usage

Examples:
  /context-engine init
  /context-engine retrieve --query "authentication patterns"
  /context-engine stats
  /context-engine workflow --workflow hybrid-rag-workflow
  /context-engine optimize

Options:
  -p, --project <path>      Project directory (default: .)
  -q, --query <query>       Search query
  -k, --key <key>           Storage key
  -c, --content <content>   Content to store
  -w, --workflow <name>     Workflow template
  -b, --budget <tokens>     Token budget (default: 2000)
  --compact                 Compact output

Context Strategies:
  1. Offloading - Store outside context window
  2. Pruning - Remove low-signal tokens
  3. RAG - Just-in-time retrieval
  4. Summarization - Compress history
  5. Tool Loadout - Minimal tool sets per agent
  6. Quarantine - Isolated contexts
  `);
}
