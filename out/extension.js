"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const path = __importStar(require("path"));
const fs = __importStar(require("fs"));
const vscode = __importStar(require("vscode"));
function activate(context) {
    // Use output channel for better visibility - show it immediately
    const outputChannel = vscode.window.createOutputChannel('SBHacks12');
    outputChannel.show(true);
    outputChannel.appendLine('=== SBHacks12 extension is activating ===');
    outputChannel.appendLine(`Extension path: ${context.extensionPath}`);
    outputChannel.appendLine(`VS Code version: ${vscode.version}`);
    console.log('SBHacks12 extension is now activating...');
    // Register a simple command to verify extension is loaded
    const testCommand = vscode.commands.registerCommand('sbhacks12.test', () => {
        vscode.window.showInformationMessage('SBHacks12 extension is active!');
        outputChannel.appendLine('Test command executed');
    });
    context.subscriptions.push(testCommand);
    // Check if the MCP API is available
    outputChannel.appendLine(`vscode.lm exists: ${!!vscode.lm}`);
    outputChannel.appendLine(`vscode.lm keys: ${vscode.lm ? Object.keys(vscode.lm).join(', ') : 'N/A'}`);
    if (!vscode.lm || typeof vscode.lm.registerMcpServerDefinitionProvider !== 'function') {
        const errorMsg = 'MCP Server Definition Provider API is not available. This API may require VS Code Insiders or enabling proposed APIs.';
        console.error(errorMsg);
        outputChannel.appendLine(`ERROR: ${errorMsg}`);
        vscode.window.showErrorMessage(errorMsg);
        return;
    }
    const didChangeEmitter = new vscode.EventEmitter();
    try {
        context.subscriptions.push(vscode.lm.registerMcpServerDefinitionProvider('Visual Testing MCP', {
            onDidChangeMcpServerDefinitions: didChangeEmitter.event,
            provideMcpServerDefinitions: async () => {
                outputChannel.appendLine('provideMcpServerDefinitions called');
                let servers = [];
                // Get workspace folder for proper paths
                const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || context.extensionPath;
                const serverPath = path.join(workspaceFolder, 'server', 'server.py');
                const pythonPath = path.join(workspaceFolder, '.venv', 'bin', 'python');
                outputChannel.appendLine(`Workspace folder: ${workspaceFolder}`);
                outputChannel.appendLine(`Server path: ${serverPath}`);
                outputChannel.appendLine(`Server exists: ${fs.existsSync(serverPath)}`);
                outputChannel.appendLine(`Python path: ${pythonPath}`);
                outputChannel.appendLine(`Python exists: ${fs.existsSync(pythonPath)}`);
                // Load environment variables from system env first, then .env file
                let envVars = {
                    TL_API_KEY: process.env.TL_API_KEY || '',
                    TL_ID: process.env.TL_ID || ''
                };
                const envFilePath = path.join(workspaceFolder, '.env');
                if (fs.existsSync(envFilePath)) {
                    const envContent = fs.readFileSync(envFilePath, 'utf-8');
                    for (const line of envContent.split('\n')) {
                        const trimmedLine = line.trim();
                        if (trimmedLine && !trimmedLine.startsWith('#')) {
                            const match = trimmedLine.match(/^([^=]+)=['"]?([^'"]*)['"]?$/);
                            if (match) {
                                envVars[match[1].trim()] = match[2].trim();
                            }
                        }
                    }
                }
                outputChannel.appendLine(`Env vars loaded: TL_API_KEY=${envVars.TL_API_KEY ? '[SET]' : '[NOT SET]'}, TL_ID=${envVars.TL_ID ? '[SET]' : '[NOT SET]'}`);
                // Use the venv python if it exists, otherwise fall back to system python
                const pythonCommand = fs.existsSync(pythonPath) ? pythonPath : 'python';
                outputChannel.appendLine(`Using python command: ${pythonCommand}`);
                const serverDef = new vscode.McpStdioServerDefinition('Visual Testing MCP Server', pythonCommand, [serverPath], envVars);
                // Set the working directory to the workspace folder
                serverDef.cwd = workspaceFolder;
                servers.push(serverDef);
                outputChannel.appendLine(`Returning ${servers.length} server definition(s)`);
                return servers;
            },
            resolveMcpServerDefinition: async (server) => {
                outputChannel.appendLine(`resolveMcpServerDefinition called for: ${server.label}`);
                if (server.label === 'Visual Testing MCP Server') {
                    // Only prompt for values that are missing
                    const currentEnv = server.env || {};
                    if (!currentEnv.TL_API_KEY) {
                        const api_key = await vscode.window.showInputBox({
                            prompt: 'Enter your TwelveLabs API key',
                            ignoreFocusOut: true
                        });
                        if (api_key === undefined) {
                            // User cancelled
                            outputChannel.appendLine('User cancelled API key input');
                            return undefined;
                        }
                        currentEnv.TL_API_KEY = api_key;
                    }
                    if (!currentEnv.TL_ID) {
                        const tl_id = await vscode.window.showInputBox({
                            prompt: 'Enter your TwelveLabs Index ID',
                            ignoreFocusOut: true
                        });
                        if (tl_id === undefined) {
                            // User cancelled
                            outputChannel.appendLine('User cancelled TL_ID input');
                            return undefined;
                        }
                        currentEnv.TL_ID = tl_id;
                    }
                    server.env = currentEnv;
                    outputChannel.appendLine('Server definition resolved successfully');
                }
                return server;
            }
        }));
        outputChannel.appendLine('MCP Server Definition Provider registered successfully');
        console.log('MCP Server Definition Provider registered successfully');
    }
    catch (error) {
        const errorMsg = `Failed to register MCP Server Definition Provider: ${error}`;
        console.error(errorMsg);
        outputChannel.appendLine(errorMsg);
        vscode.window.showErrorMessage(errorMsg);
    }
    // console.log('SBHacks12 extension is now active!');
    // // Register command to start the server
    // const startServerCommand = vscode.commands.registerCommand('sbhacks12.startServer', async () => {
    //     await startLanguageServer(context);
    // });
    // // Register command to stop the server
    // const stopServerCommand = vscode.commands.registerCommand('sbhacks12.stopServer', async () => {
    //     await stopLanguageServer();
    // });
    // context.subscriptions.push(startServerCommand, stopServerCommand);
    // // Auto-start the language server
    // startLanguageServer(context);
}
function getPythonPath(extensionPath) {
    // Check for uv virtual environment first
    const uvVenvPath = path.join(extensionPath, '.venv', 'bin', 'python');
    // On Windows, use different path
    const isWindows = process.platform === 'win32';
    const venvPython = isWindows
        ? path.join(extensionPath, '.venv', 'Scripts', 'python.exe')
        : uvVenvPath;
    // Try to get Python path from VS Code settings
    const pythonConfig = vscode.workspace.getConfiguration('python');
    const configuredPython = pythonConfig.get('defaultInterpreterPath');
    if (configuredPython) {
        return configuredPython;
    }
    // Default to venv python or system python
    return venvPython;
}
function deactivate() {
    // Nothing to clean up - MCP servers are managed by VS Code
    return undefined;
}
//# sourceMappingURL=extension.js.map