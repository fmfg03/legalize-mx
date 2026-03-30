#!/usr/bin/env node

/**
 * Claude Code Slash Command: /workflows
 * Enterprise Development Workflows
 */

const { execSync } = require('child_process');

exports.command = 'workflows';
exports.description = 'Enterprise development workflows and pipelines';
exports.usage = '/workflows [list|run|info] [workflow-name]';
exports.category = 'Development';

exports.handler = function(args, options) {
    try {
        const command = args.join(' ');
        const fullCommand = `claude-workflows ${command}`;
        
        console.log(`🔄 Running: ${fullCommand}`);
        
        const result = execSync(fullCommand, { 
            encoding: 'utf8',
            stdio: 'inherit'
        });
        
        return { success: true };
        
    } catch (error) {
        console.error('❌ Workflows Error:', error.message);
        return { success: false, error: error.message };
    }
};

exports.subcommands = {
    'list': {
        description: 'List available enterprise workflows',
        usage: '/workflows list'
    },
    'run': {
        description: 'Execute a workflow pipeline',
        usage: '/workflows run feature-complete'
    },
    'info': {
        description: 'Get workflow information',
        usage: '/workflows info bug-fix'
    }
};

if (require.main === module) {
    const args = process.argv.slice(2);
    exports.handler(args, {});
}