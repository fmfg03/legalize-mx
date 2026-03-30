#!/usr/bin/env node

/**
 * Claude Code Slash Command: /intelligence
 * Cross-Project Intelligence System
 */

const { execSync } = require('child_process');

exports.command = 'intelligence';
exports.description = 'Cross-project pattern discovery and intelligence';
exports.usage = '/intelligence [analyze|suggest|insights] [path]';
exports.category = 'Intelligence';

exports.handler = function(args, options) {
    try {
        const command = args.join(' ');
        const fullCommand = `claude-intelligence ${command}`;
        
        console.log(`🧠 Running: ${fullCommand}`);
        
        const result = execSync(fullCommand, { 
            encoding: 'utf8',
            stdio: 'inherit'
        });
        
        return { success: true };
        
    } catch (error) {
        console.error('❌ Intelligence Error:', error.message);
        return { success: false, error: error.message };
    }
};

exports.subcommands = {
    'analyze': {
        description: 'Analyze project for cross-project patterns',
        usage: '/intelligence analyze ~/project'
    },
    'suggest': {
        description: 'Get pattern suggestions for current project',
        usage: '/intelligence suggest .'
    },
    'insights': {
        description: 'View system-wide intelligence insights',
        usage: '/intelligence insights'
    }
};

if (require.main === module) {
    const args = process.argv.slice(2);
    exports.handler(args, {});
}