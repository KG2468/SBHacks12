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
const vscode = __importStar(require("vscode"));
const node_1 = require("vscode-languageclient/node");
let client;
function activate(context) {
    console.log('SBHacks12 extension is now active!');
    // Register command to start the server
    const startServerCommand = vscode.commands.registerCommand('sbhacks12.startServer', async () => {
        await startLanguageServer(context);
    });
    // Register command to stop the server
    const stopServerCommand = vscode.commands.registerCommand('sbhacks12.stopServer', async () => {
        await stopLanguageServer();
    });
    context.subscriptions.push(startServerCommand, stopServerCommand);
    // Auto-start the language server
    startLanguageServer(context);
}
async function startLanguageServer(context) {
    if (client) {
        vscode.window.showInformationMessage('Language server is already running.');
        return;
    }
    // Path to the Python server script
    const serverPath = path.join(context.extensionPath, 'server', 'server.py');
    // Get Python path - try to use the uv virtual environment
    const pythonPath = getPythonPath(context.extensionPath);
    const serverOptions = {
        command: pythonPath,
        args: [serverPath],
        transport: node_1.TransportKind.stdio
    };
    const clientOptions = {
        // Register the server for all documents
        documentSelector: [{ scheme: 'file', language: '*' }],
        synchronize: {
            // Notify the server about file changes
            fileEvents: vscode.workspace.createFileSystemWatcher('**/*')
        },
        outputChannelName: 'SBHacks12 Language Server'
    };
    client = new node_1.LanguageClient('sbhacks12', 'SBHacks12 Language Server', serverOptions, clientOptions);
    try {
        await client.start();
        vscode.window.showInformationMessage('Language server started successfully.');
    }
    catch (error) {
        vscode.window.showErrorMessage(`Failed to start language server: ${error}`);
        client = undefined;
    }
}
async function stopLanguageServer() {
    if (!client) {
        vscode.window.showInformationMessage('Language server is not running.');
        return;
    }
    try {
        await client.stop();
        client = undefined;
        vscode.window.showInformationMessage('Language server stopped.');
    }
    catch (error) {
        vscode.window.showErrorMessage(`Failed to stop language server: ${error}`);
    }
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
    if (!client) {
        return undefined;
    }
    return client.stop();
}
//# sourceMappingURL=extension.js.map