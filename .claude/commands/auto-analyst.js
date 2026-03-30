#!/usr/bin/env node

/**
 * Claude Code Slash Command: /auto-analyst
 * Auto-Analyst Data Analytics System
 */

const { execSync } = require('child_process');
const path = require('path');

// Command metadata for Claude Code
exports.command = 'auto-analyst';
exports.description = 'Auto-Analyst data analytics automation system';
exports.usage = '/auto-analyst [analyze|quick-ml|visualize|agents] [options]';
exports.category = 'Analytics';

// Main command handler
exports.handler = function(args, options) {
    try {
        const command = args.join(' ');
        const fullCommand = `claude-auto-analyst ${command}`;
        
        console.log(`🤖 Running: ${fullCommand}`);
        
        const result = execSync(fullCommand, { 
            encoding: 'utf8',
            stdio: 'inherit'
        });
        
        return { success: true };
        
    } catch (error) {
        console.error('❌ Auto-Analyst Error:', error.message);
        return { success: false, error: error.message };
    }
};

// Subcommands
exports.subcommands = {
    'analyze': {
        description: 'Analyze datasets for insights',
        usage: '/auto-analyst analyze "goal" -d data.csv'
    },
    'quick-ml': {
        description: 'Quick machine learning analysis',
        usage: '/auto-analyst quick-ml "task" -d data.csv'
    },
    'visualize': {
        description: 'Create data visualizations',
        usage: '/auto-analyst visualize "charts" -d data.csv'
    },
    'agents': {
        description: 'List available data analytics agents',
        usage: '/auto-analyst agents'
    }
};

// If run directly (for testing)
if (require.main === module) {
    const args = process.argv.slice(2);
    exports.handler(args, {});
}