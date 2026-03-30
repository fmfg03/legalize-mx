#!/usr/bin/env node

/**
 * Claude Code Slash Command: /create-agent
 * Natural Language Agent Creation System
 */

const { execSync } = require('child_process');

exports.command = 'create-agent';
exports.description = 'Create custom agents from natural language descriptions';
exports.usage = '/create-agent "I need an agent that validates APIs"';
exports.category = 'Development';

exports.handler = function(args, options) {
    try {
        const description = args.join(' ');
        const fullCommand = `claude-create agent "${description}"`;
        
        console.log(`🤖 Running: ${fullCommand}`);
        
        const result = execSync(fullCommand, { 
            encoding: 'utf8',
            stdio: 'inherit'
        });
        
        return { success: true };
        
    } catch (error) {
        console.error('❌ Agent Creation Error:', error.message);
        return { success: false, error: error.message };
    }
};

exports.subcommands = {
    'agent': {
        description: 'Create a new specialized agent',
        usage: '/create-agent "I need an agent for API validation"'
    },
    'analyze': {
        description: 'Analyze agent requirements without creating',
        usage: '/create-agent analyze "database optimization agent"'
    }
};

if (require.main === module) {
    const args = process.argv.slice(2);
    exports.handler(args, {});
}