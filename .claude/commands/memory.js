#!/usr/bin/env node

/**
 * Claude Code Slash Command: /memory
 * Learning Memory System
 */

const { execSync } = require('child_process');

exports.command = 'memory';
exports.description = 'Learning memory system for pattern recognition';
exports.usage = '/memory [learn|suggest|list|stats] [options]';
exports.category = 'Intelligence';

exports.handler = function(args, options) {
    try {
        const command = args.join(' ');
        const fullCommand = `claude-memory ${command}`;
        
        console.log(`🧠 Running: ${fullCommand}`);
        
        const result = execSync(fullCommand, { 
            encoding: 'utf8',
            stdio: 'inherit'
        });
        
        return { success: true };
        
    } catch (error) {
        console.error('❌ Memory Error:', error.message);
        return { success: false, error: error.message };
    }
};

exports.subcommands = {
    'learn': {
        description: 'Learn from successful patterns',
        usage: '/memory learn "JWT authentication" "httpOnly cookies with bcrypt"'
    },
    'suggest': {
        description: 'Get pattern-based suggestions',
        usage: '/memory suggest "implement user auth"'
    },
    'list': {
        description: 'List learned patterns',
        usage: '/memory list'
    },
    'stats': {
        description: 'View learning statistics',
        usage: '/memory stats'
    }
};

if (require.main === module) {
    const args = process.argv.slice(2);
    exports.handler(args, {});
}