#!/usr/bin/env node

/**
 * Claude Code Slash Command: /orchestrator
 * Magic DSPy Orchestrator System
 */

const { execSync } = require('child_process');

exports.command = 'orchestrator';
exports.description = 'Magic DSPy Orchestrator for multi-agent coordination';
exports.usage = '/orchestrator [run|compete|collaborate|iterate] "task" [options]';
exports.category = 'Orchestration';

exports.handler = function(args, options) {
    try {
        const command = args.join(' ');
        const fullCommand = `magic-orchestrator ${command}`;
        
        console.log(`🎯 Running: ${fullCommand}`);
        
        const result = execSync(fullCommand, { 
            encoding: 'utf8',
            stdio: 'inherit'
        });
        
        return { success: true };
        
    } catch (error) {
        console.error('❌ Orchestrator Error:', error.message);
        return { success: false, error: error.message };
    }
};

exports.subcommands = {
    'run': {
        description: 'Run adaptive multi-agent task',
        usage: '/orchestrator run "build React app with tests"'
    },
    'compete': {
        description: 'Competitive agent execution',
        usage: '/orchestrator compete "optimize performance" --agents react-expert,vite-expert'
    },
    'collaborate': {
        description: 'Collaborative agents working together',
        usage: '/orchestrator collaborate "design architecture" --agents backend-architect,database-expert'
    },
    'iterate': {
        description: 'Progressive iterative refinement',
        usage: '/orchestrator iterate "improve auth system" --rounds 3'
    }
};

if (require.main === module) {
    const args = process.argv.slice(2);
    exports.handler(args, {});
}