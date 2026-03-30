#!/usr/bin/env node

/**
 * Claude Code Slash Command: /analytics
 * Agent Performance Analytics System
 */

const { execSync } = require('child_process');

exports.command = 'analytics';
exports.description = 'Agent performance analytics and monitoring';
exports.usage = '/analytics [performance|top|trends] [agent-name]';
exports.category = 'Analytics';

exports.handler = function(args, options) {
    try {
        const command = args.join(' ');
        const fullCommand = `claude-analytics ${command}`;
        
        console.log(`📊 Running: ${fullCommand}`);
        
        const result = execSync(fullCommand, { 
            encoding: 'utf8',
            stdio: 'inherit'
        });
        
        return { success: true };
        
    } catch (error) {
        console.error('❌ Analytics Error:', error.message);
        return { success: false, error: error.message };
    }
};

exports.subcommands = {
    'performance': {
        description: 'Get agent performance metrics',
        usage: '/analytics performance react-expert'
    },
    'top': {
        description: 'View top performing agents',
        usage: '/analytics top'
    },
    'trends': {
        description: 'Analyze performance trends',
        usage: '/analytics trends'
    }
};

if (require.main === module) {
    const args = process.argv.slice(2);
    exports.handler(args, {});
}