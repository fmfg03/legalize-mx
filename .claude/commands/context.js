#!/usr/bin/env node

/**
 * Claude Code Slash Command: /context
 * Intelligent Project Context System
 */

const { execSync } = require('child_process');

exports.command = 'context';
exports.description = 'Intelligent project context analysis and configuration';
exports.usage = '/context [analyze|init|recommend] [options]';
exports.category = 'Intelligence';

exports.handler = function(args, options) {
    try {
        const command = args.join(' ');
        const fullCommand = `claude-context ${command}`;
        
        console.log(`🎯 Running: ${fullCommand}`);
        
        const result = execSync(fullCommand, { 
            encoding: 'utf8',
            stdio: 'inherit'
        });
        
        return { success: true };
        
    } catch (error) {
        console.error('❌ Context Error:', error.message);
        return { success: false, error: error.message };
    }
};

exports.subcommands = {
    'analyze': {
        description: 'Analyze current project context',
        usage: '/context analyze'
    },
    'init': {
        description: 'Initialize project with optimal configuration',
        usage: '/context init --auto-configure'
    },
    'recommend': {
        description: 'Get intelligent project recommendations',
        usage: '/context recommend'
    }
};

if (require.main === module) {
    const args = process.argv.slice(2);
    exports.handler(args, {});
}